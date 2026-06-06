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
      <el-tab-pane name="chart">
        <template #label>
          <span>五段温压曲线</span>
          <el-badge v-if="openOrdersCount > 0" :value="openOrdersCount" class="tab-badge" :max="99" />
        </template>
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
              <span class="legend-item">
                <span class="legend-color" style="background: rgba(255, 193, 7, 0.3); border: 1px dashed #ff9800;"></span>
                塌陷事件
              </span>
              <span class="legend-item">
                <span class="legend-color" style="background: #2196f3; width: 2px;"></span>
                计划到温
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

      <el-tab-pane name="events">
        <template #label>
          <span>烟道塌陷事件</span>
          <el-badge v-if="flueEventsCount > 0" :value="flueEventsCount" class="tab-badge" type="warning" :max="99" />
        </template>
        <el-card>
          <el-alert 
            v-if="firing?.flue_events?.length > 0"
            type="warning" 
            :title="`检测到 ${firing.flue_events.length} 次烟道塌陷异常`"
            show-icon
            style="margin-bottom: 15px;"
          />
          <el-table 
            :data="firing?.flue_events || []" 
            stripe 
            ref="eventsTableRef"
            highlight-current-row
            @row-click="onEventRowClick"
          >
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
                <el-link v-if="row.work_order_id" type="primary" @click.stop="goToOrder(row.work_order_id)">
                  #{{ row.work_order_id }}
                </el-link>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="orders">
        <template #label>
          <span>工单</span>
          <el-badge v-if="openOrdersCount > 0" :value="openOrdersCount" class="tab-badge" type="danger" :max="99" />
        </template>
        <el-card>
          <el-table :data="firing?.orders || []" stripe>
            <el-table-column prop="id" label="工单号" width="100">
              <template #default="{ row }">
                <el-link type="primary" @click="goToOrder(row.id)">#{{ row.id }}</el-link>
              </template>
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
import { ref, reactive, onMounted, watch, nextTick, computed } from 'vue'
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
const eventsTableRef = ref(null)
let chartInstance = null
let highlightTimer = null

const highlightedEventId = ref(null)
const highlightedSegment = ref(null)

const addBatchVisible = ref(false)
const batchForm = reactive({
  batch_code: '',
  color_grade: 3,
  warpage_mm: 2.0
})

const segmentColors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db']

const openOrdersCount = computed(() => {
  if (!firing.value?.orders) return 0
  return firing.value.orders.filter(o => o.status !== 'closed').length
})

const flueEventsCount = computed(() => {
  return firing.value?.flue_events?.length || 0
})

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

const buildFlueEventMarkAreas = () => {
  if (!firing.value?.flue_events) return []
  
  const markAreas = []
  const segments = firing.value.segments || []
  
  firing.value.flue_events.forEach((event, eventIdx) => {
    const segIdx = event.segment - 1
    if (segIdx >= 0 && segIdx < segments.length) {
      const startTime = dayjs(event.start_time).toDate()
      const endTime = dayjs(event.start_time).add(event.duration_minutes, 'minute').toDate()
      
      const segData = segments[segIdx].timestamps.map((t, i) => {
        const val = chartType.value === 'temp' ? segments[segIdx].temperatures[i] : segments[segIdx].pressures[i]
        return [dayjs(t).toDate(), Number(val)]
      })
      
      const segMin = Math.min(...segData.map(d => d[1]))
      const segMax = Math.max(...segData.map(d => d[1]))
      
      markAreas.push({
        name: `烟道塌陷-${eventIdx}`,
        silent: false,
        itemStyle: {
          color: 'rgba(255, 193, 7, 0.25)',
          borderColor: '#ff9800',
          borderWidth: 1,
          borderType: 'dashed'
        },
        data: [
          [
            {
              xAxis: startTime,
              yAxis: segMin - (segMax - segMin) * 0.1
            },
            {
              xAxis: endTime,
              yAxis: segMax + (segMax - segMin) * 0.1
            }
          ]
        ]
      })
    }
  })
  
  return markAreas
}

const buildPlanTempMarkLine = () => {
  if (!firing.value?.plan_temp_time) return []
  
  return {
    silent: true,
    symbol: 'none',
    lineStyle: {
      color: '#2196f3',
      width: 2,
      type: 'solid'
    },
    label: {
      show: true,
      formatter: '计划到温',
      position: 'end',
      color: '#2196f3',
      fontSize: 12
    },
    data: [
      {
        xAxis: dayjs(firing.value.plan_temp_time).toDate()
      }
    ]
  }
}

