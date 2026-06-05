import { api } from '../lib/api';

export const messagesApi = {
  list: (params) => api.get('/api/messages/', { params }),
  create: (data) => api.post('/api/messages/', data),
  update: (messageId, data) => api.patch(`/api/messages/${messageId}`, data),
  queue: (messageId) => api.post(`/api/messages/${messageId}/queue`),
  sendTest: (messageId, toEmail) =>
    api.post(`/api/messages/${messageId}/send-test`, { to_email: toEmail }),
  generate: (leadId, data) => api.post(`/api/ai/generate/${leadId}`, data),
};
