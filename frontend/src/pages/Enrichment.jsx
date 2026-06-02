import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Globe,
  Phone,
  Mail,
  Play,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  Clock,
  BarChart3,
  Zap,
  ChevronRight,
  Minus,
  Send,
} from 'lucide-react';
import { enrichmentApi } from '../api/enrichment';

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

// ─── Carte stat ───────────────────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sub, color }) {
  const colors = {
    violet: 'bg-violet-100 text-violet-600',
    green: 'bg-success-100 text-success-600',
    amber: 'bg-amber-100 text-amber-600',
  };
  return (
    <motion.div {...fadeUp} className="stat-card">
      <div className={`p-3 rounded-xl w-fit mb-3 ${colors[color] || colors.violet}`}>
        <Icon className="w-5 h-5" />
      </div>
      <p className="text-2xl font-bold text-primary-900">{value}</p>
      <p className="text-sm text-primary-600 font-medium mt-0.5">{label}</p>
      {sub && <p className="text-xs text-primary-400 mt-1">{sub}</p>}
    </motion.div>
  );
}

// ─── Ligne du stream d'activité ───────────────────────────────────────────────
function ActivityRow({ result, index }) {
  const found =
    result.contacts_found > 0 || result.enriched_data?.email || result.enriched_data?.phone;
  const source = result.sources?.[0] || null;
  const details = [];
  if (result.enriched_data?.email) details.push('email');
  if (result.enriched_data?.phone) details.push('tél');
  if (result.enriched_data?.website) details.push('site web');

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`flex items-center gap-3 py-2.5 px-3 rounded-lg text-sm ${
        found ? 'bg-success-50/60' : 'bg-primary-50/40'
      }`}
    >
      {found ? (
        <CheckCircle className="w-4 h-4 text-success-500 flex-shrink-0" />
      ) : (
        <Minus className="w-4 h-4 text-primary-300 flex-shrink-0" />
      )}
      <span className="font-medium text-primary-800 flex-1">{result.lead_name}</span>
      {found ? (
        <span className="text-success-600 text-xs">
          {details.join(', ')} trouvé{details.length > 1 ? 's' : ''}
          {source ? <span className="text-primary-400 ml-1">(via {source})</span> : null}
        </span>
      ) : (
        <span className="text-primary-400 text-xs">aucune donnée trouvée</span>
      )}
    </motion.div>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────
