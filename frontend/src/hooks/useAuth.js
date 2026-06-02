import { useState, useEffect } from 'react';

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
    sessionStorage.removeItem('agent_messages');
    setToken(null);
  };

  return {
    token,
    isAuthenticated: !!token && isTokenValid(token),
    login,
    logout,
  };
}
