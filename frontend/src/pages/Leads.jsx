import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { campaignsApi } from '../api/campaigns';
import { enrichmentApi } from '../api/enrichment';
import { leadsApi } from '../api/leads';
import {
  DEPT_NAMES,
  QUALIF_FILTERS,
  STATUS_FILTERS,
  STATUS_LABELS,
  TYPE_EMOJI,
  TYPE_LABELS,
  TYPE_TABS,
  getQualification,
} from '../features/leads/leadMetadata';
import { QualifBadge, ScoreBadge } from '../features/leads/LeadBadges';
import { useToast } from '../hooks/useToast';
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
  Send,
  Target,
} from 'lucide-react';

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

function SelectCampaignModal({ lead, onClose, onSuccess }) {
  const [campaigns, setCampaigns] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    campaignsApi
      .list()
      .then((r) => {
        const active = (r.data.campaigns || []).filter((c) => c.status !== 'completed');
        setCampaigns(active);
        if (active.length > 0) setSelectedId(active[0].id);
      })
      .catch(() => setError('Impossible de charger les campagnes'))
      .finally(() => setLoading(false));
  }, []);

  const handleConfirm = async () => {
    if (!selectedId) return;
    setSending(true);
    setError(null);
    try {
      await campaignsApi.addLeads(selectedId, [lead.id]);
      onSuccess('Lead ajouté à la campagne avec succès');
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'ajout");
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[60] p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.2 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-accent-50">
              <Target className="w-4 h-4 text-accent-600" />
            </div>
            <h3 className="font-bold text-primary-900 text-base">Choisir une campagne</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4 text-primary-500" />
          </button>
        </div>

        <p className="text-sm text-primary-500 mb-4">
          Ajouter <span className="font-semibold text-primary-800">{lead.name}</span> à :
        </p>

        {loading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="w-5 h-5 text-accent-500 animate-spin" />
          </div>
        ) : campaigns.length === 0 ? (
          <div className="text-center py-6">
            <Target className="w-8 h-8 text-primary-300 mx-auto mb-2" />
            <p className="text-sm text-primary-500">Aucune campagne active</p>
            <a
              href="/campaigns"
              className="text-xs text-accent-600 hover:underline mt-1 inline-block"
            >
              Créer une campagne →
            </a>
          </div>
        ) : (
          <div className="space-y-2 mb-5">
            {campaigns.map((c) => (
              <label
                key={c.id}
                className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors
                  ${
                    selectedId === c.id
                      ? 'border-accent-400 bg-accent-50'
                      : 'border-primary-200 hover:bg-primary-50'
                  }`}
              >
                <input
                  type="radio"
                  name="campaign"
                  value={c.id}
                  checked={selectedId === c.id}
                  onChange={() => setSelectedId(c.id)}
                  className="accent-accent-500"
                />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-primary-900 truncate">{c.name}</p>
                  <p className="text-xs text-primary-400 capitalize">
                    {c.channel} · {c.status}
                  </p>
                </div>
              </label>
            ))}
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-red-600 text-xs p-2.5 bg-red-50 rounded-lg border border-red-200 mb-4">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-primary-200 text-primary-600 text-sm font-medium hover:bg-primary-50 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selectedId || sending || campaigns.length === 0}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-accent-500 text-white text-sm font-semibold hover:bg-accent-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Envoyer
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function LeadDetailModal({ lead, onClose, onEnrich, enrichingId, onAddToCampaign, onNotesSaved }) {
  const q = getQualification(lead);
  const status = STATUS_LABELS[lead.status] || STATUS_LABELS.new;
  const [strongArgs, setStrongArgs] = useState([]);
  const [notes, setNotes] = useState(lead.notes || '');
  const [notesSaving, setNotesSaving] = useState(false);
  const [notesSaved, setNotesSaved] = useState(false);

  useEffect(() => {
    setNotes(lead.notes || '');
  }, [lead.id, lead.notes]);

  useEffect(() => {
    if (lead?.id) {
      leadsApi
        .strongArguments(lead.id)
        .then((r) => setStrongArgs(r.data?.arguments || []))
        .catch(() => {});
    }
  }, [lead?.id]);

  const handleSaveNotes = async () => {
    setNotesSaving(true);
    try {
      await leadsApi.updateNotes(lead.id, notes);
      setNotesSaved(true);
      onNotesSaved(lead.id, notes);
      setTimeout(() => setNotesSaved(false), 2000);
    } catch {
      // silencieux
    } finally {
      setNotesSaving(false);
    }
  };

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

          {/* Alerte contact alternatif */}
          {lead.status === 'no_email' && (
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-orange-50 border border-orange-200 text-sm text-orange-800">
              <span className="text-base flex-shrink-0">📞</span>
              <div>
                <p className="font-semibold">Contacter autrement</p>
                <p className="text-xs text-orange-600 mt-0.5">
                  Aucun email trouvé. Utilisez le téléphone ou LinkedIn ci-dessous.
                </p>
              </div>
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
              <a
                href={`tel:${lead.phone.replace(/\s/g, '')}`}
                className={`flex items-center gap-2 text-sm ${lead.status === 'no_email' ? 'text-orange-700 font-semibold hover:text-orange-800' : 'text-primary-700 hover:text-primary-900'}`}
              >
                <Phone
                  className={`w-4 h-4 flex-shrink-0 ${lead.status === 'no_email' ? 'text-orange-500' : 'text-primary-400'}`}
                />
                {lead.phone}
                {lead.status === 'no_email' && (
                  <span className="text-xs text-orange-500 ml-1">← Appeler</span>
                )}
              </a>
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

          {/* Nouvelles Entreprises — Infos RCS */}
          {lead.is_nouvelle_entreprise && (
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-100 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-emerald-800 flex items-center gap-1.5">
                  🆕 Nouvelle Entreprise
                </span>
                {lead.rcs_score != null && (
                  <span
                    className={`text-sm font-bold px-2 py-0.5 rounded-full ${
                      lead.rcs_score >= 4
                        ? 'bg-emerald-200 text-emerald-800'
                        : lead.rcs_score >= 2
                          ? 'bg-teal-100 text-teal-700'
                          : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    RCS {lead.rcs_score}/5
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {lead.forme_juridique && (
                  <div>
                    <span className="text-emerald-500">Forme :</span>{' '}
                    <span className="font-medium text-primary-800">{lead.forme_juridique}</span>
                  </div>
                )}
                {lead.capital != null && (
                  <div>
                    <span className="text-emerald-500">Capital :</span>{' '}
                    <span className="font-medium text-primary-800">
                      {lead.capital.toLocaleString('fr-FR')} €
                    </span>
                  </div>
                )}
                {lead.siren && (
                  <div>
                    <span className="text-emerald-500">SIREN :</span>{' '}
                    <span className="font-mono text-primary-700">{lead.siren}</span>
                  </div>
                )}
              </div>
              {lead.objet_social && (
                <div className="text-xs">
                  <span className="text-emerald-500 font-medium">Objet social :</span>
                  <p className="text-primary-700 mt-0.5 leading-relaxed">{lead.objet_social}</p>
                </div>
              )}
              {lead.bodacc_activite && (
                <div className="text-xs">
                  <span className="text-emerald-500 font-medium">Activité BODACC :</span>
                  <p className="text-primary-700 mt-0.5 leading-relaxed">{lead.bodacc_activite}</p>
                </div>
              )}
              {lead.domiciliation && (
                <div className="text-xs flex items-start gap-1">
                  <span className="text-emerald-500">Domiciliation :</span>
                  <span className="text-primary-700">{lead.domiciliation}</span>
                  {lead.is_domiciliataire && (
                    <span className="ml-1 text-orange-600 font-semibold whitespace-nowrap">
                      ⚠ Domiciliataire
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Score détaillé */}
          {lead.score !== undefined && (
            <div className="p-4 bg-primary-50 rounded-xl border border-primary-100">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-primary-800 flex items-center gap-1.5">
                  <Target className="w-4 h-4 text-accent-500" /> Potentiel commercial
                </span>
                <span
                  className={`text-sm font-bold ${lead.score >= 70 ? 'text-red-600' : lead.score >= 40 ? 'text-amber-600' : 'text-slate-500'}`}
                >
                  {lead.score}/100
                </span>
              </div>
              <div className="space-y-2 text-xs">
                {[
                  {
                    label: 'Présence web',
                    pts: lead.has_website === false ? 35 : lead.has_website === true ? 0 : 15,
                    max: 35,
                    note:
                      lead.has_website === false
                        ? 'Pas de site = fort potentiel'
                        : lead.has_website === true
                          ? 'A déjà un site'
                          : 'Non vérifié',
                  },
                  {
                    label: 'Qualité du site',
                    pts:
                      lead.website_quality_score != null
                        ? Math.round(lead.website_quality_score * 0.4)
                        : null,
                    max: 40,
                    note:
                      lead.website_quality_score != null
                        ? `Score : ${lead.website_quality_score}/100`
                        : 'Non analysé',
                  },
                  {
                    label: 'Avis Google',
                    pts:
                      lead.google_rating != null
                        ? Math.round(
                            ((lead.google_rating / 5) * 0.5 +
                              Math.min((lead.google_reviews_count || 0) / 200, 0.5)) *
                              20
                          )
                        : null,
                    max: 20,
                    note:
                      lead.google_rating != null
                        ? `${lead.google_rating}/5 · ${lead.google_reviews_count ?? 0} avis`
                        : 'Non disponible',
                  },
                  {
                    label: 'Classement / étoiles',
                    pts: lead.star_rating ? 15 : null,
                    max: 15,
                    note: lead.star_rating || 'Non classé',
                  },
                ].map(({ label, pts, max, note }) => (
                  <div key={label}>
                    <div className="flex justify-between mb-1">
                      <span className="text-primary-600">{label}</span>
                      <span className="text-primary-500">
                        {pts != null ? `${pts}/${max}` : '—'}
                      </span>
                    </div>
                    <div className="w-full bg-primary-200 rounded-full h-1.5">
                      <div
                        className="h-1.5 rounded-full bg-accent-400 transition-all"
                        style={{
                          width: pts != null ? `${Math.round((pts / max) * 100)}%` : '0%',
                          opacity: pts != null ? 1 : 0.3,
                        }}
                      />
                    </div>
                    {note && <p className="text-primary-400 mt-0.5">{note}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Arguments forts */}
          {strongArgs.length > 0 && (
            <div className="p-4 bg-red-50/60 rounded-xl border border-red-100">
              <p className="text-sm font-bold text-red-800 mb-2.5 flex items-center gap-1.5">
                🎯 Arguments forts
              </p>
              <div className="space-y-2">
                {strongArgs.slice(0, 4).map((arg, i) => (
                  <div key={arg.key} className="flex items-start gap-2">
                    <span
                      className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                        i === 0 ? 'bg-red-500 text-white' : 'bg-red-200 text-red-700'
                      }`}
                    >
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <p
                        className={`text-xs font-semibold ${i === 0 ? 'text-red-700' : 'text-primary-700'}`}
                      >
                        {arg.label}
                      </p>
                      <p className="text-[11px] text-primary-500 leading-snug mt-0.5">{arg.hook}</p>
                    </div>
                  </div>
                ))}
              </div>
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
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-primary-500 uppercase tracking-wide flex items-center gap-1.5">
              📝 Notes
            </p>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Infos utiles, contexte, retour prospect..."
              rows={3}
              className="w-full px-3 py-2.5 rounded-xl border border-primary-200 bg-primary-50 text-sm text-primary-800 placeholder-primary-300 outline-none focus:border-accent-400 focus:bg-white transition-colors resize-none"
            />
            {notes !== (lead.notes || '') && (
              <button
                onClick={handleSaveNotes}
                disabled={notesSaving}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-500 text-white text-xs font-medium hover:bg-accent-600 disabled:opacity-50 transition-colors"
              >
                {notesSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                {notesSaved ? '✓ Enregistré' : 'Enregistrer'}
              </button>
            )}
          </div>

          {/* Actions */}
          <div className="pt-2 border-t border-gray-100 space-y-2">
            <div className="flex gap-2">
              {!lead.enriched_at ? (
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
                  Enrichir
                </button>
              ) : (
                <div className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-green-50 text-green-600 border border-green-200 text-sm font-medium">
                  <Sparkles className="w-4 h-4" />
                  Déjà enrichi
                </div>
              )}
              {lead.email && (
                <a
                  href={`mailto:${lead.email}`}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-primary-200 text-sm text-primary-700 hover:bg-primary-50 transition-colors"
                >
                  <Mail className="w-4 h-4" /> Contacter
                </a>
              )}
            </div>
            <button
              onClick={() => onAddToCampaign(lead)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 transition-colors"
            >
              <Send className="w-4 h-4" />
              Envoyer en campagne
            </button>
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
  const [typeFilter, setTypeFilter] = useState('');
  const [sortBy, setSortBy] = useState('score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [enrichingId, setEnrichingId] = useState(null);
  const { toast, showToast } = useToast();
  const [detailLead, setDetailLead] = useState(null);
  const [campaignLead, setCampaignLead] = useState(null);
  const [batches, setBatches] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [typeCounts, setTypeCounts] = useState({});
  const [campaignMap, setCampaignMap] = useState({});
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [deleting, setDeleting] = useState(false);
  const [starFilter, setStarFilter] = useState('');
  const perPage = 25;
  const initDone = useRef(false);

  const toggleSelect = (id, e) => {
    e.stopPropagation();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredLeads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredLeads.map((l) => l.id)));
    }
  };

  const handleDeleteSelected = async () => {
    if (!selectedIds.size) return;
    setDeleting(true);
    try {
      await Promise.all([...selectedIds].map((id) => leadsApi.delete(id)));
      showToast(
        `${selectedIds.size} lead${selectedIds.size > 1 ? 's' : ''} supprimé${selectedIds.size > 1 ? 's' : ''}`
      );
      setSelectedIds(new Set());
      fetchLeads(
        page,
        search,
        statusFilter,
        typeFilter,
        sortBy,
        sortOrder,
        selectedBatch,
        starFilter
      );
    } catch {
      showToast('Erreur lors de la suppression', 'red');
    } finally {
      setDeleting(false);
    }
  };

  const handleExport = () => {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    window.open(leadsApi.exportUrl(Object.fromEntries(params)), '_blank');
  };

  const handleEnrichOne = async (leadId, leadName) => {
    setEnrichingId(leadId);
    try {
      await enrichmentApi.single(leadId);
      showToast(`${leadName} enrichi avec succès`);
      // Mise à jour locale immédiate — marque comme enrichi sans attendre le refetch
      setLeads((prev) =>
        prev.map((l) =>
          l.id === leadId
            ? {
                ...l,
                enriched_at: new Date().toISOString(),
                status: l.status === 'new' ? 'enriched' : l.status,
              }
            : l
        )
      );
      setTimeout(
        () =>
          fetchLeads(
            page,
            search,
            statusFilter,
            typeFilter,
            sortBy,
            sortOrder,
            selectedBatch,
            starFilter
          ),
        1500
      );
    } catch {
      showToast("Erreur lors de l'enrichissement");
    } finally {
      setEnrichingId(null);
    }
  };

  const fetchLeads = useCallback(
    async (
      p = 1,
      city = '',
      status = '',
      type = '',
      sort = 'score',
      order = 'desc',
      batchId = null,
      stars = ''
    ) => {
      setLoading(true);
      setError(null);
      try {
        const params = { page: p, per_page: perPage, sort_by: sort, sort_order: order };
        if (city) params.city = city;
        if (status) params.status = status;
        if (type === 'nouvelle_entreprise') {
          params.is_nouvelle_entreprise = true;
        } else {
          params.is_nouvelle_entreprise = false;
          if (type) params.lead_type = type;
        }
        if (batchId) params.batch_id = batchId;
        if (stars) params.star_rating = stars;
        const res = await leadsApi.list(params);
        const loadedLeads = res.data.leads || [];
        setLeads(loadedLeads);
        setTotal(res.data.total || 0);

        // Charger le statut campagne des leads affichés
        if (loadedLeads.length > 0) {
          const ids = loadedLeads.map((l) => l.id).join(',');
          leadsApi
            .campaignStatus(ids)
            .then((r) => setCampaignMap((prev) => ({ ...prev, ...r.data })))
            .catch(() => {});
        }
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

  useEffect(() => {
    // Lecture du batch_id dans l'URL (ex: /leads?batch_id=3)
    const params = new URLSearchParams(window.location.search);
    const urlBatchId = params.get('batch_id');
    if (urlBatchId && !initDone.current) {
      setSelectedBatch(parseInt(urlBatchId));
    }
    initDone.current = true;

    leadsApi
      .batches()
      .then((r) => setBatches(r.data || []))
      .catch(() => {});
    // Fetch des compteurs par type pour les tabs
    leadsApi
      .stats()
      .then((r) => {
        const counts = { ...(r.data?.by_type || {}) };
        if (r.data?.nouvelles_entreprises?.total) {
          counts.nouvelle_entreprise = r.data.nouvelles_entreprises.total;
        }
        setTypeCounts(counts);
      })
      .catch(() => {});
  }, []);

  // search est intentionnellement exclu : on ne relance pas au keystroke, seulement sur submit
  useEffect(() => {
    fetchLeads(
      page,
      search,
      statusFilter,
      typeFilter,
      sortBy,
      sortOrder,
      selectedBatch,
      starFilter
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter, typeFilter, sortBy, sortOrder, selectedBatch, starFilter, fetchLeads]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    fetchLeads(1, search, statusFilter, typeFilter, sortBy, sortOrder, selectedBatch, starFilter);
  };

  const handleStatusFilter = (value) => {
    setStatusFilter(value);
    setPage(1);
  };

  // Filtre qualification côté client (leads déjà chargés)
  const filteredLeads = (() => {
    let result = leads.filter((lead) => {
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
    // Dans la vue "Tous" : trier par priorité de qualification
    if (!typeFilter) {
      const QUALIF_ORDER = {
        'SANS SITE': 0,
        CHAUD: 1,
        TIÈDE: 2,
        'À ANALYSER': 3,
        'NON ANALYSÉ': 4,
        FROID: 5,
      };
      result = [...result].sort((a, b) => {
        const qa = getQualification(a).label;
        const qb = getQualification(b).label;
        return (QUALIF_ORDER[qa] ?? 99) - (QUALIF_ORDER[qb] ?? 99);
      });
    }
    return result;
  })();

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
            onAddToCampaign={(lead) => {
              setDetailLead(null);
              setCampaignLead(lead);
            }}
            onNotesSaved={(leadId, newNotes) => {
              setLeads((prev) =>
                prev.map((l) => (l.id === leadId ? { ...l, notes: newNotes } : l))
              );
              setDetailLead((prev) => (prev ? { ...prev, notes: newNotes } : prev));
            }}
          />
        )}
      </AnimatePresence>

      {/* Modal sélection campagne */}
      <AnimatePresence>
        {campaignLead && (
          <SelectCampaignModal
            lead={campaignLead}
            onClose={() => setCampaignLead(null)}
            onSuccess={(msg) => {
              showToast(msg);
              // Rafraîchir le statut campagne immédiatement
              const ids = leads.map((l) => l.id).join(',');
              if (ids)
                leadsApi
                  .campaignStatus(ids)
                  .then((r) => setCampaignMap(r.data))
                  .catch(() => {});
            }}
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
            className={`fixed top-6 right-6 z-50 flex items-center gap-2 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg ${
              toast.color === 'red' ? 'bg-red-600' : 'bg-green-600'
            }`}
          >
            {toast.msg}
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
            onClick={() =>
              fetchLeads(
                page,
                search,
                statusFilter,
                typeFilter,
                sortBy,
                sortOrder,
                selectedBatch,
                starFilter
              )
            }
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

      {/* Tabs par type d'établissement */}
      <motion.div {...fadeUp} className="flex gap-1.5 flex-wrap">
        {TYPE_TABS.map((tab) => {
          const count =
            tab.value === ''
              ? Object.values(typeCounts).reduce((a, b) => a + b, 0)
              : typeCounts[tab.value] || 0;
          const active = typeFilter === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => {
                setTypeFilter(tab.value);
                setPage(1);
              }}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-all duration-150 ${
                active
                  ? tab.activeClass
                  : 'bg-white text-primary-600 border-primary-200 hover:bg-primary-50'
              }`}
            >
              <span>{tab.emoji}</span>
              <span>{tab.label}</span>
              {count > 0 && (
                <span
                  className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                    active ? 'bg-white/20 text-white' : 'bg-primary-100 text-primary-500'
                  }`}
                >
                  {count.toLocaleString('fr-FR')}
                </span>
              )}
            </button>
          );
        })}
      </motion.div>

      {/* Filtres rapides par statut */}
      <motion.div {...fadeUp} className="flex gap-2 flex-wrap items-center">
        <span className="text-xs text-primary-400 font-medium">Statut :</span>
        {[
          {
            value: '',
            label: 'Tous',
            emoji: '',
            cls: 'bg-primary-800 text-white border-primary-800',
            inactiveExtra: '',
          },
          {
            value: 'enriched',
            label: 'Enrichis',
            emoji: '✅',
            cls: 'bg-green-600 text-white border-green-600',
            inactiveExtra: '',
          },
          {
            value: 'new',
            label: 'Nouveaux',
            emoji: '🆕',
            cls: 'bg-slate-600 text-white border-slate-600',
            inactiveExtra: '',
          },
          {
            value: 'no_email',
            label: 'Contact tél/LinkedIn',
            emoji: '📞',
            cls: 'bg-orange-500 text-white border-orange-500',
            inactiveExtra: '',
          },
          {
            value: 'contacted',
            label: 'Contactés',
            emoji: '📧',
            cls: 'bg-amber-500 text-white border-amber-500',
            inactiveExtra: '',
          },
          {
            value: 'responded',
            label: 'Ont répondu',
            emoji: '💬',
            cls: 'bg-blue-600 text-white border-blue-600',
            inactiveExtra: '',
          },
        ].map(({ value, label, emoji, cls }) => {
          const active = statusFilter === value;
          return (
            <button
              key={value}
              onClick={() => {
                handleStatusFilter(value);
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all duration-150 ${
                active ? cls : 'bg-white text-primary-600 border-primary-200 hover:bg-primary-50'
              }`}
            >
              {emoji && <span>{emoji}</span>}
              <span>{label}</span>
            </button>
          );
        })}
      </motion.div>

      {/* Lots d'import */}
      {batches.length > 0 && (
        <motion.div {...fadeUp}>
          <p className="text-xs font-semibold text-primary-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <span>📦</span> Lots d'import
          </p>
          <div className="flex gap-2 flex-wrap items-center">
            <button
              onClick={() => {
                setSelectedBatch(null);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                selectedBatch === null
                  ? 'bg-accent-500 text-white border-accent-500'
                  : 'bg-white text-primary-600 border-primary-200 hover:bg-primary-50'
              }`}
            >
              Tous les lots
            </button>
            {batches.map((b) => {
              const date = new Date(b.created_at).toLocaleDateString('fr-FR', {
                day: '2-digit',
                month: 'short',
                year: '2-digit',
              });
              const typeEmojis = {
                hotel: '🏨',
                camping: '⛺',
                gite: '🏡',
                chambre_hotes: '🛏️',
                residence: '🏢',
                activite: '🎯',
                other: '🏠',
              };
              const typeStr = (b.types || [])
                .slice(0, 3)
                .map((t) => typeEmojis[t] || '🏠')
                .join('');

              // Libellé géographique : départements si disponibles, sinon nom du lot
              const depts = b.departments || [];
              const deptLabel =
                depts.length > 0
                  ? depts.map((d) => `${d} — ${DEPT_NAMES[d] || d}`).join(', ')
                  : b.name?.split('—')[0]?.trim() || `Lot #${b.id}`;

              // Sous-titre court pour l'affichage condensé dans le badge
              const deptShort =
                depts.length > 0 ? depts.map((d) => `Dept. ${d}`).join(' · ') : null;

              const active = selectedBatch === b.id;
              const enrichPct =
                b.total_leads > 0 ? Math.round((b.enriched / b.total_leads) * 100) : 0;
              return (
                <button
                  key={b.id}
                  onClick={() => {
                    setSelectedBatch(b.id);
                    setPage(1);
                  }}
                  title={`${deptLabel}\n${b.total_leads} leads · ${b.enriched} enrichis · ${b.contacted} contactés`}
                  className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-left transition-all ${
                    active
                      ? 'border-accent-500 bg-accent-50 shadow-sm ring-1 ring-accent-200'
                      : 'border-primary-200 bg-white hover:bg-primary-50'
                  }`}
                >
                  <span className="text-base leading-none">{typeStr || '📦'}</span>
                  <div className="min-w-0">
                    <p
                      className={`text-xs font-bold leading-tight truncate max-w-[160px] ${active ? 'text-accent-700' : 'text-primary-800'}`}
                    >
                      {deptShort || deptLabel}
                    </p>
                    <p className="text-[10px] text-primary-400 truncate max-w-[160px]">
                      {b.total_leads} leads · {date}
                      {enrichPct > 0 ? (
                        <span className="text-green-500 ml-1">· {enrichPct}%</span>
                      ) : null}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* Compteurs qualification */}
      {leads.length > 0 && (
        <motion.div {...fadeUp} className="flex gap-3 flex-wrap">
          {[
            {
              key: 'SANS SITE',
              label: '🔥 Sans site',
              bg: 'bg-red-100 border-red-200 text-red-700',
            },
            {
              key: 'PRIORITAIRE',
              label: '🔥 Prioritaire RCS',
              bg: 'bg-emerald-100 border-emerald-200 text-emerald-700',
            },
            {
              key: 'INTÉRESSANT',
              label: '👀 Intéressant RCS',
              bg: 'bg-teal-50 border-teal-100 text-teal-700',
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
      {/* Ligne 1 : Recherche */}
      <motion.div {...fadeUp} className="card p-4">
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-50 border border-primary-200">
            <Search className="w-4 h-4 text-primary-400 flex-shrink-0" />
            <input
              className="flex-1 bg-transparent text-sm text-primary-900 placeholder-primary-400 outline-none"
              placeholder="Rechercher par ville…"
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
                fetchLeads(
                  1,
                  '',
                  statusFilter,
                  typeFilter,
                  sortBy,
                  sortOrder,
                  selectedBatch,
                  starFilter
                );
              }}
              className="px-3 py-2 rounded-lg border border-primary-200 text-primary-600 hover:bg-primary-50 text-sm transition-colors"
            >
              Effacer
            </button>
          )}
        </form>
      </motion.div>

      {/* Ligne 2 : Filtres & Tri */}
      <motion.div {...fadeUp} className="card p-4 flex items-center gap-3 flex-wrap">
        {/* Type — géré par les tabs ci-dessus, affiché comme badge actif ici */}
        {typeFilter && (
          <button
            onClick={() => {
              setTypeFilter('');
              setPage(1);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-primary-300 bg-primary-100 text-primary-700 hover:bg-primary-200 transition-colors"
          >
            {TYPE_EMOJI[typeFilter] || '🏠'} {TYPE_LABELS[typeFilter] || typeFilter}
            <X className="w-3 h-3 ml-0.5" />
          </button>
        )}

        {/* Tri */}
        <select
          value={`${sortBy}_${sortOrder}`}
          onChange={(e) => {
            const val = e.target.value;
            if (val === 'enriched_first') {
              handleStatusFilter('enriched');
              setSortBy('score');
              setSortOrder('desc');
              setPage(1);
            } else {
              const [s, o] = val.split('_');
              setSortBy(s);
              setSortOrder(o);
              setPage(1);
            }
          }}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-primary-200 bg-primary-50 text-primary-700 outline-none cursor-pointer hover:bg-primary-100 transition-colors"
        >
          <option value="score_desc">Score ↓</option>
          <option value="score_asc">Score ↑</option>
          <option value="created_at_desc">Plus récents</option>
          <option value="created_at_asc">Plus anciens</option>
          <option value="name_asc">Nom A→Z</option>
          <option value="name_desc">Nom Z→A</option>
          <option value="enriched_first">✅ Enrichis d'abord</option>
        </select>

        {/* Filtre étoiles */}
        <div className="flex items-center gap-1.5">
          <Star className="w-4 h-4 text-amber-400" />
          <div className="flex gap-1">
            <button
              onClick={() => {
                setStarFilter('');
                setPage(1);
              }}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                starFilter === ''
                  ? 'bg-amber-500 text-white'
                  : 'bg-primary-50 text-primary-600 hover:bg-primary-100'
              }`}
            >
              Toutes
            </button>
            {['1', '2', '3', '4', '5'].map((s) => (
              <button
                key={s}
                onClick={() => {
                  setStarFilter(starFilter === s ? '' : s);
                  setPage(1);
                }}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-0.5 ${
                  starFilter === s
                    ? 'bg-amber-500 text-white'
                    : 'bg-primary-50 text-primary-600 hover:bg-primary-100'
                }`}
              >
                {s} {'★'}
              </button>
            ))}
          </div>
        </div>

        {/* Séparateur visuel */}
        <div className="w-px h-5 bg-primary-200" />

        {/* Qualification */}
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

      {/* Barre d'actions sélection */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 bg-primary-900 text-white rounded-2xl shadow-2xl"
          >
            <span className="text-sm font-semibold">
              {selectedIds.size} sélectionné{selectedIds.size > 1 ? 's' : ''}
            </span>
            <div className="w-px h-4 bg-white/20" />
            <button
              onClick={() => setSelectedIds(new Set())}
              className="text-xs text-white/60 hover:text-white transition-colors"
            >
              Désélectionner
            </button>
            <button
              onClick={handleDeleteSelected}
              disabled={deleting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {deleting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <X className="w-3.5 h-3.5" />
              )}
              Supprimer
            </button>
          </motion.div>
        )}
      </AnimatePresence>

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
          <div className="w-full overflow-hidden">
            <table className="w-full table-fixed">
              <thead className="bg-primary-50 border-b border-primary-100">
                <tr>
                  <th className="w-9 px-2 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={
                        filteredLeads.length > 0 && selectedIds.size === filteredLeads.length
                      }
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded accent-accent-500 cursor-pointer"
                    />
                  </th>
                  <th className="w-[26%] text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-3 py-3">
                    Établissement
                  </th>
                  <th className="w-[10%] text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-2 py-3 hidden xl:table-cell">
                    Type
                  </th>
                  <th className="w-[14%] text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-2 py-3">
                    Qualification
                  </th>
                  <th
                    className="w-[10%] text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-2 py-3 cursor-pointer hover:text-accent-600 select-none"
                    onClick={() => {
                      setSortBy('score');
                      setSortOrder(sortBy === 'score' && sortOrder === 'desc' ? 'asc' : 'desc');
                      setPage(1);
                    }}
                    title="Cliquer pour trier"
                  >
                    Potentiel {sortBy === 'score' ? (sortOrder === 'desc' ? '↓' : '↑') : '↕'}
                  </th>
                  <th className="w-[18%] text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-2 py-3 hidden 2xl:table-cell">
                    Contact
                  </th>
                  <th className="w-[15%] text-left text-xs font-semibold text-primary-500 uppercase tracking-wider px-2 py-3 hidden 2xl:table-cell">
                    Site web
                  </th>
                  <th className="w-[96px] text-center text-xs font-semibold text-primary-500 uppercase tracking-wider px-2 py-3 bg-primary-50">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-primary-50">
                {filteredLeads.map((lead) => {
                  const q = getQualification(lead);
                  const camp = campaignMap[String(lead.id)];
                  return (
                    <>
                      <tr
                        key={lead.id}
                        onClick={() => setDetailLead(lead)}
                        className={`transition-colors group cursor-pointer ${
                          lead.is_nouvelle_entreprise
                            ? selectedIds.has(lead.id)
                              ? 'bg-emerald-100'
                              : 'bg-emerald-50/60 hover:bg-emerald-50'
                            : selectedIds.has(lead.id)
                              ? 'bg-accent-50'
                              : 'hover:bg-primary-50/40'
                        }`}
                        style={
                          lead.is_nouvelle_entreprise ? { boxShadow: 'inset 3px 0 0 #10b981' } : {}
                        }
                      >
                        {/* Checkbox */}
                        <td className="w-9 px-2 py-3.5" onClick={(e) => toggleSelect(lead.id, e)}>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(lead.id)}
                            onChange={() => {}}
                            className="w-4 h-4 rounded accent-accent-500 cursor-pointer"
                          />
                        </td>

                        {/* Établissement */}
                        <td className="px-3 py-3.5">
                          <div className="flex items-center gap-3">
                            <div className="relative flex-shrink-0">
                              <div
                                className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm border ${
                                  lead.is_nouvelle_entreprise
                                    ? 'bg-emerald-100 border-emerald-200'
                                    : `${q.bg} ${q.border}`
                                }`}
                              >
                                <span>
                                  {lead.is_nouvelle_entreprise
                                    ? '🆕'
                                    : TYPE_EMOJI[lead.lead_type] || '🏠'}
                                </span>
                              </div>
                              {lead.enriched_at && (
                                <span
                                  className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-green-500 rounded-full border-2 border-white"
                                  title="Enrichi"
                                />
                              )}
                              {lead.notes && (
                                <span
                                  className="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-amber-400 rounded-full border-2 border-white flex items-center justify-center"
                                  title={lead.notes}
                                >
                                  <span className="text-[7px] leading-none">📝</span>
                                </span>
                              )}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <p
                                  className={`font-medium text-sm truncate max-w-[130px] xl:max-w-[170px] 2xl:max-w-[210px] ${lead.is_nouvelle_entreprise ? 'text-emerald-900' : 'text-primary-900'}`}
                                >
                                  {lead.name}
                                </p>
                                {lead.is_nouvelle_entreprise && lead.forme_juridique && (
                                  <span className="text-[10px] font-bold text-emerald-600 bg-emerald-100 px-1.5 py-0.5 rounded-md border border-emerald-200 whitespace-nowrap">
                                    {lead.forme_juridique}
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-primary-400 truncate">
                                {lead.city}
                                {lead.postal_code ? ` · ${lead.postal_code}` : ''}
                                {lead.is_nouvelle_entreprise && lead.capital != null && (
                                  <span className="ml-1.5 text-emerald-600 font-medium">
                                    · {lead.capital.toLocaleString('fr-FR')} € capital
                                  </span>
                                )}
                                {!lead.is_nouvelle_entreprise && lead.status === 'enriched' && (
                                  <span className="ml-1.5 text-green-600 font-medium">
                                    · enrichi
                                  </span>
                                )}
                              </p>
                              {lead.is_nouvelle_entreprise && lead.objet_social && (
                                <p className="text-[11px] text-emerald-700/80 truncate max-w-[240px] mt-0.5 italic">
                                  {lead.objet_social.slice(0, 60)}
                                  {lead.objet_social.length > 60 ? '…' : ''}
                                </p>
                              )}
                              {camp && (
                                <p className="text-[10px] mt-0.5 truncate max-w-[200px]">
                                  <span
                                    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md font-medium ${
                                      camp.message_status === 'sent' ||
                                      camp.message_status === 'delivered'
                                        ? 'bg-blue-50 text-blue-600'
                                        : camp.message_status === 'queued'
                                          ? 'bg-amber-50 text-amber-600'
                                          : 'bg-primary-50 text-primary-500'
                                    }`}
                                  >
                                    {camp.message_status === 'sent' ||
                                    camp.message_status === 'delivered'
                                      ? '📨'
                                      : camp.message_status === 'queued'
                                        ? '⏳'
                                        : '📋'}
                                    {camp.campaign_name}
                                  </span>
                                </p>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Type */}
                        <td className="px-2 py-3.5 hidden xl:table-cell">
                          <div className="flex flex-col gap-1">
                            {lead.is_nouvelle_entreprise ? (
                              <span className="text-xs text-emerald-700 bg-emerald-100 border border-emerald-200 px-2 py-1 rounded-lg font-semibold">
                                🆕 Nlle Entreprise
                              </span>
                            ) : (
                              <span className="text-xs text-primary-500 bg-primary-50 px-2 py-1 rounded-lg">
                                {TYPE_LABELS[lead.lead_type] || lead.lead_type}
                                {lead.star_rating &&
                                  ` · ${lead.star_rating.replace(' étoiles', '★')}`}
                              </span>
                            )}
                            {lead.is_nouvelle_entreprise && (
                              <span className="text-[10px] text-primary-400">
                                {TYPE_LABELS[lead.lead_type] || lead.lead_type}
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Qualification */}
                        <td className="px-2 py-3.5">
                          <QualifBadge lead={lead} />
                        </td>

                        {/* Score / Potentiel */}
                        <td className="px-2 py-3.5">
                          <ScoreBadge score={lead.score} lead={lead} />
                        </td>

                        {/* Contact */}
                        <td className="px-2 py-3.5 hidden 2xl:table-cell">
                          <div className="flex flex-col gap-0.5">
                            {lead.email ? (
                              <span className="flex items-center gap-1 text-xs text-success-600">
                                <Mail className="w-3 h-3" />
                                <span className="truncate max-w-[95px] xl:max-w-[130px]">
                                  {lead.email}
                                </span>
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
                        <td className="px-2 py-3.5 hidden 2xl:table-cell">
                          {lead.website && !['', '-'].includes(lead.website) ? (
                            <a
                              href={lead.website}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-xs text-accent-600 hover:text-accent-700"
                            >
                              <Globe className="w-3 h-3" />
                              <span className="truncate max-w-[80px] xl:max-w-[110px]">
                                {lead.website.replace(/^https?:\/\//, '')}
                              </span>
                              <ExternalLink className="w-2.5 h-2.5 opacity-50" />
                            </a>
                          ) : (
                            <span className="text-xs text-red-400 font-medium">Pas de site</span>
                          )}
                        </td>

                        {/* Actions */}
                        <td
                          className="w-[96px] px-2 py-3.5 whitespace-nowrap"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="flex items-center justify-center gap-2">
                            {!lead.enriched_at ? (
                              <button
                                onClick={() => handleEnrichOne(lead.id, lead.name)}
                                disabled={enrichingId === lead.id}
                                title="Enrichir ce lead"
                                className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-xs font-medium
                              bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100
                              disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                              >
                                {enrichingId === lead.id ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Sparkles className="w-3 h-3" />
                                )}
                              </button>
                            ) : (
                              <span
                                title="Lead enrichi"
                                className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-xs font-medium bg-green-50 text-green-600 border border-green-200"
                              >
                                <Sparkles className="w-3 h-3" />
                              </span>
                            )}
                            <button
                              onClick={() => setCampaignLead(lead)}
                              title="Envoyer en campagne"
                              className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-xs font-medium
                            bg-accent-50 text-accent-700 border border-accent-200 hover:bg-accent-100
                            transition-colors"
                            >
                              <Send className="w-3 h-3" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
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
              <div className="flex items-center gap-1.5 text-sm text-primary-700">
                <input
                  type="number"
                  min={1}
                  max={totalPages}
                  value={page}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (val >= 1 && val <= totalPages) setPage(val);
                  }}
                  className="w-14 text-center border border-primary-200 rounded-lg px-2 py-1 text-sm font-medium text-primary-800 outline-none focus:border-accent-400 focus:ring-1 focus:ring-accent-200"
                />
                <span className="text-primary-400">/ {totalPages}</span>
              </div>
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
