import { api } from '../lib/api';

export const campaignsApi = {
  list: (params) => api.get('/api/campaigns/', { params }),
  create: (data) => api.post('/api/campaigns/', data),
  update: (campaignId, data) => api.patch(`/api/campaigns/${campaignId}`, data),
  delete: (campaignId) => api.delete(`/api/campaigns/${campaignId}`),
  start: (campaignId) => api.post(`/api/campaigns/${campaignId}/start`),
  pause: (campaignId) => api.post(`/api/campaigns/${campaignId}/pause`),
  queueStats: () => api.get('/api/campaigns/queue-stats'),
  processQueue: () => api.post('/api/campaigns/process-queue'),
  previewLeads: (campaignId, params) =>
    api.get(`/api/campaigns/${campaignId}/preview-leads`, { params }),
  addLeads: (campaignId, leadIds) =>
    api.post(`/api/campaigns/${campaignId}/add-leads`, { lead_ids: leadIds }),
  removeLead: (campaignId, leadId) => api.delete(`/api/campaigns/${campaignId}/leads/${leadId}`),
};
