import { api } from '../lib/api';

export const agentApi = {
  chat: (payload) => api.post('/api/agent/chat', payload),
  respond: (payload) => api.post('/api/agent/respond', payload),
  resetSession: (sessionId) => api.delete(`/api/agent/session/${sessionId}`),
};
