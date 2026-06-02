import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Leads from './pages/Leads';
import Campaigns from './pages/Campaigns';
import Import from './pages/Import';
import Enrichment from './pages/Enrichment';
import Messages from './pages/Messages';
import Agent from './pages/Agent';
import Settings from './pages/Settings';
import { useAuth } from './hooks/useAuth';

export default function App() {
  const { isAuthenticated, login, logout } = useAuth();

  if (!isAuthenticated) {
    return <Login onLogin={login} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout onLogout={logout} />}>
          <Route
            index
            element={
              <ErrorBoundary>
                <Dashboard />
              </ErrorBoundary>
            }
          />
          <Route
            path="leads"
            element={
              <ErrorBoundary>
                <Leads />
              </ErrorBoundary>
            }
          />
          <Route
            path="campaigns"
            element={
              <ErrorBoundary>
                <Campaigns />
              </ErrorBoundary>
            }
          />
          <Route
            path="import"
            element={
              <ErrorBoundary>
                <Import />
              </ErrorBoundary>
            }
          />
          <Route
            path="enrichment"
            element={
              <ErrorBoundary>
                <Enrichment />
              </ErrorBoundary>
            }
          />
          <Route
            path="messages"
            element={
              <ErrorBoundary>
                <Messages />
              </ErrorBoundary>
            }
          />
          <Route
            path="agent"
            element={
              <ErrorBoundary>
                <Agent />
              </ErrorBoundary>
            }
          />
          <Route
            path="settings"
            element={
              <ErrorBoundary>
                <Settings />
              </ErrorBoundary>
            }
          />
          <Route
            path="*"
            element={
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <p className="text-6xl font-bold text-primary-200 mb-4">404</p>
                <p className="text-lg font-semibold text-primary-700 mb-2">Page introuvable</p>
                <p className="text-sm text-primary-400 mb-6">
                  Cette page n'existe pas ou a été déplacée.
                </p>
                <a
                  href="/"
                  className="px-4 py-2 rounded-xl bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 transition-colors"
                >
                  Retour au dashboard
                </a>
              </div>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
