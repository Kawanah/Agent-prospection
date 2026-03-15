import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';
import { API_URL } from '../config';
import {
  Users,
  Search,
  ExternalLink,
  Mail,
  Phone,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  Filter,
  Globe,
  Building2,
  RefreshCw,
  Download,
  Sparkles,
  X,
  Star,
  MapPin,
  Tag,
  Activity,
  Calendar,
} from 'lucide-react';

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

const TYPE_LABELS = {
  hotel: 'Hôtel',
  camping: 'Camping',
  gite: 'Gîte',
  residence: 'Résidence',
  chambre_hotes: "Ch. d'hôtes",
  other: 'Autre',
};

const TYPE_EMOJI = {
  hotel: '🏨',
  camping: '⛺',
  gite: '🏡',
  residence: '🏢',
  chambre_hotes: '🛏️',
  other: '🏠',
};

// ─── Calcul de la qualification ───────────────────────────────────────────────
// Règles (par priorité) :
// 1. has_website=false (confirmé après enrichissement) → SANS SITE
// 2. has_website=null ET website=null → NON ANALYSÉ (pas encore enrichi)
// 3. has_website=null ET website existe (URL connue mais non vérifiée) → À ANALYSER
// 4. has_website=true ou website_quality_score connu → score chaud/tiède/froid
// Les avis Google sont intégrés dans le score backend (google_reviews_count, google_rating).
function getQualification(lead) {
  // Cas 1 : enrichissement confirmé → pas de site web
  if (lead.has_website === false) {
    return {
      label: 'SANS SITE',
      short: 'Sans site',
      bg: 'bg-red-100',
      text: 'text-red-700',
      dot: 'bg-red-500',
      border: 'border-red-200',
      emoji: '🔥',
    };
  }

  // Cas 2 : pas encore analysé du tout (aucune URL, aucune vérification)
  const invalidUrls = ['', '-', 'n/a', 'na', 'none', 'null'];
  const hasValidUrl =
    lead.website &&
    !invalidUrls.includes(lead.website.toLowerCase().trim()) &&
    lead.website.trim().length > 3;

  if (!hasValidUrl && lead.has_website === null) {
    return {
      label: 'NON ANALYSÉ',
      short: 'Non analysé',
      bg: 'bg-slate-100',
      text: 'text-slate-600',
      dot: 'bg-slate-400',
      border: 'border-slate-200',
      emoji: '❓',
    };
  }

  // Cas 3 : URL connue mais site pas encore vérifié
  if (hasValidUrl && lead.has_website === null && lead.website_quality_score === null) {
    return {
      label: 'À ANALYSER',
      short: 'À analyser',
      bg: 'bg-orange-100',
      text: 'text-orange-700',
      dot: 'bg-orange-400',
      border: 'border-orange-200',
      emoji: '⚠️',
    };
  }

  // Cas 4 : lead analysé → qualification par score
  // (le score inclut : qualité site, SEO, GEO, avis Google, taille établissement)
  if (lead.score >= 70) {
    return {
      label: 'CHAUD',
      short: 'Chaud',
      bg: 'bg-red-50',
      text: 'text-red-600',
      dot: 'bg-red-400',
      border: 'border-red-100',
      emoji: '🔥',
    };
  }
  if (lead.score >= 40) {
    return {
      label: 'TIÈDE',
      short: 'Tiède',
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      dot: 'bg-amber-400',
      border: 'border-amber-100',
      emoji: '😐',
    };
  }
  return {
    label: 'FROID',
    short: 'Froid',
    bg: 'bg-blue-50',
    text: 'text-blue-600',
    dot: 'bg-blue-400',
    border: 'border-blue-100',
    emoji: '❄️',
  };
}

function ScoreBadge({ score }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="relative w-8 h-8">
        <svg className="w-8 h-8 -rotate-90" viewBox="0 0 32 32">
          <circle cx="16" cy="16" r="13" fill="none" stroke="#e5e7eb" strokeWidth="3" />
          <circle
            cx="16"
            cy="16"
            r="13"
            fill="none"
            stroke={score >= 70 ? '#ef4444' : score >= 40 ? '#f59e0b' : '#94a3b8'}
            strokeWidth="3"
            strokeDasharray={`${(score / 100) * 81.7} 81.7`}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-primary-800">
          {score}
        </span>
      </div>
    </div>
  );
}

