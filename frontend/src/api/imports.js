import { api } from '../lib/api';

export const importsApi = {
  source: (url, payload) => api.post(url, payload),
  googlePlaces: (payload) => api.post('/api/sources/google-places/import', payload),
  sirene: (payload) => api.post('/api/sources/sirene/import', payload),
  pappers: (payload) => api.post('/api/sources/pappers/import', payload),
  gouvJobs: () => api.get('/api/gouv/jobs'),
  createGouvJob: (payload) => api.post('/api/gouv/jobs', payload),
  startGouvJob: (jobId) => api.post(`/api/gouv/jobs/${jobId}/start`),
  pauseGouvJob: (jobId) => api.post(`/api/gouv/jobs/${jobId}/pause`),
};
