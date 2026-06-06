# 砖窑作坊温度监控与工单管理系统

## 系统概述

本系统实现砖窑作坊阶梯窑的全流程数字化管理，包括窑次管理、五段温压监控、烟道塌陷自动检测、砖批次品级管理、返工工单自动生成以及装车出库管控。

## 功能模块

### 1. 窑次管理
- 窑次创建与状态跟踪（装窑中→烧制中→冷却中→已完成）
- 窑道编号与计划到温时刻记录
- 一窑从装窑到出窑全程可查

### 2. 五段温压监控
- 沿窑长分五段，每分钟记录各段温度与烟道负压
- 实时温度/负压曲线图展示
- 历史数据回溯与对比分析

### 3. 烟道塌陷检测
**检测规则**：
- 时间范围：计划到温时刻前半小时内
- 对比基准：该段前一小时温度均值
- 触发条件：温度较均值低 35°C 以上，且持续 12 分钟以上
- 扫描频率：后台每分钟自动扫描

### 4. 砖批次管理
- 出窑后登记色度品级（1–5，5 最好）
- 登记翘曲毫米数
- 批次状态跟踪

### 5. 工单管理
**自动生成条件**：
1. 烟道塌陷 → 生成「烟道塌陷」工单
2. 烟道塌陷 + 存在品级≤2 的批次 → 自动为该批次生成「返工」工单

**工单状态**：待处理 → 处理中 → 已关闭

### 6. 装车出库管控
**核心规则**：工单未关闭前，该窑次关联批次不得装车出库

系统在装车操作时强制校验：
- 该窑次是否存在未关闭工单
- 批次当前状态是否允许装车
- 校验不通过则返回明确错误原因

## 快速启动

### 环境要求
- Docker >= 20.10
- Docker Compose >= 2.0

### 启动步骤

```bash
# 1. 构建并启动所有服务
docker-compose up -d --build

# 2. 等待数据库就绪后，导入演示数据
docker-compose exec backend python seed_data.py

# 3. 访问系统
# 前端: http://localhost:8080
# 后端API文档: http://localhost:8000/docs
```

### 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 停止服务
docker-compose down

# 停止并清理数据
docker-compose down -v
```

## 项目结构

```
.
├── docker-compose.yml          # Docker Compose 配置
├── backend/                    # 后端服务 (FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # 应用入口 + API路由
│   ├── models.py               # 数据库模型
│   ├── schemas.py              # Pydantic 数据模型
│   ├── crud.py                 # 业务逻辑 + 烟道塌陷检测
│   ├── database.py             # 数据库连接配置
│   ├── seed_data.py            # 演示数据生成脚本
│   └── init.sql                # 数据库初始化脚本
├── frontend/                   # 前端应用 (Vue.js)
│   ├── Dockerfile
│   ├── nginx.conf              # Nginx配置(含API代理)
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router/index.js
│       ├── api/index.js
│       └── views/
│           ├── FiringList.vue      # 窑次列表
│           ├── FiringDetail.vue    # 窑次详情 + 温压曲线
│           ├── Orders.vue          # 工单待办
│           └── Loading.vue         # 装车操作
└── README.md
```

## 并发处理说明

### 1. 工单与装车的并发控制

**问题场景**：
- 用户A正在处理某窑次的工单，即将关闭
- 用户B同时尝试为该窑次的批次执行装车操作

**解决方案**：

#### 数据库事务 + 行级锁
在 [crud.py](backend/crud.py#L172-L186) 的 `create_loading_record` 函数中：

```python
def create_loading_record(db: Session, loading: LoadingRecordCreate):
    # 第一步：检查是否可装车（查询窑次工单状态）
    can_load, message = can_load_batch(db, loading.batch_id)
    if not can_load:
        return None, message
    
    # 第二步：在同一事务中执行写入
    db_loading = LoadingRecord(**loading.model_dump())
    db.add(db_loading)
    
    batch = get_batch(db, loading.batch_id)
    if batch:
        batch.status = 'loaded'  # 原子更新批次状态
    
    db.commit()  # 事务提交：只有校验通过才会写入
    return db_loading, "装车成功"
