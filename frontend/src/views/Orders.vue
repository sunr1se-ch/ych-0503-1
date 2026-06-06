<template>
  <div class="orders-page">
    <div class="page-header">
      <h2><el-icon><Warning /></el-icon> 工单待办</h2>
      <div class="header-actions">
        <el-tag v-if="filterFiringId" closable @close="clearFiringFilter" type="primary" effect="light" style="margin-right: 10px;">
          窑次 #{{ filterFiringId }}
          <el-icon><Close /></el-icon>
        </el-tag>
        <el-select v-model="filterStatus" placeholder="按状态筛选" style="width: 140px; margin-right: 10px;">
          <el-option label="全部" value="" />
          <el-option label="待处理" value="open" />
          <el-option label="处理中" value="in_progress" />
          <el-option label="已关闭" value="closed" />
        </el-select>
        <el-button type="warning" @click="manualScan" :icon="Refresh">
          手动扫描烟道
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="8">
        <el-card class="stat-card open">
          <div class="stat-content">
            <el-icon :size="32"><Clock /></el-icon>
            <div class="stat-info">
              <div class="stat-value">{{ stats.open }}</div>
              <div class="stat-label">待处理</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card in-progress">
          <div class="stat-content">
            <el-icon :size="32"><Loading /></el-icon>
            <div class="stat-info">
              <div class="stat-value">{{ stats.inProgress }}</div>
              <div class="stat-label">处理中</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card closed">
          <div class="stat-content">
            <el-icon :size="32"><CircleCheck /></el-icon>
            <div class="stat-info">
              <div class="stat-value">{{ stats.closed }}</div>
              <div class="stat-label">已关闭</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <el-table 
        :data="filteredOrders" 
        v-loading="loading" 
        stripe 
        ref="ordersTableRef"
        highlight-current-row
      >
        <el-table-column prop="id" label="工单号" width="90">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column label="窑道" width="120">
          <template #default="{ row }">
            <router-link :to="`/firing/${row.firing_id}`">
              <el-tag type="primary" effect="plain">窑次 #{{ row.firing_id }}</el-tag>
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="order_type" label="类型" width="130">
          <template #default="{ row }">
            <el-tag :type="row.order_type === 'flue_collapse' ? 'danger' : 'warning'" effect="dark">
              <el-icon v-if="row.order_type === 'flue_collapse'"><Warning /></el-icon>
              <el-icon v-else><Tools /></el-icon>
              {{ row.order_type === 'flue_collapse' ? '烟道塌陷' : '返工' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="segment" label="段位" width="100">
          <template #default="{ row }">
            <span v-if="row.segment">第{{ row.segment }}段</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="280" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="orderStatusType(row.status)">
              {{ orderStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测时间" width="170">
          <template #default="{ row }">{{ formatTime(row.detected_at) }}</template>
        </el-table-column>
        <el-table-column label="关闭时间" width="170">
          <template #default="{ row }">
            {{ row.closed_at ? formatTime(row.closed_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status !== 'closed'"
              type="primary" 
              size="small" 
              @click="updateStatus(row, 'in_progress')"
              :disabled="row.status === 'in_progress'"
            >
              开始处理
            </el-button>
            <el-button 
              v-if="row.status !== 'closed'"
              type="success" 
              size="small" 
              @click="showCloseDialog(row)"
            >
              关闭
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="closeDialogVisible" title="关闭工单" width="450px">
      <el-form :model="closeForm" label-width="80px">
        <el-form-item label="处理人">
          <el-input v-model="closeForm.closed_by" placeholder="请输入处理人姓名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmClose" :loading="submitting">确认关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { orderApi, scanApi } from '../api'
import dayjs from 'dayjs'

const route = useRoute()

const loading = ref(false)
const submitting = ref(false)
const orders = ref([])
const filterStatus = ref('')
const filterFiringId = ref(null)
const filterOrderId = ref(null)
const ordersTableRef = ref(null)
const closeDialogVisible = ref(false)
const currentOrder = ref(null)
const closeForm = reactive({
  closed_by: ''
})

const filteredOrders = computed(() => {
  let result = [...orders.value]
  
  if (filterStatus.value) {
    result = result.filter(o => o.status === filterStatus.value)
  }
  
  if (filterFiringId.value) {
    result = result.filter(o => o.firing_id === Number(filterFiringId.value))
  }
  
  return result
})

const stats = computed(() => ({
  open: filteredOrders.value.filter(o => o.status === 'open').length,
  inProgress: filteredOrders.value.filter(o => o.status === 'in_progress').length,
  closed: filteredOrders.value.filter(o => o.status === 'closed').length
}))

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

const loadOrders = async () => {
  loading.value = true
  try {
    const res = await orderApi.list(filterStatus.value || undefined)
    orders.value = res.data
    nextTick(() => {
      locateTargetOrder()
    })
  } catch (e) {
    ElMessage.error('加载工单列表失败')
  } finally {
    loading.value = false
  }
}

const clearFiringFilter = () => {
  filterFiringId.value = null
  filterOrderId.value = null
}

const locateTargetOrder = () => {
  if (!filterOrderId.value || !ordersTableRef.value) return
  
  const targetOrder = filteredOrders.value.find(o => o.id === Number(filterOrderId.value))
  if (targetOrder) {
    ordersTableRef.value.setCurrentRow(targetOrder)
    ordersTableRef.value.scrollToRow(targetOrder)
  }
}

const updateStatus = async (order, status) => {
  try {
    await orderApi.update(order.id, { status })
    ElMessage.success('状态更新成功')
    loadOrders()
  } catch (e) {
    ElMessage.error('更新失败：' + (e.response?.data?.detail || e.message))
  }
}

const showCloseDialog = (order) => {
  currentOrder.value = order
  closeForm.closed_by = ''
  closeDialogVisible.value = true
}

const confirmClose = async () => {
  if (!closeForm.closed_by) {
    ElMessage.warning('请输入处理人姓名')
    return
  }
  
  submitting.value = true
  try {
    await orderApi.update(currentOrder.value.id, {
      status: 'closed',
      closed_by: closeForm.closed_by
    })
    ElMessage.success('工单已关闭')
    closeDialogVisible.value = false
    loadOrders()
  } catch (e) {
    ElMessage.error('关闭失败：' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

const manualScan = async () => {
  try {
    const res = await scanApi.scanFlue()
    const count = res.data.detected_events
    if (count > 0) {
      ElMessage.warning(`扫描发现 ${count} 个烟道塌陷事件`)
    } else {
      ElMessage.success('未检测到烟道塌陷异常')
    }
    loadOrders()
  } catch (e) {
    ElMessage.error('扫描失败：' + (e.response?.data?.detail || e.message))
  }
}

watch(filterStatus, () => {
  loadOrders()
})

watch(filteredOrders, () => {
  nextTick(() => {
    locateTargetOrder()
  })
})

onMounted(() => {
  if (route.query.firingId) {
    filterFiringId.value = route.query.firingId
    filterStatus.value = ''
  }
  if (route.query.orderId) {
    filterOrderId.value = route.query.orderId
  }
  loadOrders()
})
</script>

<style scoped>
.orders-page {
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

.stat-card {
  border-radius: 8px;
  overflow: hidden;
}

.stat-card.open {
  border-left: 4px solid #f56c6c;
}

.stat-card.in-progress {
  border-left: 4px solid #e6a23c;
}

.stat-card.closed {
  border-left: 4px solid #67c23a;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-content :deep(.el-icon) {
  color: #909399;
}

.stat-info .stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  line-height: 1.2;
}

.stat-info .stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

:deep(.el-table__row.current-row) {
  background-color: #ecf5ff !important;
}

:deep(.el-table__row.current-row > td) {
  background-color: #ecf5ff !important;
}

.filter-tag {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
