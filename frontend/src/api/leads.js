import { api, buildUrl } from '../lib/api';

export const leadsApi = {
  list: (params) => api.get('/api/leads/', { params }),
  stats: () => api.get('/api/leads/stats'),
  batches: () => api.get('/api/leads/batches'),
  names: (ids) => api.get('/api/leads/names', { params: { ids } }),
  campaignStatus: (ids) => api.get('/api/leads/campaign-status', { params: { ids } }),
  strongArguments: (leadId) => api.get(`/api/leads/${leadId}/strong-arguments`),
  updateNotes: (leadId, notes) => api.patch(`/api/leads/${leadId}/notes`, { notes }),
  updateWebsiteReview: (leadId, checklist) =>
    api.patch(`/api/leads/${leadId}/website-review`, { checklist }),
  updateWebsiteMatch: (leadId, payload) => api.patch(`/api/leads/${leadId}/website-match`, payload),
  upload: (formData, config) => api.post('/api/leads/upload', formData, config),
  delete: (leadId) => api.delete(`/api/leads/${leadId}`),
  exportUrl: (params) => buildUrl('/api/leads/export', params),
};
