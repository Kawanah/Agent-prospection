import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Sparkles,
  Star,
  Globe,
  AlertCircle,
  Loader2,
  ArrowUpRight,
  Bot,
  Upload,
  TrendingUp,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { leadsApi } from '../api/leads';

const TYPE_LABELS = {
  hotel: 'Hôtels',
  camping: 'Campings',
  gite: 'Gîtes',
  residence: 'Résidences',
  chambre_hotes: "Ch. d'hôtes",
  activite: 'Activités',
  other: 'Autres',
};

const TYPE_COLORS = {
  hotel: '#c9a227',
  camping: '#22c55e',
  gite: '#3b82f6',
  residence: '#8b5cf6',
  chambre_hotes: '#f97316',
  activite: '#06b6d4',
  other: '#94a3b8',
};

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recentLeads, setRecentLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, leadsRes] = await Promise.all([
          leadsApi.stats(),
          leadsApi.list({ per_page: 5, page: 1 }),
        ]);
        setStats(statsRes.data);
        setRecentLeads(leadsRes.data.leads || []);
      } catch {
        setError('Impossible de charger les données. Vérifiez que le backend tourne.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    // Auto-refresh toutes les 30 secondes
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-accent-500 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-6 border border-red-200 bg-red-50 flex items-center gap-3 text-red-600">
        <AlertCircle className="w-5 h-5 flex-shrink-0" />
        <p>{error}</p>
      </div>
    );
  }

  // Préparer les données pour les graphiques
  const typeChartData = Object.entries(stats.by_type || {})
    .map(([key, value]) => ({
      name: TYPE_LABELS[key] || key,
      value,
      color: TYPE_COLORS[key] || '#94a3b8',
    }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);

  const statusChartData = [
    { name: 'Sans site', value: stats.without_website || 0, color: '#c9a227' },
    { name: 'Avec site', value: stats.with_website || 0, color: '#22c55e' },
    {
      name: 'Non vérifié',
      value: (stats.total || 0) - (stats.with_website || 0) - (stats.without_website || 0),
      color: '#94a3b8',
    },
  ].filter((d) => d.value > 0);

  const kpis = [
    {
      label: 'Total Leads',
      value: (stats.total || 0).toLocaleString('fr-FR'),
      sub: 'établissements en base',
      icon: Users,
      color: 'accent',
    },
    {
      label: 'Sans site web',
      value: (stats.without_website || 0).toLocaleString('fr-FR'),
      sub: `${stats.total ? Math.round((stats.without_website / stats.total) * 100) : 0}% des leads`,
      icon: Globe,
      color: 'warning',
    },
    {
      label: 'Leads prioritaires',
      value: (stats.hot_leads || 0).toLocaleString('fr-FR'),
      sub: 'score ≥ 80',
      icon: Star,
      color: 'success',
    },
    {
      label: 'Score moyen',
      value: `${stats.average_score || 0}`,
      sub: 'sur 100',
      icon: TrendingUp,
      color: 'primary',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div {...fadeUp} className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-primary-900">Tableau de Bord</h1>
          <p className="mt-1 text-primary-500">Vue d'ensemble de votre prospection</p>
        </div>
        <button
          onClick={() => navigate('/import')}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 transition-colors text-sm"
        >
          <Upload className="w-4 h-4" /> Importer des leads
        </button>
      </motion.div>

      {/* KPIs */}
      <motion.div {...fadeUp} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="stat-card card-hover relative overflow-hidden group">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-primary-500">{kpi.label}</p>
                <p className="mt-2 text-3xl font-display font-bold text-primary-900">{kpi.value}</p>
                <p className="mt-1 text-xs text-primary-400">{kpi.sub}</p>
              </div>
              <div
                className={`p-3 rounded-xl ${
                  kpi.color === 'accent'
                    ? 'bg-accent-100 text-accent-600'
                    : kpi.color === 'success'
                      ? 'bg-success-100 text-success-600'
                      : kpi.color === 'warning'
                        ? 'bg-warning-100 text-warning-500'
                        : 'bg-primary-100 text-primary-600'
                }`}
              >
                <kpi.icon className="w-6 h-6" />
              </div>
            </div>
          </div>
        ))}
      </motion.div>

      {/* Graphiques */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Bar chart par type */}
        <motion.div {...fadeUp} className="lg:col-span-2 card p-6">
          <h3 className="text-lg font-display font-semibold text-primary-900 mb-1">
            Leads par type d'établissement
          </h3>
          <p className="text-sm text-primary-500 mb-6">
            Répartition de vos {(stats.total || 0).toLocaleString('fr-FR')} leads
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={typeChartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tick={{ fill: '#64748b' }} />
              <YAxis stroke="#94a3b8" fontSize={12} tick={{ fill: '#94a3b8' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
                }}
                formatter={(value) => [value.toLocaleString('fr-FR'), 'Leads']}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {typeChartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Pie chart présence web */}
        <motion.div {...fadeUp} className="card p-6">
          <h3 className="text-lg font-display font-semibold text-primary-900 mb-1">Présence web</h3>
          <p className="text-sm text-primary-500 mb-4">Opportunités de création de site</p>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={statusChartData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={72}
                paddingAngle={4}
                dataKey="value"
              >
                {statusChartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                }}
                formatter={(value) => [value.toLocaleString('fr-FR'), 'leads']}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-3 space-y-2">
            {statusChartData.map((s) => (
              <div key={s.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="text-sm text-primary-600">{s.name}</span>
                </div>
                <span className="text-sm font-semibold text-primary-900">
                  {s.value.toLocaleString('fr-FR')}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Leads récents + CTA Agent */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Leads top score */}
        <motion.div {...fadeUp} className="card p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-lg font-display font-semibold text-primary-900">Top leads</h3>
              <p className="text-sm text-primary-500">Les 5 meilleurs scores</p>
            </div>
            <button
              onClick={() => navigate('/leads')}
              className="text-sm font-medium text-accent-600 hover:text-accent-700 transition-colors flex items-center gap-1"
            >
              Voir tout <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-3">
            {recentLeads.length === 0 ? (
              <p className="text-sm text-primary-400 text-center py-6">Aucun lead en base</p>
            ) : (
              recentLeads.map((lead) => (
                <div
                  key={lead.id}
                  className="flex items-center justify-between p-3 rounded-xl bg-primary-50/50 hover:bg-primary-100/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                      {lead.name?.charAt(0) || '?'}
                    </div>
                    <div>
                      <p className="font-medium text-primary-900 text-sm max-w-[160px] truncate">
                        {lead.name}
                      </p>
                      <p className="text-xs text-primary-500">{lead.city || '—'}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Star className="w-3.5 h-3.5 text-accent-500" />
                    <span className="text-sm font-bold text-primary-900">{lead.score}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </motion.div>

        {/* Prochaines étapes */}
        <motion.div {...fadeUp} className="card p-6 flex flex-col gap-4">
          <h3 className="text-lg font-display font-semibold text-primary-900">Prochaines étapes</h3>
          <p className="text-sm text-primary-500 -mt-2">
            Que faire avec vos {(stats.total || 0).toLocaleString('fr-FR')} leads ?
          </p>

          {[
            {
              icon: Sparkles,
              title: 'Enrichir les leads',
              desc: 'Trouver les emails et infos de contact',
              path: '/enrichment',
              color: 'bg-success-100 text-success-600',
            },
            {
              icon: Bot,
              title: "Lancer l'agent",
              desc: "Prospection automatique avec l'IA",
              path: '/agent',
              color: 'bg-accent-100 text-accent-600',
            },
            {
              icon: Users,
              title: 'Créer une campagne',
              desc: 'Organiser vos envois multicanaux',
              path: '/campaigns',
              color: 'bg-primary-100 text-primary-600',
            },
          ].map((action) => (
            <button
              key={action.title}
              onClick={() => navigate(action.path)}
              className="flex items-center gap-4 p-4 rounded-xl border-2 border-primary-100 hover:border-accent-300 hover:bg-accent-50/30 transition-all text-left group"
            >
              <div className={`p-2.5 rounded-xl ${action.color} flex-shrink-0`}>
                <action.icon className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-primary-900 group-hover:text-accent-600 transition-colors">
                  {action.title}
                </p>
                <p className="text-sm text-primary-500">{action.desc}</p>
              </div>
              <ArrowUpRight className="w-4 h-4 text-primary-300 group-hover:text-accent-500 transition-colors flex-shrink-0" />
            </button>
          ))}
        </motion.div>
      </div>
    </div>
  );
}
