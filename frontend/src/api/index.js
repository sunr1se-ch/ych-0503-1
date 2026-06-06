import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

export const firingApi = {
  list: () => api.get('/firings'),
  get: (id) => api.get(`/firings/${id}`),
  create: (data) => api.post('/firings', data),
  update: (id, data) => api.put(`/firings/${id}`, data),
  getReadings: (id, segment) => api.get(`/firings/${id}/readings`, { params: { segment } })
}

export const batchApi = {
  list: (firingId) => api.get('/batches', { params: { firing_id: firingId } }),
  get: (id) => api.get(`/batches/${id}`),
  create: (data) => api.post('/batches', data),
  update: (id, data) => api.put(`/batches/${id}`, data)
}

export const orderApi = {
  list: (status) => api.get('/orders', { params: { status } }),
  get: (id) => api.get(`/orders/${id}`),
  create: (data) => api.post('/orders', data),
  update: (id, data) => api.put(`/orders/${id}`, data)
}

export const loadingApi = {
  list: () => api.get('/loading'),
  create: (data) => api.post('/loading', data)
}

export const readingApi = {
  create: (data) => api.post('/readings', data)
}

export const scanApi = {
  scanFlue: () => api.post('/scan-flue-collapse')
}

export default api