```

#### 关键保护机制

| 层级 | 保护方式 | 说明 |
|------|----------|------|
| 前端 | UI禁用 + 状态标记 | 批次 `can_load=false` 时禁用装车按钮 |
| API | 业务逻辑校验 | 写入前查询 `has_open_orders()` 校验 |
| 数据库 | 事务原子性 | 校验与写入在同一事务，避免竞态 |
| 状态机 | 批次状态流转 | `produced → rework_pending → rework_done → loaded` |

### 2. 定时扫描的并发安全

**问题场景**：
- 后台定时任务扫描烟道塌陷
- 同时有API请求也在执行手动扫描

**解决方案**：

#### 事件去重 + 幂等处理
在 [crud.py](backend/crud.py#L259-L264) 中：

```python
existing_event = db.query(FlueCollapseEvent).filter(
    FlueCollapseEvent.firing_id == firing.id,
    FlueCollapseEvent.segment == segment,
    FlueCollapseEvent.end_time.is_(None),
    func.abs(func.extract('epoch', FlueCollapseEvent.start_time - group[0].recorded_at)) < 60
).first()
```

- 同一事件（同窑次+同段位+相近开始时间）只创建一次
- 重复扫描时更新持续时间，不重复创建工单

#### 工单防重
```python
existing_order = db.query(WorkOrder).filter(
    WorkOrder.firing_id == firing.id,
    WorkOrder.segment == segment,
    WorkOrder.order_type == 'flue_collapse',
    WorkOrder.status != 'closed'
).first()
```

- 同类型未关闭工单不重复创建

### 3. 数据库连接池配置

在 [database.py](backend/database.py#L15-L16) 中：

```python
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,   # 连接前健康检查
    pool_recycle=300      # 连接5分钟回收，避免超时
)
```

支持高并发请求下的数据库连接复用与管理。

## API 接口列表

### 窑次管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/firings` | 获取窑次列表 |
| GET | `/api/firings/{id}` | 获取窑次详情（含曲线数据） |
| POST | `/api/firings` | 创建窑次 |
| PUT | `/api/firings/{id}` | 更新窑次状态 |

### 温度读数
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/readings` | 上报温压读数 |
| GET | `/api/firings/{id}/readings` | 获取窑次读数历史 |

### 砖批次
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/batches` | 获取批次列表 |
| GET | `/api/batches/{id}` | 获取批次详情 |
| POST | `/api/batches` | 登记砖批次 |
| PUT | `/api/batches/{id}` | 更新批次信息 |

### 工单管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/orders` | 获取工单列表 |
| GET | `/api/orders/{id}` | 获取工单详情 |
| PUT | `/api/orders/{id}` | 更新工单状态/关闭工单 |

### 装车管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/loading` | 获取装车记录 |
| POST | `/api/loading` | 执行装车操作（含并发校验） |

### 系统管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/scan-flue-collapse` | 手动触发烟道扫描 |

## 数据模型

### 核心表关系

```
firings (窑次)
    ├── id (PK)
    ├── kiln_number (窑道编号)
    ├── plan_temp_time (计划到温时间)
    ├── status (状态)
    │
    ├─→ temperature_readings (温压读数，1:N)
    │      ├── segment (段1-5)
    │      ├── temperature (温度)
    │      ├── negative_pressure (负压)
    │      └── recorded_at (记录时间)
    │
    ├─→ brick_batches (砖批次，1:N)
    │      ├── batch_code (批次编号)
    │      ├── color_grade (品级1-5)
    │      ├── warpage_mm (翘曲mm)
    │      └── status (状态)
    │
    ├─→ work_orders (工单，1:N)
    │      ├── order_type (flue_collapse/rework)
    │      ├── status (open/in_progress/closed)
    │      ├── segment (关联段位)
    │      └── batch_id (关联返工批次)
    │
    └─→ flue_collapse_events (烟道塌陷事件，1:N)
           ├── segment (段位)
           ├── start_time (开始时间)
           ├── avg_temp_drop (平均降温)
           └── duration_minutes (持续分钟)

brick_batches
    └─→ loading_records (装车记录，1:N)
           ├── vehicle_plate (车牌号)
           ├── operator (操作员)
           └── loading_time (装车时间)
```

## 演示数据说明

运行 `seed_data.py` 后将生成：

| 窑次 | 状态 | 说明 |
|------|------|------|
| K-001 | 烧制中 | 正常烧制，无异常 |
| K-002 | 烧制中 | **第3段烟道塌陷**，含品级1、2批次 → 自动生成返工工单 |
| K-003 | 冷却中 | **第2段烟道塌陷**，含品级2批次 → 自动生成返工工单 |
| K-004 | 已完成 | 已完成，已有装车记录 |
| K-005 | 装窑中 | 新窑次，待开始 |

## 业务流程示例

### 正常流程
```
创建窑次 → 开始烧制 → 每分钟上报温压 → 出窑登记批次 → 无异常 → 批次装车出库
```

### 异常流程
```
创建窑次 → 开始烧制 → 温度异常下降(<-35°C)
                ↓
         后台扫描检测到烟道塌陷
                ↓
         自动创建「烟道塌陷」工单
                ↓
         出窑登记批次，发现品级≤2
                ↓
         自动为该批次创建「返工」工单
                ↓
         【禁止装车】直到所有工单关闭
                ↓
         处理工单 → 关闭工单 → 返工完成
                ↓
         批次可正常装车出库
```

## 技术栈

- **后端**：Python 3.11 + FastAPI + SQLAlchemy 2.0 + APScheduler
- **数据库**：PostgreSQL 15
- **前端**：Vue 3 + Vite + Element Plus + ECharts
- **部署**：Docker Compose + Nginx

## 监控与运维

- 后端日志：`docker-compose logs -f backend`
- 定时任务日志：INFO级别输出扫描结果
- 数据库数据持久化：Docker volume `postgres_data`
- API文档：Swagger UI `http://localhost:8000/docs`
