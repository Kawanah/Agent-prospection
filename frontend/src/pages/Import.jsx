import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  FileText,
  CheckCircle,
  AlertCircle,
  Download,
  X,
  Loader2,
  Database,
  Play,
  Pause,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Clock,
  Ban,
  MapPin,
  Search,
  Building2,
  Sparkles,
} from 'lucide-react';
import { importsApi } from '../api/imports';
import { leadsApi } from '../api/leads';
import { GOOGLE_LEAD_TYPES, PAPPERS_NAF, SIRENE_NAF } from '../features/import/importMetadata';
import { useImportRequest } from '../features/import/useImportRequest';

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

const ALLOWED_EXTENSIONS = ['.csv', '.xlsx', '.xls'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 Mo

const TABS = [
  {
    id: 'gouv',
    Icon: Database,
    label: 'Atout France',
    badge: '21k',
    badgeClass: 'bg-accent-500 text-white',
  },
  {
    id: 'google',
    Icon: MapPin,
    label: 'Google Places',
    badge: 'Nouveau',
    badgeClass: 'bg-green-500 text-white',
  },
  {
    id: 'sirene',
    Icon: Building2,
    label: 'Sirene / INSEE',
    badge: 'Gratuit',
    badgeClass: 'bg-violet-500 text-white',
  },
  {
    id: 'pappers',
    Icon: Sparkles,
    label: 'Pappers',
    badge: '🔥 Leads',
    badgeClass: 'bg-orange-500 text-white',
  },
  { id: 'csv', Icon: Upload, label: 'CSV / Excel', badge: null, badgeClass: '' },
];

// Types réellement présents dans le dataset Atout France
// (hôtels, campings, résidences, villages de vacances, parcs résidentiels)
const LEAD_TYPES = [
  { value: 'hotel', label: 'Hôtels de tourisme', emoji: '🏨', count: '13 192' },
  { value: 'camping', label: 'Campings', emoji: '⛺', count: '5 704' },
  { value: 'residence', label: 'Résidences & Villages', emoji: '🏢', count: '2 253' },
  { value: 'other', label: 'Auberges collectives', emoji: '🏠', count: '106' },
];

const REGIONS = [
  '',
  'Auvergne-Rhône-Alpes',
  'Bourgogne-Franche-Comté',
  'Bretagne',
  'Centre-Val de Loire',
  'Corse',
  'Grand Est',
  'Hauts-de-France',
  'Île-de-France',
  'Normandie',
  'Nouvelle-Aquitaine',
  'Occitanie',
  'Pays de la Loire',
  "Provence-Alpes-Côte d'Azur",
];

const STATUS_CONFIG = {
  pending: { label: 'En attente', color: 'bg-primary-100 text-primary-600', dot: 'bg-primary-400' },
  running: {
    label: 'En cours',
    color: 'bg-accent-100 text-accent-700',
    dot: 'bg-accent-500 animate-pulse',
  },
  paused: { label: 'En pause', color: 'bg-warning-100 text-warning-700', dot: 'bg-warning-500' },
  completed: { label: 'Terminé', color: 'bg-success-100 text-success-700', dot: 'bg-success-500' },
  failed: { label: 'Échec', color: 'bg-error-100 text-error-700', dot: 'bg-error-500' },
};

// ─── Composant : badge de statut ──────────────────────────────────────────────
function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${cfg.color}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ─── Composant : barre de progression ────────────────────────────────────────
function ProgressBar({ pct, status }) {
  const color =
    status === 'completed'
      ? 'bg-success-500'
      : status === 'failed'
        ? 'bg-error-500'
        : status === 'paused'
          ? 'bg-warning-500'
          : 'bg-accent-500';
  return (
    <div className="w-full bg-primary-100 rounded-full h-2 overflow-hidden">
      <motion.div
        className={`h-full rounded-full ${color}`}
        initial={{ width: 0 }}
        animate={{ width: `${pct ?? 0}%` }}
        transition={{ duration: 0.4 }}
      />
    </div>
  );
}

// ─── Composant : carte d'un job ───────────────────────────────────────────────
function JobCard({ job, onStart, onPause, actionLoading }) {
  const [expanded, setExpanded] = useState(false);
  const types = Array.isArray(job.lead_types) ? job.lead_types : [];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-primary-100 rounded-2xl bg-white overflow-hidden"
    >
      {/* En-tête du job */}
      <div className="flex items-center justify-between p-4 gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
            <Database className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-primary-900 text-sm truncate">Job #{job.id}</span>
              <StatusBadge status={job.status} />
            </div>
            <p className="text-xs text-primary-400 mt-0.5">
              {types.length > 0 ? types.join(', ') : 'tous types'}
              {job.star_filter
                ? ` · ${job.star_filter
                    .sort()
                    .map((s) => s + '★')
                    .join(', ')}`
                : ''}
              {job.region ? ` · ${job.region}` : ''}
              {job.department ? ` · Dép. ${job.department}` : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Bouton action */}
          {(job.status === 'pending' || job.status === 'paused' || job.status === 'failed') && (
            <button
              onClick={() => onStart(job.id)}
              disabled={actionLoading === job.id}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-accent-500 text-white text-xs font-semibold hover:bg-accent-600 transition-colors disabled:opacity-50"
            >
              {actionLoading === job.id ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Play className="w-3 h-3" />
              )}
              {job.status === 'paused' ? 'Reprendre' : 'Lancer'}
            </button>
          )}
          {job.status === 'running' && (
            <button
              onClick={() => onPause(job.id)}
              disabled={actionLoading === job.id}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-warning-100 text-warning-700 text-xs font-semibold hover:bg-warning-200 transition-colors disabled:opacity-50"
            >
              {actionLoading === job.id ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Pause className="w-3 h-3" />
              )}
              Pause
            </button>
          )}

          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg hover:bg-primary-100 text-primary-400 transition-colors"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Barre de progression */}
      {(job.status === 'running' || job.status === 'paused' || job.status === 'completed') && (
        <div className="px-4 pb-3">
          <div className="flex justify-between text-xs text-primary-400 mb-1.5">
            <span>
              Page {job.current_page - 1}/{job.total_pages ?? '?'}
            </span>
            <span>{job.progress_pct != null ? `${job.progress_pct}%` : '—'}</span>
          </div>
          <ProgressBar pct={job.progress_pct} status={job.status} />
          <div className="flex gap-4 mt-2 text-xs text-primary-500">
            <span className="text-success-600 font-medium">✓ {job.total_created} créés</span>
            <span>{job.total_skipped} ignorés</span>
            {job.total_errors > 0 && (
              <span className="text-error-500">{job.total_errors} erreurs</span>
            )}
          </div>
        </div>
      )}

      {/* Bouton "Voir ces leads" quand terminé */}
      {job.status === 'completed' && job.total_created > 0 && (
        <div className="px-4 pb-3">
          <a
            href="/leads"
            className="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-xl bg-success-50 text-success-700 border border-success-200 text-sm font-semibold hover:bg-success-100 transition-colors"
          >
            Voir ces leads →
          </a>
        </div>
      )}

      {/* Détails étendus */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-primary-50 bg-primary-50/50 px-4 py-3 text-xs text-primary-500 space-y-1"
          >
            <p>
              Dataset : <span className="font-mono text-primary-700">{job.dataset}</span>
            </p>
            <p>
              Taille lot : <span className="font-semibold text-primary-700">100</span>{' '}
              enregistrements
            </p>
            {job.last_checkpoint_at && (
              <p>Dernier checkpoint : {new Date(job.last_checkpoint_at).toLocaleString('fr-FR')}</p>
            )}
            {job.created_at && <p>Créé le : {new Date(job.created_at).toLocaleString('fr-FR')}</p>}
            {job.last_error && <p className="text-error-600">Erreur : {job.last_error}</p>}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Helper : toggle d'un item dans une liste ─────────────────────────────────
const toggle = (list, item) =>
  list.includes(item) ? list.filter((i) => i !== item) : [...list, item];

// ─── Composant : alerte d'erreur ─────────────────────────────────────────────
function ErrorAlert({ error }) {
  if (!error) return null;
  return (
    <div className="flex items-center gap-2 text-sm text-error-600 bg-error-50 border border-error-200 rounded-xl px-4 py-3">
      <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
    </div>
  );
}

// ─── Composant : résultats d'import ──────────────────────────────────────────
function ImportResultCard({ result, color }) {
  if (!result) return null;
  const colors = {
    green: {
      border: 'border-green-200',
      bg: 'bg-green-50',
      text: 'text-green-700',
      btn: 'bg-green-600 hover:bg-green-700',
    },
    violet: {
      border: 'border-violet-200',
      bg: 'bg-violet-50',
      text: 'text-violet-700',
      btn: 'bg-violet-600 hover:bg-violet-700',
    },
    orange: {
      border: 'border-orange-200',
      bg: 'bg-orange-50',
      text: 'text-orange-700',
      btn: 'bg-orange-500 hover:bg-orange-600',
    },
  };
  const c = colors[color] ?? colors.green;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={`card p-6 border-2 ${c.border} ${c.bg}`}
    >
      <div className="flex items-center gap-3 mb-4">
        <CheckCircle className={`w-6 h-6 ${c.text}`} />
        <h3 className={`font-semibold text-lg ${c.text}`}>Import terminé</h3>
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        {[
          ['Importés', result.imported ?? 0],
          ['Ignorés / doublons', result.skipped ?? 0],
          ...(result.new_no_website > 0 ? [['🔥 Sans site web', result.new_no_website]] : []),
          ...(result.errors?.length > 0 ? [['Erreurs', result.errors.length]] : []),
        ].map(([label, val]) => (
          <div key={label} className="text-center p-3 bg-white rounded-xl">
            <p className="text-2xl font-bold text-primary-900">{val}</p>
            <p className="text-sm text-primary-500">{label}</p>
          </div>
        ))}
      </div>
      <a
        href="/leads"
        className={`flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-white text-sm font-semibold transition-colors ${c.btn}`}
      >
        Voir ces leads →
      </a>
    </motion.div>
  );
}

