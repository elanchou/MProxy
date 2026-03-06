import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export default {
  getSubs: () => api.get('/subscriptions'),
  createSub: (data) => api.post('/subscriptions', data),
  updateSub: (id, data) => api.put(`/subscriptions/${id}`, data),
  deleteSub: (id) => api.delete(`/subscriptions/${id}`),
  refreshSub: (id) => api.post(`/subscriptions/${id}/refresh`),
  getNodes: (subId) => api.get('/nodes', { params: subId ? { subscription_id: subId } : {} }),
  toggleNode: (id, enabled) => api.patch(`/nodes/${id}`, { enabled }),
  proxyStatus: () => api.get('/proxy/status'),
  proxyStart: () => api.post('/proxy/start'),
  proxyStop: () => api.post('/proxy/stop'),
  proxyRestart: () => api.post('/proxy/restart'),
}