export default function Enrichment() {
  const [stats, setStats] = useState(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [batchSize, setBatchSize] = useState(10);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResult, setBatchResult] = useState(null);
  const [error, setError] = useState(null);
  const [jobProgress, setJobProgress] = useState(null); // { current, total, status, results }
  const pollRef = useRef(null);

  const fetchStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const res = await enrichmentApi.stats();
      setStats(res.data);
    } catch {
      // silencieux
    } finally {
      setLoadingStats(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Nettoyage du polling au démontage
  useEffect(
    () => () => {
      if (pollRef.current) clearInterval(pollRef.current);
    },
    []
  );

  const startPolling = (jobId, total) => {
    setJobProgress({ current: 0, total, status: 'running', results: [] });
    pollRef.current = setInterval(async () => {
      try {
        const res = await enrichmentApi.job(jobId);
        const job = res.data;
        setJobProgress({
          current: job.current,
          total: job.total,
          status: job.status,
          results: job.results,
        });
        if (job.status === 'done') {
          clearInterval(pollRef.current);
          setBatchRunning(false);
          setBatchResult({ total: job.total, results: job.results });
          await fetchStats();
        }
      } catch {
        clearInterval(pollRef.current);
        setBatchRunning(false);
      }
    }, 2000);
  };

  const handleBatch = async () => {
    setBatchRunning(true);
    setBatchResult(null);
    setJobProgress(null);
    setError(null);
    try {
      const res = await enrichmentApi.batch({ limit: batchSize, status: 'new' });
      if (!res.data.job_id) {
        setBatchRunning(false);
        return;
      }
      startPolling(res.data.job_id, res.data.total);
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'enrichissement batch");
      setBatchRunning(false);
    }
  };

  const enrichRate = stats ? stats.enrichment_rate : 0;
  const toEnrich = stats?.to_enrich ?? 0;

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <motion.div {...fadeUp} className="flex items-end justify-between">
        <div>
          <p className="text-xs font-semibold text-violet-500 uppercase tracking-widest mb-1">
            Phase 2 du pipeline
          </p>
          <h1 className="text-3xl font-display font-bold text-primary-900">Enrichissement</h1>
          <p className="mt-1 text-primary-500">
            L'agent recherche les contacts, emails et sites web pour chaque établissement
          </p>
        </div>
        <button
          onClick={fetchStats}
          className="p-2 rounded-xl border border-primary-200 hover:bg-primary-50 transition-colors"
          title="Rafraîchir"
        >
          <RefreshCw className="w-4 h-4 text-primary-500" />
        </button>
      </motion.div>

      {/* 3 stats clés */}
      <div className="grid grid-cols-3 gap-4">
        {loadingStats ? (
          Array(3)
            .fill(0)
            .map((_, i) => (
              <div key={i} className="stat-card animate-pulse">
                <div className="w-10 h-10 bg-primary-100 rounded-xl mb-3" />
                <div className="h-6 bg-primary-100 rounded w-16 mb-2" />
                <div className="h-3 bg-primary-100 rounded w-24" />
              </div>
            ))
        ) : (
          <>
            <StatCard
              icon={Clock}
              label="À enrichir"
              value={toEnrich.toLocaleString('fr-FR')}
              color="amber"
              sub="Statut NEW"
            />
            <StatCard
              icon={CheckCircle}
              label="Enrichis"
              value={(stats?.enriched ?? 0).toLocaleString('fr-FR')}
              color="green"
              sub={`sur ${(stats?.total_leads ?? 0).toLocaleString('fr-FR')} leads`}
            />
            <StatCard
              icon={BarChart3}
              label="Progression"
              value={`${enrichRate}%`}
              color="violet"
              sub="du total enrichi"
            />
          </>
        )}
      </div>

      {/* Barre de progression globale */}
      {stats && (
        <motion.div {...fadeUp} className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="font-semibold text-primary-900 text-sm">Avancement global</span>
            <span className="text-sm font-bold text-violet-600">{enrichRate}%</span>
          </div>
          <div className="w-full bg-primary-100 rounded-full h-3 overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-violet-400 to-violet-600"
              initial={{ width: 0 }}
              animate={{ width: `${enrichRate}%` }}
              transition={{ duration: 0.9, ease: 'easeOut' }}
            />
          </div>
          <p className="text-xs text-primary-400 mt-2">
            {stats.enriched} enrichis · {toEnrich} restants · {stats.total_leads} leads au total
          </p>
        </motion.div>
      )}

      {/* Bloc de lancement */}
      <motion.div {...fadeUp} className="card p-6">
        {/* Contexte de phase */}
        <div className="flex items-start gap-3 mb-6 p-4 rounded-xl bg-violet-50 border border-violet-100">
          <div className="p-2 rounded-lg bg-violet-100 text-violet-600 flex-shrink-0 mt-0.5">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-violet-900 mb-1">Ce que fait l'agent</p>
            <p className="text-xs text-violet-700 leading-relaxed">
              Pour chaque établissement, l'agent suit un pipeline automatique :
            </p>
            <div className="flex flex-wrap items-center gap-1.5 mt-2 text-xs text-violet-600 font-medium">
              <span className="px-2 py-0.5 bg-violet-100 rounded-md flex items-center gap-1">
                <Globe className="w-3 h-3" /> Site web
              </span>
              <ChevronRight className="w-3 h-3 text-violet-400" />
              <span className="px-2 py-0.5 bg-violet-100 rounded-md">PagesJaunes</span>
              <ChevronRight className="w-3 h-3 text-violet-400" />
              <span className="px-2 py-0.5 bg-violet-100 rounded-md">Societe.com</span>
              <ChevronRight className="w-3 h-3 text-violet-400" />
              <span className="px-2 py-0.5 bg-violet-100 rounded-md flex items-center gap-1">
                <Mail className="w-3 h-3" /> Patterns email
              </span>
            </div>
          </div>
        </div>

        {/* Sélecteur de taille + bouton */}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-primary-700">Lot de :</label>
            <div className="flex gap-1.5">
              {[10, 20, 50].map((n) => (
                <button
                  key={n}
                  onClick={() => setBatchSize(n)}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-colors
                    ${
                      batchSize === n
                        ? 'bg-violet-500 text-white shadow-sm'
                        : 'bg-primary-100 text-primary-600 hover:bg-primary-200'
                    }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleBatch}
            disabled={batchRunning || toEnrich === 0}
            className="flex items-center gap-2 px-7 py-3 rounded-xl bg-violet-500 text-white font-semibold text-sm
                       hover:bg-violet-600 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed ml-auto shadow-sm"
          >
            {batchRunning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Enrichissement en cours…
              </>
            ) : (
              <>
                <Play className="w-4 h-4" /> Lancer l'enrichissement{' '}
                <span className="opacity-70 ml-1">({batchSize} leads)</span>
              </>
            )}
          </button>
        </div>

        {toEnrich === 0 && !loadingStats && (
          <p className="mt-3 text-xs text-success-600 flex items-center gap-1.5">
            <CheckCircle className="w-3.5 h-3.5" /> Tous les leads sont déjà enrichis
          </p>
        )}

        {/* Barre de progression live */}
        <AnimatePresence>
          {jobProgress && jobProgress.status === 'running' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-5 space-y-2"
            >
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-violet-700 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Enrichissement en cours…
                </span>
                <span className="text-primary-500 font-semibold">
                  {jobProgress.current} / {jobProgress.total}
                </span>
              </div>
              <div className="w-full bg-primary-100 rounded-full h-3 overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-violet-400 to-violet-600"
                  animate={{
                    width: `${jobProgress.total > 0 ? (jobProgress.current / jobProgress.total) * 100 : 0}%`,
                  }}
                  transition={{ duration: 0.4, ease: 'easeOut' }}
                />
              </div>
              {jobProgress.results.length > 0 && (
                <p className="text-xs text-primary-500">
                  Dernier traité :{' '}
                  <span className="font-medium text-primary-700">
                    {jobProgress.results[jobProgress.results.length - 1]?.lead_name}
                  </span>
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Erreur */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="mt-4 p-3 rounded-xl bg-error-50 border border-error-200 flex items-center gap-2 text-error-600 text-sm"
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Stream d'activité — résultats du dernier batch */}
      <AnimatePresence>
        {batchResult && (
          <motion.div
            {...fadeUp}
            initial="hidden"
            animate="visible"
            exit={{ opacity: 0 }}
            className="card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-primary-900 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-violet-500" />
                Résultats du dernier batch
              </h3>
              <div className="flex items-center gap-3 text-xs text-primary-500">
                <span className="flex items-center gap-1 text-success-600 font-medium">
                  <CheckCircle className="w-3.5 h-3.5" />
                  {batchResult.enriched ?? batchResult.success_count ?? 0} enrichis
                </span>
                <span>·</span>
                <span>{batchResult.failed ?? batchResult.error_count ?? 0} sans résultat</span>
                <span>·</span>
                <span>{batchResult.total ?? batchSize} traités</span>
              </div>
            </div>

            {batchResult.results && batchResult.results.length > 0 ? (
              <div className="space-y-1.5">
                {batchResult.results.map((result, i) => (
                  <ActivityRow key={i} result={result} index={i} />
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-3 py-4 text-sm text-primary-500">
                <CheckCircle className="w-5 h-5 text-success-400" />
                <span>
                  {batchResult.enriched ?? batchResult.success_count ?? 0} leads enrichis avec
                  succès.
                </span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* CTA permanent → Campagnes */}
      <motion.div {...fadeUp} className="card p-5 flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold text-primary-900 text-sm">
            {stats?.enriched > 0
              ? `${stats.enriched.toLocaleString('fr-FR')} leads enrichis sont prêts à être contactés`
              : 'Enrichissez vos leads, puis lancez une campagne'}
          </p>
          <p className="text-xs text-primary-400 mt-0.5">
            Créez une campagne email ou LinkedIn pour démarrer la prospection
          </p>
        </div>
        <a
          href="/campaigns"
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-accent-500 text-white font-semibold text-sm
                     hover:bg-accent-600 active:scale-95 transition-all shadow-sm flex-shrink-0"
        >
          <Send className="w-4 h-4" />
          Envoyer en campagne
        </a>
      </motion.div>
    </div>
  );
}
