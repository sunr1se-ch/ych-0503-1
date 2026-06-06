<template>
  <div class="firing-list">
    <div class="page-header">
      <h2><el-icon><List /></el-icon> 窑次列表</h2>
      <el-button type="primary" @click="showAddDialog" :icon="Plus">新建窑次</el-button>
    </div>

    <el-card class="stats-card">
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">窑次总数</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item firing">
            <div class="stat-value">{{ stats.firing }}</div>
            <div class="stat-label">烧制中</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item warning">
            <div class="stat-value">{{ stats.withOpenOrders }}</div>
            <div class="stat-label">有待处理工单</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item success">
            <div class="stat-value">{{ stats.completed }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="table-card">
      <el-table :data="firings" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="kiln_number" label="窑道编号" width="120">
          <template #default="{ row }">
            <el-tag type="primary" effect="plain">{{ row.kiln_number }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="计划到温时间" width="200">
          <template #default="{ row }">
            <el-icon><Clock /></el-icon> {{ formatTime(row.plan_temp_time) }}
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="200">
          <template #default="{ row }">
            {{ row.start_time ? formatTime(row.start_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="异常状态" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.has_open_orders" type="danger" effect="dark">
              <el-icon><Warning /></el-icon> 工单待处理
            </el-tag>
            <el-tag v-else type="success" effect="plain">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetail(row.id)" :icon="View">
              详情
            </el-button>
            <el-button 
              type="danger" 
              size="small" 
              v-if="row.has_open_orders"
              @click="goToOrders(row.id)"
              :icon="Warning"
            >
              工单
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="新建窑次" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="窑道编号">
          <el-input v-model="form.kiln_number" placeholder="例如：K-006" />
        </el-form-item>
        <el-form-item label="计划到温时间">
          <el-date-picker
            v-model="form.plan_temp_time"
            type="datetime"
            placeholder="选择日期时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="装窑中" value="loading" />
            <el-option label="烧制中" value="firing" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createFiring" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { firingApi } from '../api'
import dayjs from 'dayjs'

const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const firings = ref([])
const addDialogVisible = ref(false)
const form = reactive({
  kiln_number: '',
  plan_temp_time: null,
  status: 'loading'
})

const stats = computed(() => ({
  total: firings.value.length,
  firing: firings.value.filter(f => f.status === 'firing').length,
  completed: firings.value.filter(f => f.status === 'completed').length,
  withOpenOrders: firings.value.filter(f => f.has_open_orders).length
}))

const statusType = (status) => {
  const map = {
    loading: 'info',
    firing: 'warning',
    cooling: 'primary',
    completed: 'success'
  }
  return map[status] || 'info'
}

const statusText = (status) => {
  const map = {
    loading: '装窑中',
    firing: '烧制中',
    cooling: '冷却中',
    completed: '已完成'
  }
  return map[status] || status
}

const formatTime = (time) => {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

const loadFirings = async () => {
  loading.value = true
  try {
    const res = await firingApi.list()
    firings.value = res.data
  } catch (e) {
    ElMessage.error('加载窑次列表失败')
  } finally {
    loading.value = false
  }
}

const showAddDialog = () => {
  form.kiln_number = ''
  form.plan_temp_time = null
  form.status = 'loading'
  addDialogVisible.value = true
}

const createFiring = async () => {
  if (!form.kiln_number || !form.plan_temp_time) {
    ElMessage.warning('请填写完整信息')
    return
  }
  
  submitting.value = true
  try {
    await firingApi.create({
      ...form,
      plan_temp_time: dayjs(form.plan_temp_time).toISOString()
    })
    ElMessage.success('窑次创建成功')
    addDialogVisible.value = false
    loadFirings()
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

const viewDetail = (id) => {
  router.push(`/firing/${id}`)
}

const goToOrders = (firingId) => {
  router.push(`/orders?firingId=${firingId}`)
}

onMounted(() => {
  loadFirings()
})
</script>

<style scoped>
.firing-list {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  color: #303133;
}

.stats-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 15px;
  border-radius: 8px;
  background: #f8f9fa;
}

.stat-item.firing {
  background: #fff7e6;
}

.stat-item.warning {
  background: #fff1f0;
}

.stat-item.success {
  background: #f6ffed;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.table-card {
  background: white;
  border-radius: 8px;
}
</style>
