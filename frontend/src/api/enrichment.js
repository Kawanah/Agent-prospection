import { api } from '../lib/api';

export const enrichmentApi = {
  stats: () => api.get('/api/enrichment/stats'),
  job: (jobId) => api.get(`/api/enrichment/job/${jobId}`),
  batch: (params) => api.post('/api/enrichment/batch', null, { params }),
  single: (leadId) => api.post(`/api/enrichment/${leadId}`),
};
