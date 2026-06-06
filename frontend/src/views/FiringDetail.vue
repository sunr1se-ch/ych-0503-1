<template>
  <div class="firing-detail" v-loading="loading">
    <div class="page-header">
      <div>
        <el-button @click="goBack" :icon="ArrowLeft">返回</el-button>
        <h2 style="display: inline; margin-left: 15px;">
          窑次详情 - {{ firing?.kiln_number }}
        </h2>
        <el-tag :type="statusType(firing?.status)" style="margin-left: 15px;">
          {{ statusText(firing?.status) }}
        </el-tag>
        <el-tag v-if="firing?.has_open_orders" type="danger" effect="dark" style="margin-left: 10px;">
          <el-icon><Warning /></el-icon> 有未关闭工单
        </el-tag>
      </div>
    </div>

    <el-card class="info-card" v-if="firing">
      <el-row :gutter="24">
        <el-col :span="8">
          <div class="info-item">
            <span class="label">窑道编号：</span>
            <span class="value">{{ firing.kiln_number }}</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="info-item">
            <span class="label">计划到温时间：</span>
            <span class="value">{{ formatTime(firing.plan_temp_time) }}</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="info-item">
            <span class="label">开始时间：</span>
            <span class="value">{{ firing.start_time ? formatTime(firing.start_time) : '-' }}</span>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="五段温压曲线" name="chart">
        <el-card>
          <div class="chart-toolbar">
            <el-button-group>
              <el-button :type="chartType === 'temp' ? 'primary' : ''" @click="chartType = 'temp'">
                温度曲线
              </el-button>
              <el-button :type="chartType === 'pressure' ? 'primary' : ''" @click="chartType = 'pressure'">
                负压曲线
              </el-button>
            </el-button-group>
            <div class="legend-info">
              <span v-for="seg in 5" :key="seg" class="legend-item">
                <span class="legend-color" :style="{ background: segmentColors[seg-1] }"></span>
                第{{ seg }}段
              </span>
            </div>
          </div>
          <div ref="chartRef" class="chart-container"></div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="砖批次" name="batches">
        <el-card>
          <div style="margin-bottom: 15px;">
            <el-button type="primary" @click="showAddBatchDialog" :icon="Plus">
              新增批次
            </el-button>
          </div>
          <el-table :data="firing?.batches || []" stripe>
            <el-table-column prop="batch_code" label="批次编号" width="150" />
            <el-table-column prop="color_grade" label="色度品级" width="120">
              <template #default="{ row }">
                <el-tag :type="gradeType(row.color_grade)" effect="dark">
                  {{ row.color_grade }} 级
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="warpage_mm" label="翘曲(mm)" width="120" />
            <el-table-column prop="status" label="状态" width="150">
              <template #default="{ row }">
                <el-tag :type="batchStatusType(row.status)">{{ batchStatusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="可否装车" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.can_load" type="success">可装车</el-tag>
                <el-tag v-else type="danger">禁止装车</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="烟道塌陷事件" name="events">
        <el-card>
          <el-alert 
            v-if="firing?.flue_events?.length > 0"
            type="warning" 
            :title="`检测到 ${firing.flue_events.length} 次烟道塌陷异常`"
            show-icon
            style="margin-bottom: 15px;"
          />
          <el-table :data="firing?.flue_events || []" stripe>
            <el-table-column prop="segment" label="段位" width="100">
              <template #default="{ row }">第{{ row.segment }}段</template>
            </el-table-column>
            <el-table-column label="开始时间" width="180">
              <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
            </el-table-column>
            <el-table-column prop="avg_temp_drop" label="平均降温(°C)" width="150" />
            <el-table-column prop="duration_minutes" label="持续时间(分钟)" width="150" />
            <el-table-column prop="work_order_id" label="关联工单" width="120">
              <template #default="{ row }">
                <el-link v-if="row.work_order_id" type="primary" @click="activeTab = 'orders'">
                  #{{ row.work_order_id }}
                </el-link>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="工单" name="orders">
        <el-card>
          <el-table :data="firing?.orders || []" stripe>
            <el-table-column prop="id" label="工单号" width="100">
              <template #default="{ row }">#{{ row.id }}</template>
            </el-table-column>
            <el-table-column prop="order_type" label="类型" width="140">
              <template #default="{ row }">
                <el-tag :type="row.order_type === 'flue_collapse' ? 'danger' : 'warning'">
                  {{ row.order_type === 'flue_collapse' ? '烟道塌陷' : '返工' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="orderStatusType(row.status)">
                  {{ orderStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="检测时间" width="180">
              <template #default="{ row }">{{ formatTime(row.detected_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="addBatchVisible" title="新增砖批次" width="500px">
      <el-form :model="batchForm" label-width="100px">
        <el-form-item label="批次编号">
          <el-input v-model="batchForm.batch_code" placeholder="例如：K-001-B001" />
        </el-form-item>
        <el-form-item label="色度品级">
          <el-select v-model="batchForm.color_grade" style="width: 100%">
            <el-option v-for="g in 5" :key="g" :label="g + ' 级'" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="翘曲(mm)">
          <el-input-number v-model="batchForm.warpage_mm" :min="0" :max="20" :step="0.1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addBatchVisible = false">取消</el-button>
        <el-button type="primary" @click="createBatch" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { firingApi, batchApi } from '../api'
import * as echarts from 'echarts'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const firing = ref(null)
const activeTab = ref('chart')
const chartType = ref('temp')
const chartRef = ref(null)
let chartInstance = null

const addBatchVisible = ref(false)
const batchForm = reactive({
  batch_code: '',
  color_grade: 3,
  warpage_mm: 2.0
})

const segmentColors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db']

const statusType = (status) => {
  const map = { loading: 'info', firing: 'warning', cooling: 'primary', completed: 'success' }
  return map[status] || 'info'
}

const statusText = (status) => {
  const map = { loading: '装窑中', firing: '烧制中', cooling: '冷却中', completed: '已完成' }
  return map[status] || status
}

const gradeType = (grade) => {
  if (grade >= 4) return 'success'
  if (grade === 3) return 'warning'
  return 'danger'
}

const batchStatusType = (status) => {
  const map = {
    produced: 'info',
    rework_pending: 'warning',
    rework_done: 'primary',
    loaded: 'success',
    shipped: 'success'
  }
  return map[status] || 'info'
}

const batchStatusText = (status) => {
  const map = {
    produced: '已生产',
    rework_pending: '待返工',
    rework_done: '返工完成',
    loaded: '已装车',
    shipped: '已发货'
  }
  return map[status] || status
}

const orderStatusType = (status) => {
  const map = { open: 'danger', in_progress: 'warning', closed: 'success' }
  return map[status] || 'info'
}

const orderStatusText = (status) => {
  const map = { open: '待处理', in_progress: '处理中', closed: '已关闭' }
  return map[status] || status
}

const formatTime = (time) => {
  return time ? dayjs(time).format('YYYY-MM-DD HH:mm') : '-'
}

const initChart = () => {
  if (!chartRef.value || !firing.value) return
  
  if (chartInstance) {
    chartInstance.dispose()
  }
  
  chartInstance = echarts.init(chartRef.value)
  
  const series = []
  const segments = firing.value.segments || []
  
  segments.forEach((seg, idx) => {
    const data = seg.timestamps.map((t, i) => {
      const val = chartType.value === 'temp' ? seg.temperatures[i] : seg.pressures[i]
      return [dayjs(t).toDate(), Number(val)]
    })
    
    series.push({
      name: `第${seg.segment}段`,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2 },
      itemStyle: { color: segmentColors[idx] },
      data: data
    })
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let html = dayjs(params[0].axisValue).format('YYYY-MM-DD HH:mm') + '<br/>'
        params.forEach(p => {
          html += `${p.marker} ${p.seriesName}: ${p.data[1].toFixed(1)} ${chartType.value === 'temp' ? '°C' : 'Pa'}<br/>`
        })
        return html
      }
    },
    legend: {
      data: segments.map(s => `第${s.segment}段`),
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: 60,
      containLabel: true
    },
    xAxis: {
      type: 'time',
      axisLabel: {
        formatter: (value) => dayjs(value).format('MM-DD HH:mm')
      }
    },
    yAxis: {
      type: 'value',
      name: chartType.value === 'temp' ? '温度 (°C)' : '负压 (Pa)',
      axisLabel: {
        formatter: (value) => value.toFixed(0)
      }
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { start: 0, end: 100, bottom: 20 }
    ],
    series: series
  }
  
  chartInstance.setOption(option)
}

const loadFiringDetail = async () => {
  const id = route.params.id
  loading.value = true
  try {
    const res = await firingApi.get(id)
    firing.value = res.data
    await nextTick()
    initChart()
  } catch (e) {
    ElMessage.error('加载详情失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/')
}

const showAddBatchDialog = () => {
  batchForm.batch_code = `${firing.value.kiln_number}-B${String((firing.value.batches?.length || 0) + 1).padStart(3, '0')}`
  batchForm.color_grade = 3
  batchForm.warpage_mm = 2.0
  addBatchVisible.value = true
}

const createBatch = async () => {
  if (!batchForm.batch_code) {
    ElMessage.warning('请填写批次编号')
    return
  }
  
  submitting.value = true
  try {
    await batchApi.create({
      firing_id: firing.value.id,
      ...batchForm
    })
    ElMessage.success('批次创建成功')
    addBatchVisible.value = false
    loadFiringDetail()
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

watch(chartType, () => {
  nextTick(() => initChart())
})

onMounted(() => {
  loadFiringDetail()
  window.addEventListener('resize', () => {
    chartInstance?.resize()
  })
})
</script>

<style scoped>
.firing-detail {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h2 {
  font-size: 22px;
  color: #303133;
}

.info-card {
  margin-bottom: 20px;
}

.info-item {
  padding: 10px 0;
}

.info-item .label {
  color: #909399;
  margin-right: 8px;
}

.info-item .value {
  font-weight: 500;
  color: #303133;
}

.detail-tabs {
  margin-top: 20px;
}

.chart-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.legend-info {
  display: flex;
  gap: 20px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
}

.legend-color {
  width: 16px;
  height: 16px;
  border-radius: 50%;
}

.chart-container {
  width: 100%;
  height: 500px;
}
</style>
