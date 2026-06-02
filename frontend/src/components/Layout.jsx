import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Users,
  FolderKanban,
  Upload,
  Sparkles,
  Mail,
  Bot,
  Settings,
  ChevronLeft,
  ChevronRight,
  Target,
  LogOut,
} from 'lucide-react';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/leads', icon: Users, label: 'Leads' },
  { path: '/campaigns', icon: FolderKanban, label: 'Campagnes' },
  { path: '/import', icon: Upload, label: 'Import' },
  { path: '/enrichment', icon: Sparkles, label: 'Enrichissement' },
  { path: '/messages', icon: Mail, label: 'Messages' },
  { path: '/agent', icon: Bot, label: 'Agent' },
];

export default function Layout({ onLogout }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-primary-50">
      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 80 : 280 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        className="relative flex flex-col bg-primary-900 text-white shadow-2xl"
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-6 border-b border-white/10">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-accent-500 shadow-glow">
            <Target className="w-5 h-5 text-white" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
              >
                <h1 className="text-xl font-display font-bold tracking-tight">Kawanah Tourisme</h1>
                <p className="text-xs text-primary-400">Agent Prospection</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group
                ${
                  isActive
                    ? 'bg-accent-500/20 text-accent-400 shadow-lg shadow-accent-500/10'
                    : 'text-primary-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    className="font-medium"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </NavLink>
          ))}
        </nav>

        {/* Settings */}
        <div className="px-3 py-4 border-t border-white/10">
          <NavLink
            to="/settings"
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-primary-300 hover:bg-white/5 hover:text-white transition-all duration-200"
          >
            <Settings className="w-5 h-5" />
            {!collapsed && <span className="font-medium">Paramètres</span>}
          </NavLink>
        </div>

        {/* Collapse Button */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-20 w-6 h-6 rounded-full bg-primary-800 border border-primary-700
                     flex items-center justify-center text-primary-400 hover:text-white hover:bg-primary-700
                     transition-all duration-200 shadow-lg"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </motion.aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-end px-8 py-4 bg-white border-b border-primary-100">
          <div className="flex items-center gap-4">
            {/* User Avatar + Logout */}
            <div className="flex items-center gap-3">
              <div
                className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-400 to-accent-600
                              flex items-center justify-center text-white font-bold text-sm shadow-soft"
              >
                K
              </div>
              <div className="hidden sm:block">
                <p className="text-sm font-semibold text-primary-900">Kawanah Tourisme</p>
                <p className="text-xs text-primary-500">Admin</p>
              </div>
              <button
                onClick={onLogout}
                title="Se déconnecter"
                className="ml-1 p-2 rounded-xl text-primary-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
