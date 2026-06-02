import { api } from '../lib/api';

export const settingsApi = {
  get: () => api.get('/api/settings/'),
  save: (payload) => api.put('/api/settings/', payload),
  sendTestEmail: (toEmail) => api.post('/api/settings/test-email', { to_email: toEmail }),
};
