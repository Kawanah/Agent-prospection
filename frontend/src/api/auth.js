import { api } from '../lib/api';

export const authApi = {
  login: (form) =>
    api.post('/api/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
};