// ─── Bloc Google Places ───────────────────────────────────────────────────────
function GooglePlacesBlock() {
  const [selectedTypes, setSelectedTypes] = useState(['hotel', 'camping']);
  const [location, setLocation] = useState('');
  const [radiusKm, setRadiusKm] = useState(30);
  const [maxResults, setMaxResults] = useState(200);
  const { loading, result, error, run } = useImportRequest(importsApi.googlePlaces);

  const canSubmit = location.trim().length >= 2 && selectedTypes.length > 0 && !loading;

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-2xl">
        <MapPin className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-green-800">
          <span className="font-semibold">Google Maps Platform</span> — Couvre tous les
          établissements, classés ou non : gîtes, chambres d'hôtes, activités, nouveaux
          établissements absents d'Atout France.
          <span className="block mt-1 text-green-600 text-xs">
            ✅ Clé API détectée — prêt à l'emploi
          </span>
        </div>
      </div>

      <div className="card p-6 space-y-5">
        {/* Types */}
        <div>
          <label className="block text-sm font-semibold text-primary-700 mb-3">
            Types d'établissements
          </label>
          <div className="flex flex-wrap gap-2">
            {GOOGLE_LEAD_TYPES.map(({ value, label, emoji }) => {
              const selected = selectedTypes.includes(value);
              return (
                <button
                  key={value}
                  onClick={() => setSelectedTypes((prev) => toggle(prev, value))}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border-2 transition-all
                    ${selected ? 'border-green-500 bg-green-50 text-green-700' : 'border-primary-200 text-primary-500 hover:border-primary-300'}`}
                >
                  {emoji} {label}
                  {selected && <CheckCircle className="w-3.5 h-3.5" />}
                </button>
              );
            })}
          </div>
        </div>

        {/* Localisation + rayon */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">
              Zone géographique <span className="text-error-500">*</span>
            </label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-primary-400" />
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Ex : Bordeaux, Gironde, Bretagne…"
                className={`w-full pl-10 pr-4 py-2.5 rounded-xl border-2 bg-white text-primary-900 text-sm
                  focus:border-green-500 focus:ring-4 focus:ring-green-100 outline-none transition-all
                  ${!location.trim() ? 'border-amber-300' : 'border-primary-200'}`}
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">
              Rayon : <span className="text-green-600 font-bold">{radiusKm} km</span>
            </label>
            <input
              type="range"
              min={5}
              max={100}
              step={5}
              value={radiusKm}
              onChange={(e) => setRadiusKm(Number(e.target.value))}
              className="w-full accent-green-500"
            />
            <div className="flex justify-between text-xs text-primary-400 mt-0.5">
              <span>5 km</span>
              <span>100 km</span>
            </div>
          </div>
        </div>

        {/* Plafond */}
        <div>
          <label className="block text-sm font-semibold text-primary-700 mb-1.5">
            Plafond : <span className="text-green-600 font-bold">{maxResults} établissements</span>
            <span className="ml-2 text-xs font-normal text-primary-400">
              (~{((maxResults * 0.032) / 20).toFixed(2)} $ de crédit)
            </span>
          </label>
          <input
            type="range"
            min={20}
            max={500}
            step={20}
            value={maxResults}
            onChange={(e) => setMaxResults(Number(e.target.value))}
            className="w-full accent-green-500"
          />
          <div className="flex justify-between text-xs text-primary-400 mt-0.5">
            <span>20</span>
            <span>500</span>
          </div>
        </div>

        {/* Résumé + bouton */}
        <div className="flex items-center justify-between pt-1">
          <p className="text-sm text-primary-500">
            {canSubmit ? (
              <span>
                Import{' '}
                <span className="font-semibold text-primary-700">
                  {selectedTypes.length} type(s)
                </span>{' '}
                · {location} · max {maxResults}
              </span>
            ) : (
              <span className="text-amber-500">Renseignez la zone géographique</span>
            )}
          </p>
          <button
            onClick={() =>
              run({
                lead_types: selectedTypes,
                location: location.trim(),
                radius_km: radiusKm,
                max_results: maxResults,
              })
            }
            disabled={!canSubmit}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-green-600 text-white font-semibold text-sm hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Import…
              </>
            ) : (
              <>
                <Search className="w-4 h-4" /> Lancer la recherche
              </>
            )}
          </button>
        </div>

        <ErrorAlert error={error} />
      </div>

      <AnimatePresence>
        {result && <ImportResultCard result={result} color="green" />}
      </AnimatePresence>
    </div>
  );
}

// ─── Bloc Sirene / INSEE ──────────────────────────────────────────────────────
function SireneBlock() {
  const [selectedNaf, setSelectedNaf] = useState(['5510Z', '5520Z', '5530Z']);
  const [department, setDepartment] = useState('');
  const [maxResults, setMaxResults] = useState(300);
  const [newOnly, setNewOnly] = useState(false);
  const { loading, result, error, run } = useImportRequest(importsApi.sirene);

  const canSubmit = department.trim().length >= 2 && selectedNaf.length > 0 && !loading;

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 p-4 bg-violet-50 border border-violet-200 rounded-2xl">
        <Building2 className="w-5 h-5 text-violet-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-violet-800">
          <span className="font-semibold">API Sirene / INSEE</span> — Base officielle de toutes les
          entreprises françaises. Couvre gîtes, chambres d'hôtes et activités absents d'Atout
          France.
          <span className="block mt-1 text-violet-600 text-xs font-medium">
            ✅ Gratuit · Sans clé API · Données officielles INSEE
          </span>
        </div>
      </div>

      <div className="card p-6 space-y-5">
        {/* Codes NAF */}
        <div>
          <label className="block text-sm font-semibold text-primary-700 mb-3">
            Secteurs d'activité (codes NAF)
          </label>
          <div className="space-y-2">
            {SIRENE_NAF.map(({ code, label, emoji }) => {
              const selected = selectedNaf.includes(code);
              return (
                <label
                  key={code}
                  className={`flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all
                  ${selected ? 'border-violet-400 bg-violet-50' : 'border-primary-200 hover:border-primary-300'}`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => setSelectedNaf((prev) => toggle(prev, code))}
                    className="accent-violet-500 w-4 h-4"
                  />
                  <span className="text-lg">{emoji}</span>
                  <div className="min-w-0">
                    <p
                      className={`text-sm font-medium ${selected ? 'text-violet-800' : 'text-primary-700'}`}
                    >
                      {label}
                    </p>
                    <p className="text-xs text-primary-400 font-mono">{code}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        {/* Département + plafond */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">
              Département <span className="text-error-500">*</span>
            </label>
            <input
              type="text"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="Ex : 33, 06, 75…"
              maxLength={3}
              className={`w-full px-4 py-2.5 rounded-xl border-2 bg-white text-primary-900 text-sm
                focus:border-violet-500 focus:ring-4 focus:ring-violet-100 outline-none transition-all
                ${!department.trim() ? 'border-amber-300' : 'border-primary-200'}`}
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">
              Plafond : <span className="text-violet-600 font-bold">{maxResults} entreprises</span>
            </label>
            <input
              type="range"
              min={50}
              max={1000}
              step={50}
              value={maxResults}
              onChange={(e) => setMaxResults(Number(e.target.value))}
              className="w-full accent-violet-500 mt-2"
            />
            <div className="flex justify-between text-xs text-primary-400 mt-0.5">
              <span>50</span>
              <span>1 000</span>
            </div>
          </div>
        </div>

        {/* Option nouvelles immat. */}
        <label className="flex items-center gap-3 p-4 rounded-xl border-2 border-primary-200 cursor-pointer hover:border-violet-300 transition-colors">
          <input
            type="checkbox"
            checked={newOnly}
            onChange={(e) => setNewOnly(e.target.checked)}
            className="accent-violet-500 w-4 h-4"
          />
          <div>
            <p className="text-sm font-semibold text-primary-800">
              🔥 Nouvelles immatriculations seulement{' '}
              <span className="text-xs font-normal text-violet-600 ml-1">(&lt; 1 an)</span>
            </p>
            <p className="text-xs text-primary-400 mt-0.5">
              Ces entreprises viennent d&apos;ouvrir et n&apos;ont probablement pas encore de site
              web — prospects chauds
            </p>
          </div>
        </label>

        {/* Résumé + bouton */}
        <div className="flex items-center justify-between pt-1">
          <p className="text-sm text-primary-500">
            {canSubmit ? (
              <span>
                <span className="font-semibold text-primary-700">
                  {selectedNaf.length} code(s) NAF
                </span>{' '}
                · Dép. {department} · max {maxResults}
              </span>
            ) : (
              <span className="text-amber-500">Renseignez un département</span>
            )}
          </p>
          <button
            onClick={() =>
              run({
                naf_codes: selectedNaf,
                department: department.trim(),
                max_results: maxResults,
                new_only: newOnly,
              })
            }
            disabled={!canSubmit}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-violet-600 text-white font-semibold text-sm hover:bg-violet-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Import…
              </>
            ) : (
              <>
                <Building2 className="w-4 h-4" /> Lancer l&apos;import
              </>
            )}
          </button>
        </div>

        <ErrorAlert error={error} />
      </div>

      <AnimatePresence>
        {result && <ImportResultCard result={result} color="violet" />}
      </AnimatePresence>
    </div>
  );
}

// ─── Bloc Pappers ─────────────────────────────────────────────────────────────
function PappersBlock() {
  const [selectedNaf, setSelectedNaf] = useState(['5510Z', '5520Z', '5530Z']);
  const [department, setDepartment] = useState('');
  const [maxResults, setMaxResults] = useState(200);
  const [newOnly, setNewOnly] = useState(true);
  const [monthsBack, setMonthsBack] = useState(6);
  const { loading, result, error, run } = useImportRequest(importsApi.pappers);

  const canSubmit = department.trim().length >= 2 && selectedNaf.length > 0 && !loading;

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 p-4 bg-orange-50 border border-orange-200 rounded-2xl">
        <Sparkles className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-orange-800">
          <span className="font-semibold">Pappers.fr</span> — Données légales françaises enrichies.
          Trouve les <strong>nouvelles structures hospitalité</strong> qui n&apos;ont pas encore de
          site web, avec le nom du dirigeant inclus directement.
          <span className="block mt-1 text-orange-600 text-xs font-medium">
            ⏳ Accès gratuit 15 jours — profitez-en pour importer un maximum
          </span>
        </div>
      </div>

      <div className="card p-6 space-y-5">
        {/* Codes NAF */}
        <div>
          <label className="block text-sm font-semibold text-primary-700 mb-3">
            Secteurs d&apos;activité (codes NAF)
          </label>
          <div className="space-y-2">
            {PAPPERS_NAF.map(({ code, label, emoji }) => {
              const selected = selectedNaf.includes(code);
              return (
                <label
                  key={code}
                  className={`flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all
                  ${selected ? 'border-orange-400 bg-orange-50' : 'border-primary-200 hover:border-primary-300'}`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => setSelectedNaf((prev) => toggle(prev, code))}
                    className="accent-orange-500 w-4 h-4"
                  />
                  <span className="text-lg">{emoji}</span>
                  <div className="min-w-0">
                    <p
                      className={`text-sm font-medium ${selected ? 'text-orange-800' : 'text-primary-700'}`}
                    >
                      {label}
                    </p>
                    <p className="text-xs text-primary-400 font-mono">{code}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        {/* Département + plafond */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">
              Département <span className="text-error-500">*</span>
            </label>
            <input
              type="text"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="Ex : 33, 06, 75…"
              maxLength={3}
              className={`w-full px-4 py-2.5 rounded-xl border-2 bg-white text-primary-900 text-sm
                focus:border-orange-500 focus:ring-4 focus:ring-orange-100 outline-none transition-all
                ${!department.trim() ? 'border-amber-300' : 'border-primary-200'}`}
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">
              Plafond : <span className="text-orange-600 font-bold">{maxResults} structures</span>
            </label>
            <input
              type="range"
              min={50}
              max={500}
              step={50}
              value={maxResults}
              onChange={(e) => setMaxResults(Number(e.target.value))}
              className="w-full accent-orange-500 mt-2"
            />
            <div className="flex justify-between text-xs text-primary-400 mt-0.5">
              <span>50</span>
              <span>500</span>
            </div>
          </div>
        </div>

        {/* Option nouvelles structures */}
        <div
          className={`p-4 rounded-xl border-2 transition-all ${newOnly ? 'border-orange-300 bg-orange-50' : 'border-primary-200'}`}
        >
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={newOnly}
              onChange={(e) => setNewOnly(e.target.checked)}
              className="accent-orange-500 w-4 h-4"
            />
            <div>
              <p className="text-sm font-semibold text-primary-800">
                🔥 Nouvelles structures seulement
                <span className="text-xs font-normal text-orange-600 ml-1">
                  (prospect chaud idéal)
                </span>
              </p>
              <p className="text-xs text-primary-400 mt-0.5">
                Viennent d&apos;ouvrir et n&apos;ont probablement pas encore de site web
              </p>
            </div>
          </label>
          {newOnly && (
            <div className="mt-3 pl-7">
              <label className="block text-xs font-semibold text-orange-700 mb-1">
                Fenêtre : <span className="text-orange-600">{monthsBack} derniers mois</span>
              </label>
              <input
                type="range"
                min={1}
                max={18}
                step={1}
                value={monthsBack}
                onChange={(e) => setMonthsBack(Number(e.target.value))}
                className="w-full accent-orange-500"
              />
              <div className="flex justify-between text-xs text-primary-400 mt-0.5">
                <span>1 mois</span>
                <span>18 mois</span>
              </div>
            </div>
          )}
        </div>

        {/* Résumé + bouton */}
        <div className="flex items-center justify-between pt-1">
          <p className="text-sm text-primary-500">
            {canSubmit ? (
              <span>
                <span className="font-semibold text-primary-700">
                  {selectedNaf.length} secteur(s)
                </span>{' '}
                · Dép. {department} · max {maxResults}
              </span>
            ) : (
              <span className="text-amber-500">Renseignez un département</span>
            )}
          </p>
          <button
            onClick={() =>
              run({
                naf_codes: selectedNaf,
                department: department.trim(),
                max_results: maxResults,
                new_only: newOnly,
                months_back: monthsBack,
              })
            }
            disabled={!canSubmit}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-orange-500 text-white font-semibold text-sm hover:bg-orange-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Import…
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Trouver les leads
              </>
            )}
          </button>
        </div>

        <ErrorAlert error={error} />
      </div>

      <AnimatePresence>
        {result && <ImportResultCard result={result} color="orange" />}
      </AnimatePresence>
    </div>
  );
}

// ─── Bloc principal data.gouv.fr ──────────────────────────────────────────────
const STAR_OPTIONS = [
  { value: '1', label: '1 étoile', emoji: '⭐' },
  { value: '2', label: '2 étoiles', emoji: '⭐⭐' },
  { value: '3', label: '3 étoiles', emoji: '⭐⭐⭐' },
  { value: '4', label: '4 étoiles', emoji: '⭐⭐⭐⭐' },
  { value: '5', label: '5 étoiles', emoji: '⭐⭐⭐⭐⭐' },
];

function GouvImportBlock() {
  const [selectedTypes, setSelectedTypes] = useState(['hotel', 'camping', 'residence']);
  const [selectedStars, setSelectedStars] = useState([]);
  const [region, setRegion] = useState('');
  const [department, setDepartment] = useState('');
  const [creating, setCreating] = useState(false);
  const [actionLoading, setActionLoading] = useState(null); // job_id en cours d'action
  const [jobs, setJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [createError, setCreateError] = useState(null);
  const pollingRef = useRef(null);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await importsApi.gouvJobs();
      setJobs(res.data.jobs || []);
    } catch {
      // silencieux si le backend n'est pas lancé
    } finally {
      setLoadingJobs(false);
    }
  }, []);

  // Polling : toutes les 2s si un job est en cours
  useEffect(() => {
    fetchJobs();
    pollingRef.current = setInterval(() => {
      fetchJobs();
    }, 2000);
    return () => clearInterval(pollingRef.current);
  }, [fetchJobs]);

  const handleCreate = async () => {
    if (selectedTypes.length === 0) return;
    setCreating(true);
    setCreateError(null);
    try {
      const res = await importsApi.createGouvJob({
        lead_types: selectedTypes,
        region: region || null,
        department: department || null,
        star_filter: selectedStars.length > 0 ? selectedStars : null,
        batch_size: 100,
      });
      await fetchJobs();
      // Auto-lancer le job
      await importsApi.startGouvJob(res.data.job_id);
      await fetchJobs();
    } catch (err) {
      setCreateError(err.response?.data?.detail || 'Erreur lors de la création du job');
    } finally {
      setCreating(false);
    }
  };

  const handleStart = async (jobId) => {
    setActionLoading(jobId);
    try {
      await importsApi.startGouvJob(jobId);
      await fetchJobs();
    } finally {
      setActionLoading(null);
    }
  };

  const handlePause = async (jobId) => {
    setActionLoading(jobId);
    try {
      await importsApi.pauseGouvJob(jobId);
      await fetchJobs();
    } finally {
      setActionLoading(null);
    }
  };

  const hasRunning = jobs.some((j) => j.status === 'running');

  return (
    <div className="space-y-5">
      {/* Formulaire de création */}
      <div className="card p-6 space-y-5">
        {/* Types d'établissements */}
        <div>
          <label className="block text-sm font-semibold text-primary-700 mb-3">
            Types d'établissements à importer
          </label>
          <div className="flex flex-wrap gap-2">
            {LEAD_TYPES.map(({ value, label, emoji, count }) => {
              const selected = selectedTypes.includes(value);
              return (
                <button
                  key={value}
                  onClick={() => setSelectedTypes((prev) => toggle(prev, value))}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border-2 transition-all duration-150
                    ${
                      selected
                        ? 'border-accent-500 bg-accent-50 text-accent-700'
                        : 'border-primary-200 text-primary-500 hover:border-primary-300 hover:text-primary-700'
                    }`}
                >
                  <span>{emoji}</span>
                  {label}
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded-full ${selected ? 'bg-accent-100 text-accent-600' : 'bg-primary-100 text-primary-400'}`}
                  >
                    {count}
                  </span>
                  {selected && <CheckCircle className="w-3.5 h-3.5" />}
                </button>
              );
            })}
          </div>
          {selectedTypes.length === 0 && (
            <p className="text-xs text-error-500 mt-2">Sélectionne au moins un type</p>
          )}
        </div>

        {/* Filtre étoiles — visible uniquement si "hotel" est sélectionné */}
        {selectedTypes.includes('hotel') && (
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-2">
              Classement hôtelier{' '}
              <span className="text-primary-400 font-normal">(optionnel — vide = tous)</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {STAR_OPTIONS.map(({ value, label }) => {
                const selected = selectedStars.includes(value);
                return (
                  <button
                    key={value}
                    onClick={() => setSelectedStars((prev) => toggle(prev, value))}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium border-2 transition-all duration-150
                      ${
                        selected
                          ? 'border-amber-400 bg-amber-50 text-amber-700'
                          : 'border-primary-200 text-primary-500 hover:border-primary-300'
                      }`}
                  >
                    {'⭐'.repeat(parseInt(value))} {label}
                    {selected && <CheckCircle className="w-3.5 h-3.5" />}
                  </button>
                );
              })}
            </div>
            {selectedStars.length > 0 && (
              <p className="text-xs text-amber-600 mt-1.5">
                Uniquement les hôtels{' '}
                {selectedStars
                  .sort()
                  .map((s) => s + '★')
                  .join(', ')}
              </p>
            )}
          </div>
        )}

        {/* Message d'aide géographique */}
        <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700">
          <Ban className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span>
            <span className="font-semibold">Travaillez département par département</span> pour
            garder le contrôle. Un département = un import = ~50 à 500 établissements.
          </span>
        </div>

        {/* Filtres géographiques */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">Région</label>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl border-2 border-primary-200 bg-white text-primary-900 text-sm
                         focus:border-accent-500 focus:ring-4 focus:ring-accent-100 outline-none transition-all"
            >
              <option value="">— Choisir une région (optionnel) —</option>
              {REGIONS.filter(Boolean).map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-primary-700 mb-1.5">
              Département <span className="text-error-500">*</span>
            </label>
            <input
              type="text"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="Ex : 06, 75, 13…"
              maxLength={3}
              className={`w-full px-4 py-2.5 rounded-xl border-2 bg-white text-primary-900 text-sm
                         focus:border-accent-500 focus:ring-4 focus:ring-accent-100 outline-none transition-all
                         ${!department ? 'border-amber-300' : 'border-primary-200'}`}
            />
            {!department && (
              <p className="text-xs text-amber-600 mt-1.5 flex items-center gap-1">
                <Ban className="w-3 h-3" /> Obligatoire — entrez un code département
              </p>
            )}
          </div>
        </div>

        {/* Résumé + bouton */}
        <div className="flex items-center justify-between pt-1">
          <div className="text-sm text-primary-500">
            {selectedTypes.length > 0 ? (
              <span>
                Import de{' '}
                <span className="font-semibold text-primary-700">
                  {selectedTypes.length} type(s)
                </span>
                {selectedStars.length > 0 &&
                  ` · ${selectedStars
                    .sort()
                    .map((s) => s + '★')
                    .join(', ')}`}
                {region ? ` · ${region}` : ''}
                {department ? (
                  ` · Dép. ${department}`
                ) : (
                  <span className="text-amber-600"> · département requis</span>
                )}
                {department && <span className="text-primary-400"> — lots de 100</span>}
              </span>
            ) : (
              <span className="text-error-400">Sélectionne des types</span>
            )}
          </div>
          <button
            onClick={handleCreate}
            disabled={creating || selectedTypes.length === 0 || hasRunning || !department}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-accent-500 text-white font-semibold text-sm
                       hover:bg-accent-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {creating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Création…
              </>
            ) : hasRunning ? (
              <>
                <Clock className="w-4 h-4" /> Import en cours
              </>
            ) : (
              <>
                <Play className="w-4 h-4" /> Lancer l'import
              </>
            )}
          </button>
        </div>

        <ErrorAlert error={createError} />
      </div>

      {/* Liste des jobs */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-primary-700">
            Historique des imports
            {hasRunning && (
              <span className="ml-2 text-xs font-normal text-accent-600 animate-pulse">
                ● Actualisation automatique
              </span>
            )}
          </h3>
          <button
            onClick={fetchJobs}
            className="p-1.5 rounded-lg hover:bg-primary-100 text-primary-400 transition-colors"
            title="Rafraîchir"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {loadingJobs ? (
          <div className="flex items-center justify-center py-8 text-primary-400">
            <Loader2 className="w-5 h-5 animate-spin mr-2" /> Chargement…
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-8 text-primary-400 border border-dashed border-primary-200 rounded-2xl">
            <Database className="w-8 h-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm">Aucun import lancé pour l'instant</p>
          </div>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onStart={handleStart}
                onPause={handlePause}
                actionLoading={actionLoading}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Page principale Import ───────────────────────────────────────────────────
export default function Import() {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('gouv'); // 'gouv' | 'google' | 'sirene' | 'csv'
  const inputRef = useRef(null);

  const handleFile = (f) => {
    const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Format non supporté (${ext}). Utilisez CSV, XLSX ou XLS.`);
      return;
    }
    if (f.size > MAX_FILE_SIZE) {
      setError(
        `Fichier trop volumineux (${(f.size / 1024 / 1024).toFixed(1)} Mo). Maximum : 10 Mo.`
      );
      return;
    }
    setFile(f);
    setResult(null);
    setError(null);
  };
  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };
  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };
  const handleDragLeave = () => setDragging(false);

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await leadsApi.upload(formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
    } catch (err) {
      setError(
        err.response?.data?.detail || "Erreur lors de l'import. Vérifiez le format du fichier."
      );
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <motion.div {...fadeUp}>
        <h1 className="text-3xl font-display font-bold text-primary-900">Import</h1>
        <p className="mt-1 text-primary-500">
          Importez des leads depuis data.gouv.fr ou depuis vos propres fichiers
        </p>
      </motion.div>

      {/* Onglets */}
      <motion.div {...fadeUp} className="flex gap-2 p-1 bg-primary-100 rounded-2xl w-fit flex-wrap">
        {TABS.map(({ id, Icon, label, badge, badgeClass }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200
              ${activeTab === id ? 'bg-white text-primary-900 shadow-soft' : 'text-primary-500 hover:text-primary-700'}`}
          >
            <Icon className="w-4 h-4" />
            {label}
            {badge && (
              <span className={`px-2 py-0.5 rounded-full text-xs ${badgeClass}`}>{badge}</span>
            )}
          </button>
        ))}
      </motion.div>

      {/* Contenu selon l'onglet */}
      <AnimatePresence mode="wait">
        {activeTab === 'gouv' ? (
          <motion.div
            key="gouv"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-2xl mb-5">
              <Database className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-700">
                <span className="font-semibold">Source officielle Atout France</span> — 21 255
                hébergements classés en France (hôtels, campings, résidences, villages de vacances).
                Import par lots de 100 avec checkpoint : si l'import s'interrompt, il reprend
                exactement où il s'était arrêté.
              </div>
            </div>
            <GouvImportBlock />
          </motion.div>
        ) : activeTab === 'google' ? (
          <motion.div
            key="google"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <GooglePlacesBlock />
          </motion.div>
        ) : activeTab === 'sirene' ? (
          <motion.div
            key="sirene"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <SireneBlock />
          </motion.div>
        ) : activeTab === 'pappers' ? (
          <motion.div
            key="pappers"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <PappersBlock />
          </motion.div>
        ) : (
          <motion.div
            key="csv"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            {/* Zone de dépôt */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => !file && inputRef.current?.click()}
              className={`card p-8 border-2 border-dashed text-center transition-all duration-200
                ${dragging ? 'border-accent-400 bg-accent-50 scale-[1.01]' : 'border-primary-200 hover:border-accent-400'}
                ${!file ? 'cursor-pointer group' : ''}
              `}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
              />
              <AnimatePresence mode="wait">
                {!file ? (
                  <motion.div
                    key="empty"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <div className="mx-auto w-16 h-16 rounded-2xl bg-accent-100 text-accent-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                      <Upload className="w-8 h-8" />
                    </div>
                    <h3 className="text-lg font-semibold text-primary-900 mb-2">
                      {dragging ? 'Relâchez le fichier ici' : 'Déposez votre fichier ici'}
                    </h3>
                    <p className="text-primary-500 mb-4">
                      CSV ou Excel — colonnes : nom, ville, type
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        inputRef.current?.click();
                      }}
                      className="px-6 py-2 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 transition-colors"
                    >
                      Parcourir les fichiers
                    </button>
                  </motion.div>
                ) : (
                  <motion.div
                    key="file"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-accent-100 text-accent-600 flex items-center justify-center">
                        <FileText className="w-6 h-6" />
                      </div>
                      <div className="text-left">
                        <p className="font-semibold text-primary-900">{file.name}</p>
                        <p className="text-sm text-primary-500">
                          {(file.size / 1024).toFixed(1)} Ko
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          reset();
                        }}
                        className="p-2 rounded-lg hover:bg-primary-100 text-primary-400 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleUpload();
                        }}
                        disabled={loading}
                        className="px-5 py-2 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 transition-colors flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                      >
                        {loading ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" /> Import en cours…
                          </>
                        ) : (
                          <>
                            <Upload className="w-4 h-4" /> Importer
                          </>
                        )}
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Résultats */}
            <AnimatePresence>
              {result && <ImportResultCard result={result} color="green" />}
              {error && <ErrorAlert error={error} />}
            </AnimatePresence>

            {/* Info cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="card p-6">
                <div className="flex items-center gap-3 mb-4">
                  <FileText className="w-5 h-5 text-accent-600" />
                  <h3 className="font-semibold text-primary-900">Format attendu</h3>
                </div>
                <div className="space-y-2 text-sm text-primary-600">
                  <p>
                    • Colonne <span className="font-mono bg-primary-50 px-1 rounded">nom</span> —
                    Nom de l'établissement <span className="text-error-500">(obligatoire)</span>
                  </p>
                  <p>
                    • Colonne <span className="font-mono bg-primary-50 px-1 rounded">ville</span> —
                    Ville (optionnel)
                  </p>
                  <p>
                    • Colonne <span className="font-mono bg-primary-50 px-1 rounded">type</span> —
                    Hôtel, Camping… (optionnel)
                  </p>
                  <p>
                    • Colonne <span className="font-mono bg-primary-50 px-1 rounded">email</span> —
                    Email contact (optionnel)
                  </p>
                </div>
                <button className="mt-4 flex items-center gap-2 text-sm text-accent-600 hover:text-accent-700 font-medium transition-colors">
                  <Download className="w-4 h-4" /> Télécharger un modèle CSV
                </button>
              </div>
              <div className="card p-6">
                <div className="flex items-center gap-3 mb-4">
                  <AlertCircle className="w-5 h-5 text-warning-500" />
                  <h3 className="font-semibold text-primary-900">Bon à savoir</h3>
                </div>
                <div className="space-y-2 text-sm text-primary-600">
                  <p>• Les doublons sont détectés automatiquement</p>
                  <p>
                    • Formats acceptés : <span className="font-mono">.csv</span>,{' '}
                    <span className="font-mono">.xlsx</span>,{' '}
                    <span className="font-mono">.xls</span>
                  </p>
                  <p>• Encodage recommandé : UTF-8</p>
                  <p>• Pas de limite de taille imposée</p>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
