<template>
  <div class="loading-page">
    <div class="page-header">
      <h2><el-icon><Van /></el-icon> 装车操作</h2>
    </div>

    <el-alert
      title="装车规则：工单未关闭前，该窑次关联批次不得装车出库"
      type="warning"
      show-icon
      style="margin-bottom: 20px;"
    />

    <el-row :gutter="24">
      <el-col :span="10">
        <el-card class="loading-form-card">
          <template #header>
            <div class="card-header">
              <el-icon><Edit /></el-icon>
              装车登记
            </div>
          </template>
          
          <el-form :model="form" label-width="100px">
            <el-form-item label="选择批次">
              <el-select 
                v-model="form.batch_id" 
                placeholder="请选择批次"
                style="width: 100%"
                filterable
                @change="onBatchChange"
              >
                <el-option 
                  v-for="batch in availableBatches" 
                  :key="batch.id" 
                  :label="`${batch.batch_code} - ${batch.color_grade}级`"
                  :value="batch.id"
                  :disabled="!batch.can_load"
                >
                  <div class="batch-option">
                    <span>{{ batch.batch_code }}</span>
                    <el-tag :type="batch.can_load ? 'success' : 'danger'" size="small">
                      {{ batch.can_load ? '可装车' : '禁止装车' }}
                    </el-tag>
                  </div>
                </el-option>
              </el-select>
              <div v-if="selectedBatch && !selectedBatch.can_load" class="batch-warning">
                <el-icon><Warning /></el-icon>
                {{ loadingBlockedReason }}
              </div>
            </el-form-item>

            <el-form-item v-if="selectedBatch" label="窑道编号">
              <el-tag type="primary">窑次 #{{ selectedBatch.firing_id }}</el-tag>
            </el-form-item>

            <el-form-item v-if="selectedBatch" label="品级">
              <el-tag :type="gradeType(selectedBatch.color_grade)" effect="dark">
                {{ selectedBatch.color_grade }} 级
              </el-tag>
            </el-form-item>

            <el-form-item v-if="selectedBatch" label="翘曲">
              {{ selectedBatch.warpage_mm }} mm
            </el-form-item>

            <el-form-item label="车牌号">
              <el-input v-model="form.vehicle_plate" placeholder="例如：京A12345" />
            </el-form-item>

            <el-form-item label="操作员">
              <el-input v-model="form.operator" placeholder="请输入操作员姓名" />
            </el-form-item>

            <el-form-item label="数量">
              <el-input-number v-model="form.quantity" :min="1" :max="10000" style="width: 100%" />
            </el-form-item>

            <el-form-item label="备注">
              <el-input 
                v-model="form.remarks" 
                type="textarea" 
                :rows="3"
                placeholder="可选"
              />
            </el-form-item>

            <el-form-item>
              <el-button 
                type="primary" 
                @click="submitLoading" 
                :loading="submitting"
                :disabled="!canSubmit"
                :icon="Check"
                style="width: 100%;"
              >
                确认装车
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><List /></el-icon>
              装车记录
              <el-tag type="success" style="margin-left: 10px;">
                共 {{ loadingRecords.length }} 条
              </el-tag>
            </div>
          </template>
          
          <el-table :data="loadingRecords" v-loading="loading" stripe max-height="600">
            <el-table-column prop="id" label="记录ID" width="80" />
            <el-table-column label="批次编号" width="150">
              <template #default="{ row }">
                <el-tag type="primary">{{ getBatchCode(row.batch_id) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="vehicle_plate" label="车牌号" width="120" />
            <el-table-column prop="operator" label="操作员" width="120" />
            <el-table-column prop="quantity" label="数量" width="100" />
            <el-table-column prop="remarks" label="备注" min-width="150" show-overflow-tooltip />
            <el-table-column label="装车时间" width="170">
              <template #default="{ row }">{{ formatTime(row.loading_time) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { batchApi, loadingApi } from '../api'
import dayjs from 'dayjs'

const loading = ref(false)
const submitting = ref(false)
const batches = ref([])
const loadingRecords = ref([])

const form = reactive({
  batch_id: null,
  vehicle_plate: '',
  operator: '',
  quantity: 1,
  remarks: ''
})

const availableBatches = computed(() => {
  return batches.value.filter(b => b.status !== 'loaded' && b.status !== 'shipped')
})

const selectedBatch = computed(() => {
  return batches.value.find(b => b.id === form.batch_id)
})

const loadingBlockedReason = computed(() => {
  if (!selectedBatch.value) return ''
  if (selectedBatch.value.status === 'rework_pending') {
    return '该批次需要返工'
  }
  if (!selectedBatch.value.can_load) {
    return '该窑次存在未关闭工单，请先处理工单'
  }
  return ''
})

const canSubmit = computed(() => {
  if (!form.batch_id || !form.vehicle_plate || !form.operator || form.quantity <= 0) {
    return false
  }
  const batch = selectedBatch.value
  if (!batch) return false
  return batch.can_load
})

const gradeType = (grade) => {
  if (grade >= 4) return 'success'
  if (grade === 3) return 'warning'
  return 'danger'
}

const formatTime = (time) => {
  return time ? dayjs(time).format('YYYY-MM-DD HH:mm:ss') : '-'
}

const getBatchCode = (batchId) => {
  const batch = batches.value.find(b => b.id === batchId)
  return batch ? batch.batch_code : `#${batchId}`
}

const loadBatches = async () => {
  try {
    const res = await batchApi.list()
    batches.value = res.data
  } catch (e) {
    ElMessage.error('加载批次列表失败')
  }
}

const loadRecords = async () => {
  loading.value = true
  try {
    const res = await loadingApi.list()
    loadingRecords.value = res.data
  } catch (e) {
    ElMessage.error('加载装车记录失败')
  } finally {
    loading.value = false
  }
}

const onBatchChange = () => {
}

const submitLoading = async () => {
  if (!canSubmit.value) {
    ElMessage.warning('请填写完整信息且批次可装车')
    return
  }
  
  submitting.value = true
  try {
    await loadingApi.create(form)
    ElMessage.success('装车登记成功')
    form.batch_id = null
    form.vehicle_plate = ''
    form.operator = ''
    form.quantity = 1
    form.remarks = ''
    loadBatches()
    loadRecords()
  } catch (e) {
    ElMessage.error('装车失败：' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadBatches()
  loadRecords()
})
</script>

<style scoped>
.loading-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  color: #303133;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.batch-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.batch-warning {
  margin-top: 8px;
  padding: 10px;
  background: #fef0f0;
  border-radius: 4px;
  color: #f56c6c;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.loading-form-card {
  position: sticky;
  top: 0;
}
</style>
