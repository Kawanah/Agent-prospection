import axios from 'axios';
import { API_URL } from '../config';

const TOKEN_KEY = 'kawanah_token';

export const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem('agent_messages');
      window.dispatchEvent(new Event('kawanah:logout'));
    }
    return Promise.reject(error);
  }
);

export function getErrorMessage(error, fallback = 'Une erreur est survenue') {
  return error.response?.data?.detail || error.message || fallback;
}

export function buildUrl(path, params = {}) {
  const url = new URL(path, API_URL);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}
