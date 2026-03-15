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
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
