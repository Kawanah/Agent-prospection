import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL } from '../config';

const TOKEN_KEY = 'kawanah_token';

// Hors du hook pour éviter l'appel de Date.now() pendant le render
function isTokenValid(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

// ── Intercepteur global Axios ─────────────────────────────────────────────────
// Ajoute le token JWT à chaque requête sortante
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirige vers /login si le backend renvoie 401
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      // Forcer le rechargement pour afficher la page login
      window.dispatchEvent(new Event('kawanah:logout'));
    }
    return Promise.reject(error);
  }
);

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useAuth() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));

  useEffect(() => {
    const handleLogout = () => setToken(null);
    window.addEventListener('kawanah:logout', handleLogout);
    return () => window.removeEventListener('kawanah:logout', handleLogout);
  }, []);

  const login = (newToken) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  };

  return {
    token,
    isAuthenticated: !!token && isTokenValid(token),
    login,
    logout,
  };
}