const initChart = (zoomRange = null) => {
  if (!chartRef.value || !firing.value) return
  
  if (chartInstance) {
    chartInstance.off('click')
    chartInstance.dispose()
  }
  
  chartInstance = echarts.init(chartRef.value)
  
  const series = []
  const segments = firing.value.segments || []
  const flueEvents = firing.value.flue_events || []
  
  segments.forEach((seg, idx) => {
    const data = seg.timestamps.map((t, i) => {
      const val = chartType.value === 'temp' ? seg.temperatures[i] : seg.pressures[i]
      return [dayjs(t).toDate(), Number(val)]
    })
    
    const isHighlighted = highlightedSegment.value === seg.segment
    
    series.push({
      name: `第${seg.segment}段`,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: isHighlighted ? 8 : 4,
      lineStyle: { 
        width: isHighlighted ? 5 : 2,
        shadowBlur: isHighlighted ? 20 : 0,
        shadowColor: isHighlighted ? segmentColors[idx] : 'transparent'
      },
      itemStyle: { 
        color: segmentColors[idx]
      },
      data: data,
      markArea: idx === 0 ? buildFlueEventMarkAreas() : undefined,
      markLine: idx === 0 ? buildPlanTempMarkLine() : undefined,
      z: isHighlighted ? 10 : 2
    })
  })
  
  const dataZoomConfig = zoomRange ? [
    { type: 'inside', start: zoomRange.start, end: zoomRange.end },
    { start: zoomRange.start, end: zoomRange.end, bottom: 20 }
  ] : [
    { type: 'inside', start: 0, end: 100 },
    { start: 0, end: 100, bottom: 20 }
  ]
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let html = dayjs(params[0].axisValue).format('YYYY-MM-DD HH:mm') + '<br/>'
        params.forEach(p => {
          if (p.componentType === 'series') {
            html += `${p.marker} ${p.seriesName}: ${p.data[1].toFixed(1)} ${chartType.value === 'temp' ? '°C' : 'Pa'}<br/>`
          }
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
    dataZoom: dataZoomConfig,
    series: series
  }
  
  chartInstance.setOption(option)
  
  chartInstance.on('click', (params) => {
    if (params.componentType === 'markArea') {
      const eventName = params.name
      if (eventName?.startsWith('烟道塌陷-')) {
        const eventIdx = parseInt(eventName.split('-')[1])
        if (!isNaN(eventIdx) && flueEvents[eventIdx]) {
          jumpToEvent(eventIdx)
        }
      }
    }
  })
  
  chartInstance.on('dataZoom', () => {
    if (highlightedSegment.value !== null) {
      highlightedSegment.value = null
      nextTick(() => initChart())
    }
  })
}

const jumpToEvent = (eventIdx) => {
  highlightedEventId.value = eventIdx
  activeTab.value = 'events'
  nextTick(() => {
    if (eventsTableRef.value) {
      eventsTableRef.value.setCurrentRow(firing.value.flue_events[eventIdx])
    }
  })
}

const onEventRowClick = (row) => {
  const eventIdx = firing.value.flue_events.findIndex(e => e === row)
  if (eventIdx === -1) return
  
  const startTime = dayjs(row.start_time)
  const endTime = startTime.add(row.duration_minutes, 'minute')
  
  const segments = firing.value.segments || []
  if (segments.length === 0) return
  
  const allTimestamps = []
  segments.forEach(seg => {
    seg.timestamps.forEach(t => allTimestamps.push(dayjs(t).toDate()))
  })
  
  if (allTimestamps.length === 0) return
  
  const minTime = Math.min(...allTimestamps.map(t => t.getTime()))
  const maxTime = Math.max(...allTimestamps.map(t => t.getTime()))
  const totalRange = maxTime - minTime
  
  const zoomStartTime = startTime.subtract(15, 'minute').toDate().getTime()
  const zoomEndTime = endTime.add(15, 'minute').toDate().getTime()
  
  const start = Math.max(0, ((zoomStartTime - minTime) / totalRange) * 100)
  const end = Math.min(100, ((zoomEndTime - minTime) / totalRange) * 100)
  
  highlightedSegment.value = row.segment
  activeTab.value = 'chart'
  
  nextTick(() => {
    initChart({ start, end })
    
    if (highlightTimer) {
      clearTimeout(highlightTimer)
    }
    highlightTimer = setTimeout(() => {
      highlightedSegment.value = null
      nextTick(() => initChart({ start, end }))
    }, 3000)
  })
}

const goToOrder = (orderId) => {
  router.push(`/orders?firingId=${firing.value.id}&orderId=${orderId}`)
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
  highlightedSegment.value = null
  nextTick(() => initChart())
})

watch(activeTab, (newTab) => {
  if (newTab === 'chart') {
    highlightedEventId.value = null
    nextTick(() => initChart())
  } else if (newTab === 'events') {
    if (highlightTimer) {
      clearTimeout(highlightTimer)
      highlightTimer = null
    }
    highlightedSegment.value = null
  }
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

.detail-tabs :deep(.el-tabs__item) {
  position: relative;
}

.tab-badge {
  margin-left: 6px;
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
  flex-wrap: wrap;
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

.detail-tabs :deep(.el-table__row.current-row) {
  background-color: #fff7e6 !important;
}

.detail-tabs :deep(.el-table__row.current-row > td) {
  background-color: #fff7e6 !important;
}
</style>