function QualifBadge({ lead }) {
  const q = getQualification(lead);
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${q.bg} ${q.text} ${q.border}`}
    >
      <span className="text-[10px]">{q.emoji}</span>
      {q.short}
    </span>
  );
}

const QUALIF_FILTERS = [
  { value: '', label: 'Tous' },
  { value: 'sans_site', label: '🔥 Sans site' },
  { value: 'a_analyser', label: '⚠️ À analyser' },
  { value: 'non_analyse', label: '❓ Non analysé' },
  { value: 'chaud', label: '🔥 Chaud' },
  { value: 'tiede', label: '😐 Tiède' },
  { value: 'froid', label: '❄️ Froid' },
];

const STATUS_FILTERS = [
  { value: '', label: 'Tous les statuts' },
  { value: 'enriched', label: '✅ Enrichis' },
  { value: 'new', label: '🆕 Nouveaux' },
  { value: 'contacted', label: '📧 Contactés' },
  { value: 'responded', label: '💬 Ont répondu' },
  { value: 'interested', label: '⭐ Intéressés' },
];

const STATUS_LABELS = {
  new: { label: 'Nouveau', cls: 'bg-slate-100 text-slate-600' },
  enriched: { label: 'Enrichi', cls: 'bg-blue-100 text-blue-700' },
  contacted: { label: 'Contacté', cls: 'bg-amber-100 text-amber-700' },
  replied: { label: 'A répondu', cls: 'bg-green-100 text-green-700' },
  converted: { label: 'Converti', cls: 'bg-emerald-100 text-emerald-700' },
  rejected: { label: 'Rejeté', cls: 'bg-red-100 text-red-600' },
};

function LeadDetailModal({ lead, onClose, onEnrich, enrichingId }) {
  const q = getQualification(lead);
  const status = STATUS_LABELS[lead.status] || STATUS_LABELS.new;

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.2 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0 border ${q.bg} ${q.border}`}
            >
              {TYPE_EMOJI[lead.lead_type] || '🏠'}
            </div>
            <div>
              <h2 className="text-lg font-bold text-primary-900 leading-tight">{lead.name}</h2>
              <p className="text-sm text-primary-400">
                {TYPE_LABELS[lead.lead_type] || lead.lead_type}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors ml-2 flex-shrink-0"
          >
            <X className="w-4 h-4 text-primary-500" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${q.bg} ${q.text} ${q.border}`}
            >
              {q.emoji} {q.label}
            </span>
            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${status.cls}`}>
              {status.label}
            </span>
            {lead.score !== undefined && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-primary-100 text-primary-700">
                Score : {lead.score}/100
              </span>
            )}
          </div>

          {/* Localisation */}
          {(lead.city || lead.postal_code || lead.address) && (
            <div className="flex items-start gap-2 text-sm text-primary-700">
              <MapPin className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
              <span>{[lead.address, lead.city, lead.postal_code].filter(Boolean).join(', ')}</span>
            </div>
          )}

          {/* Contact */}
          <div className="grid grid-cols-1 gap-2">
            {lead.email && (
              <a
                href={`mailto:${lead.email}`}
                className="flex items-center gap-2 text-sm text-accent-600 hover:text-accent-700"
              >
                <Mail className="w-4 h-4 flex-shrink-0" />
                {lead.email}
              </a>
            )}
            {lead.phone && (
              <div className="flex items-center gap-2 text-sm text-primary-700">
                <Phone className="w-4 h-4 text-primary-400 flex-shrink-0" />
                {lead.phone}
              </div>
            )}
            {lead.website && !['', '-'].includes(lead.website) && (
              <a
                href={lead.website}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-accent-600 hover:text-accent-700"
              >
                <Globe className="w-4 h-4 flex-shrink-0" />
                <span className="truncate">{lead.website}</span>
                <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-50" />
              </a>
            )}
            {(!lead.website || ['-', ''].includes(lead.website)) && (
              <div className="flex items-center gap-2 text-sm text-red-500 font-medium">
                <Globe className="w-4 h-4 flex-shrink-0" />
                Pas de site web
              </div>
            )}
          </div>

          {/* Google */}
          {(lead.google_rating || lead.google_reviews_count) && (
            <div className="flex items-center gap-3 p-3 bg-amber-50 rounded-xl border border-amber-100">
              <Star className="w-4 h-4 text-amber-500 flex-shrink-0" />
              <div className="text-sm">
                {lead.google_rating && (
                  <span className="font-semibold text-primary-800">{lead.google_rating}/5</span>
                )}
                {lead.google_reviews_count && (
                  <span className="text-primary-500 ml-1">
                    · {lead.google_reviews_count} avis Google
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Classement / étoiles */}
          {lead.star_rating && (
            <div className="flex items-center gap-2 text-sm text-primary-600">
              <Tag className="w-4 h-4 text-primary-400" />
              Classement : {lead.star_rating}
            </div>
          )}

          {/* Site web — qualité */}
          {lead.website_quality_score !== null && lead.website_quality_score !== undefined && (
            <div className="flex items-center gap-2 text-sm text-primary-600">
              <Activity className="w-4 h-4 text-primary-400" />
              Qualité du site : {lead.website_quality_score}/100
            </div>
          )}

          {/* Date */}
          {lead.created_at && (
            <div className="flex items-center gap-2 text-xs text-primary-400">
              <Calendar className="w-3.5 h-3.5" />
              Importé le{' '}
              {new Date(lead.created_at).toLocaleDateString('fr-FR', {
                day: '2-digit',
                month: 'long',
                year: 'numeric',
              })}
            </div>
          )}

          {/* Notes */}
          {lead.notes && (
            <div className="p-3 bg-primary-50 rounded-xl text-sm text-primary-700 italic">
              {lead.notes}
            </div>
          )}

          {/* Actions */}
          <div className="pt-2 border-t border-gray-100 flex gap-2">
            <button
              onClick={() => {
                onEnrich(lead.id, lead.name);
                onClose();
              }}
              disabled={enrichingId === lead.id}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-violet-500 text-white text-sm font-medium hover:bg-violet-600 disabled:opacity-50 transition-colors"
            >
              {enrichingId === lead.id ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              Enrichir ce lead
            </button>
            {lead.email && (
              <a
                href={`mailto:${lead.email}`}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-primary-200 text-sm text-primary-700 hover:bg-primary-50 transition-colors"
              >
                <Mail className="w-4 h-4" /> Contacter
              </a>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [qualifFilter, setQualifFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [enrichingId, setEnrichingId] = useState(null);
  const [toast, setToast] = useState(null);
  const [detailLead, setDetailLead] = useState(null);
  const perPage = 25;

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleExport = () => {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    window.open(`${API_URL}/api/leads/export?${params.toString()}`, '_blank');
  };

  const handleEnrichOne = async (leadId, leadName) => {
    setEnrichingId(leadId);
    try {
      await axios.post(`${API_URL}/api/enrichment/${leadId}`);
      showToast(`${leadName} enrichi avec succès`);
      setTimeout(() => fetchLeads(page, search, statusFilter), 1500);
    } catch {
      showToast("Erreur lors de l'enrichissement");
    } finally {
      setEnrichingId(null);
    }
  };

  const fetchLeads = useCallback(
    async (p = 1, city = '', status = '') => {
      setLoading(true);
      setError(null);
      try {
        const params = { page: p, per_page: perPage };
        if (city) params.city = city;
        if (status) params.status = status;
        const res = await axios.get(`${API_URL}/api/leads/`, { params });
        setLeads(res.data.leads || []);
        setTotal(res.data.total || 0);
      } catch {
        setError(
          'Impossible de charger les leads. Vérifiez que le backend tourne sur le port 8000.'
        );
      } finally {
        setLoading(false);
      }
    },
    [perPage]
  );

  // search est intentionnellement exclu : on ne relance pas au keystroke, seulement sur submit
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchLeads(page, search, statusFilter);
  }, [page, statusFilter, fetchLeads]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    fetchLeads(1, search, statusFilter);
  };

  const handleStatusFilter = (value) => {
    setStatusFilter(value);
    setPage(1);
  };

  // Filtre qualification côté client (leads déjà chargés)
  const filteredLeads = leads.filter((lead) => {
    if (!qualifFilter) return true;
    const q = getQualification(lead);
    if (qualifFilter === 'sans_site') return q.label === 'SANS SITE';
    if (qualifFilter === 'a_analyser') return q.label === 'À ANALYSER';
    if (qualifFilter === 'non_analyse') return q.label === 'NON ANALYSÉ';
    if (qualifFilter === 'chaud') return q.label === 'CHAUD';
    if (qualifFilter === 'tiede') return q.label === 'TIÈDE';
    if (qualifFilter === 'froid') return q.label === 'FROID';
    return true;
  });

  const totalPages = Math.ceil(total / perPage);

  // Compteurs par qualification sur la page courante
  const qualifCounts = leads.reduce((acc, l) => {
    const q = getQualification(l);
    acc[q.label] = (acc[q.label] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Modal fiche détail */}
      <AnimatePresence>
        {detailLead && (
          <LeadDetailModal
            lead={detailLead}
            onClose={() => setDetailLead(null)}
            onEnrich={handleEnrichOne}
            enrichingId={enrichingId}
          />
        )}
      </AnimatePresence>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="fixed top-6 right-6 z-50 flex items-center gap-2 bg-green-600 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* En-tête */}
      <motion.div {...fadeUp} className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-primary-900">Leads</h1>
          <p className="mt-1 text-primary-500">
            {total.toLocaleString('fr-FR')} établissement{total > 1 ? 's' : ''} en base
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchLeads(page, search, statusFilter)}
            className="p-2 rounded-xl border border-primary-200 hover:bg-primary-50 transition-colors"
            title="Rafraîchir"
          >
            <RefreshCw className="w-4 h-4 text-primary-500" />
          </button>
          <button
            onClick={handleExport}
            className="px-4 py-2 rounded-xl border border-primary-200 text-primary-600 hover:bg-primary-50 transition-colors flex items-center gap-2 text-sm"
            title="Exporter en CSV"
          >
            <Download className="w-4 h-4" /> Export CSV
          </button>
          <a
            href="/import"
            className="px-4 py-2 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 transition-colors flex items-center gap-2 text-sm"
          >
            <Users className="w-4 h-4" /> Importer
          </a>
        </div>
      </motion.div>

      {/* Compteurs qualification */}
      {leads.length > 0 && (
        <motion.div {...fadeUp} className="flex gap-3 flex-wrap">
          {[
            {
              key: 'SANS SITE',
              label: '🔥 Sans site',
              bg: 'bg-red-100 border-red-200 text-red-700',
            },
            { key: 'CHAUD', label: '🔥 Chaud', bg: 'bg-red-50 border-red-100 text-red-600' },
            { key: 'TIÈDE', label: '😐 Tiède', bg: 'bg-amber-50 border-amber-100 text-amber-700' },
            { key: 'FROID', label: '❄️ Froid', bg: 'bg-blue-50 border-blue-100 text-blue-600' },
            {
              key: 'À VÉRIFIER',
              label: '⚠️ À vérifier',
              bg: 'bg-orange-50 border-orange-100 text-orange-700',
            },
          ]
            .filter((c) => qualifCounts[c.key])
            .map((c) => (
              <div
                key={c.key}
                className={`px-3 py-1.5 rounded-xl border text-sm font-medium ${c.bg}`}
              >
                {c.label} <span className="font-bold ml-1">{qualifCounts[c.key]}</span>
              </div>
            ))}
        </motion.div>
      )}

      {/* Filtres */}
      <motion.div {...fadeUp} className="card p-4 flex flex-wrap gap-3">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-0">
          <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-50 border border-primary-200 min-w-0">
            <Search className="w-4 h-4 text-primary-400 flex-shrink-0" />
            <input
              className="flex-1 bg-transparent text-sm text-primary-900 placeholder-primary-400 outline-none min-w-0"
              placeholder="Filtrer par ville…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 transition-colors"
          >
            Rechercher
          </button>
          {search && (
            <button
              type="button"
              onClick={() => {
                setSearch('');
                fetchLeads(1, '');
              }}
              className="px-3 py-2 rounded-lg border border-primary-200 text-primary-600 hover:bg-primary-50 text-sm transition-colors"
            >
              Effacer
            </button>
          )}
        </form>

        {/* Filtre statut */}
        <div className="flex items-center gap-1.5">
          <select
            value={statusFilter}
            onChange={(e) => handleStatusFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-primary-200 bg-primary-50 text-primary-700 outline-none cursor-pointer hover:bg-primary-100 transition-colors"
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        {/* Filtre qualification */}
        <div className="flex items-center gap-1.5">
          <Filter className="w-4 h-4 text-primary-400" />
          <div className="flex gap-1 flex-wrap">
            {QUALIF_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setQualifFilter(f.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                  ${qualifFilter === f.value ? 'bg-accent-500 text-white' : 'bg-primary-50 text-primary-600 hover:bg-primary-100'}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Message d'erreur */}
      {error && (
        <motion.div
          {...fadeUp}
          className="card p-4 border border-red-200 bg-red-50 flex items-center gap-3 text-red-600"
        >
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{error}</p>
        </motion.div>
      )}

      {/* Tableau */}
      <motion.div {...fadeUp} className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="w-8 h-8 text-accent-500 animate-spin" />
          </div>
        ) : filteredLeads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <Building2 className="w-12 h-12 text-primary-300 mb-4" />
            <p className="text-primary-500 font-medium">Aucun lead trouvé</p>
            <p className="text-primary-400 text-sm mt-1">
              {qualifFilter
                ? 'Aucun lead pour ce filtre'
                : 'Importez des établissements pour commencer'}
            </p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-primary-50 border-b border-primary-100">
              <tr>
                <th className="text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-5 py-3">
                  Établissement
                </th>
                <th className="text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-5 py-3">
                  Type
                </th>
                <th className="text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-5 py-3">
                  Qualification
                </th>
                <th className="text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-5 py-3">
                  Score
                </th>
                <th className="text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-5 py-3">
                  Contact
                </th>
                <th className="text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-5 py-3">
                  Site web
                </th>
                <th className="text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-5 py-3">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-primary-50">
              {filteredLeads.map((lead) => {
                const q = getQualification(lead);
                return (
                  <tr
                    key={lead.id}
                    onClick={() => setDetailLead(lead)}
                    className="hover:bg-primary-50/40 transition-colors group cursor-pointer"
                  >
                    {/* Établissement */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0 border ${q.bg} ${q.border}`}
                        >
                          <span>{TYPE_EMOJI[lead.lead_type] || '🏠'}</span>
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-primary-900 text-sm truncate max-w-[200px]">
                            {lead.name}
                          </p>
                          {lead.city && (
                            <p className="text-xs text-primary-400 truncate">
                              {lead.city}
                              {lead.postal_code ? ` · ${lead.postal_code}` : ''}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Type */}
                    <td className="px-5 py-3.5">
                      <span className="text-xs text-primary-500 bg-primary-50 px-2 py-1 rounded-lg">
                        {TYPE_LABELS[lead.lead_type] || lead.lead_type}
                        {lead.star_rating && ` · ${lead.star_rating.replace(' étoiles', '★')}`}
                      </span>
                    </td>

                    {/* Qualification */}
                    <td className="px-5 py-3.5">
                      <QualifBadge lead={lead} />
                    </td>

                    {/* Score */}
                    <td className="px-5 py-3.5">
                      <ScoreBadge score={lead.score} />
                    </td>

                    {/* Contact */}
                    <td className="px-5 py-3.5">
                      <div className="flex flex-col gap-0.5">
                        {lead.email ? (
                          <span className="flex items-center gap-1 text-xs text-success-600">
                            <Mail className="w-3 h-3" />
                            <span className="truncate max-w-[120px]">{lead.email}</span>
                          </span>
                        ) : (
                          <span className="text-xs text-primary-300">— email</span>
                        )}
                        {lead.phone && (
                          <span className="flex items-center gap-1 text-xs text-primary-500">
                            <Phone className="w-3 h-3" />
                            {lead.phone}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Site web */}
                    <td className="px-5 py-3.5">
                      {lead.website && !['', '-'].includes(lead.website) ? (
                        <a
                          href={lead.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-accent-600 hover:text-accent-700"
                        >
                          <Globe className="w-3 h-3" />
                          <span className="truncate max-w-[100px]">
                            {lead.website.replace(/^https?:\/\//, '')}
                          </span>
                          <ExternalLink className="w-2.5 h-2.5 opacity-50" />
                        </a>
                      ) : (
                        <span className="text-xs text-red-400 font-medium">Pas de site</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="px-5 py-3.5" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleEnrichOne(lead.id, lead.name)}
                        disabled={enrichingId === lead.id}
                        title="Enrichir ce lead"
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium
                          bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100
                          disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {enrichingId === lead.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Sparkles className="w-3 h-3" />
                        )}
                        Enrichir
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-4 border-t border-primary-100">
            <p className="text-sm text-primary-500">
              {((page - 1) * perPage + 1).toLocaleString('fr-FR')}–
              {Math.min(page * perPage, total).toLocaleString('fr-FR')} sur{' '}
              {total.toLocaleString('fr-FR')}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg border border-primary-200 hover:bg-primary-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4 text-primary-600" />
              </button>
              <span className="text-sm font-medium text-primary-700 min-w-[80px] text-center">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-2 rounded-lg border border-primary-200 hover:bg-primary-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-4 h-4 text-primary-600" />
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
