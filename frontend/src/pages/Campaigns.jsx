import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Target,
  Play,
  Pause,
  Plus,
  Mail,
  Linkedin,
  Pencil,
  Loader2,
  AlertCircle,
  X,
  CheckCircle,
  RefreshCw,
  Send,
  Clock,
  Zap,
  BarChart3,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Users,
  Star,
  Globe,
  Trash2,
} from 'lucide-react';
import { campaignsApi } from '../api/campaigns';
import { leadsApi } from '../api/leads';
import { messagesApi } from '../api/messages';
import { useToast } from '../hooks/useToast';

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

const STATUS_STYLE = {
  draft: { label: 'Brouillon', bg: 'bg-gray-100 text-gray-600' },
  running: { label: 'Active', bg: 'bg-green-100 text-green-700' },
  paused: { label: 'En pause', bg: 'bg-amber-100 text-amber-700' },
  completed: { label: 'Terminée', bg: 'bg-blue-100 text-blue-700' },
};

// ─── Modal nouvelle campagne ──────────────────────────────────────────────────
function NewCampaignModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [channel, setChannel] = useState('email');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await campaignsApi.create({ name, channel });
      onCreate(res.data);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la création');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-primary-900">Nouvelle campagne</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-primary-100 transition-colors"
          >
            <X className="w-4 h-4 text-primary-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-primary-700 mb-1.5">
              Nom de la campagne
            </label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex: Hôtels Paris — Printemps 2026"
              className="w-full px-3 py-2.5 rounded-xl border border-primary-200 text-sm text-primary-900 placeholder-primary-400
                         focus:outline-none focus:ring-2 focus:ring-accent-400 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-primary-700 mb-1.5">Canal</label>
            <div className="flex gap-3">
              {[
                { value: 'email', label: 'Email' },
                { value: 'linkedin', label: 'LinkedIn' },
              ].map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setChannel(value)}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border text-sm font-medium transition-colors
                    ${
                      channel === value
                        ? 'bg-accent-500 text-white border-accent-500'
                        : 'bg-primary-50 text-primary-600 border-primary-200 hover:bg-primary-100'
                    }`}
                >
                  {value === 'email' ? (
                    <Mail className="w-4 h-4" />
                  ) : (
                    <Linkedin className="w-4 h-4" />
                  )}
                  {label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-600 text-sm p-3 bg-red-50 rounded-xl border border-red-200">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-xl border border-primary-200 text-primary-600 text-sm font-medium hover:bg-primary-50 transition-colors"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="flex-1 py-2.5 rounded-xl bg-accent-500 text-white text-sm font-semibold hover:bg-accent-600 transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Créer
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ─── Panneau file d'attente ───────────────────────────────────────────────────
function QueuePanel({ onToast, onRefreshCampaigns }) {
  const [stats, setStats] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await campaignsApi.queueStats();
      setStats(res.data);
    } catch {
      // silencieux
    }
  }, []);

  // Auto-refresh toutes les 30s
  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const handleProcess = async () => {
    setProcessing(true);
    setLastResult(null);
    try {
      const res = await campaignsApi.processQueue();
      setLastResult(res.data);
      onToast(
        res.data.quota_reached
          ? `Quota journalier atteint (${res.data.sent ?? 0} envoyés)`
          : `${res.data.sent ?? 0} email(s) envoyés`
      );
      await fetchStats();
      onRefreshCampaigns(); // mettre à jour les stats des campagnes
    } catch {
      onToast('Erreur lors du traitement');
    } finally {
      setProcessing(false);
    }
  };

  if (!stats) return null;

  const hasQueue = stats.queued_total > 0;
  const emailDeliveryEnabled = Boolean(stats.email_delivery_enabled);

  return (
    <motion.div {...fadeUp} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-accent-50 text-accent-600">
            <Send className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-primary-900 text-sm">File d'envoi</h3>
          </div>
        </div>
        <button
          onClick={fetchStats}
          className="p-1.5 rounded-lg hover:bg-primary-50 transition-colors"
          title="Rafraîchir"
        >
          <RefreshCw className="w-3.5 h-3.5 text-primary-400" />
        </button>
      </div>

      {/* Explication */}
      <p className="text-xs text-primary-400 mb-4">
        Les messages générés par vos campagnes sont planifiés ici. En phase développement/test,
        aucun email réel ne part.
      </p>

      {!emailDeliveryEnabled && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <p>
            Mode simulation actif : la file peut être préparée, mais le traitement réel des emails
            est désactivé.
          </p>
        </div>
      )}

      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          {
            iconKey: 'clock',
            label: 'Planifiés',
            tooltip: "Messages générés, en attente d'envoi",
            value: stats.queued_total,
            color: 'text-amber-600 bg-amber-50',
          },
          {
            iconKey: 'zap',
            label: 'Prêts maintenant',
            tooltip: "Dont l'heure d'envoi est passée",
            value: stats.ready_now,
            color: 'text-accent-600 bg-accent-50',
          },
          {
            iconKey: 'send',
            label: "Envoyés aujourd'hui",
            tooltip: 'Emails envoyés depuis minuit',
            value: stats.sent_today,
            color: 'text-green-600 bg-green-50',
          },
          {
            iconKey: 'bar',
            label: 'Quota restant',
            tooltip: `Limite : 50 emails/jour`,
            value: stats.quota_remaining_today,
            color: 'text-primary-600 bg-primary-50',
          },
        ].map(({ iconKey, label, value, color, tooltip }) => {
          const icons = { clock: Clock, zap: Zap, send: Send, bar: BarChart3 };
          const IconComp = icons[iconKey];
          return (
            <div key={label} className="text-center p-3 rounded-xl bg-gray-50" title={tooltip}>
              <div className={`inline-flex p-1.5 rounded-lg mb-1.5 ${color}`}>
                <IconComp className="w-3.5 h-3.5" />
              </div>
              <p className="text-xl font-bold text-primary-900">{value}</p>
              <p className="text-xs text-primary-500 leading-tight">{label}</p>
            </div>
          );
        })}
      </div>

      {lastResult && (
        <div
          className={`mb-3 text-xs p-2.5 rounded-lg ${lastResult.quota_reached ? 'bg-amber-50 text-amber-700' : 'bg-green-50 text-green-700'}`}
        >
          {lastResult.message}
        </div>
      )}

      <button
        onClick={handleProcess}
        disabled={
          processing || !hasQueue || stats.quota_remaining_today === 0 || !emailDeliveryEnabled
        }
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-accent-500 text-white text-sm font-semibold
                   hover:bg-accent-600 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {processing ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" /> Envoi en cours…
          </>
        ) : !emailDeliveryEnabled ? (
          'Envoi désactivé — mode développement/test'
        ) : stats.quota_remaining_today === 0 ? (
          'Quota journalier atteint — reprise demain'
        ) : !hasQueue ? (
          'Aucun message planifié'
        ) : (
          <>
            <Play className="w-4 h-4" /> Envoyer maintenant ({stats.ready_now} prêts sur{' '}
            {stats.queued_total} planifiés)
          </>
        )}
      </button>
    </motion.div>
  );
}

// ─── Panneau messages d'une campagne ─────────────────────────────────────────
function CampaignMessages({ campaignId, onRemoved }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [leadNames, setLeadNames] = useState({});
  const [removingLeadId, setRemovingLeadId] = useState(null);

  const fetchMsgs = useCallback(async () => {
    try {
      const res = await messagesApi.list({ campaign_id: campaignId, per_page: 50 });
      const msgs = res.data.messages || [];
      setMessages(msgs);
      const uniqueIds = [...new Set(msgs.map((m) => m.lead_id).filter(Boolean))];
      if (uniqueIds.length > 0) {
        try {
          const r = await leadsApi.names(uniqueIds.join(','));
          setLeadNames(r.data);
        } catch {
          /* fallback */
        }
      }
    } catch {
      /* silencieux */
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    fetchMsgs();
  }, [fetchMsgs]);

  const handleRemoveLead = async (leadId, leadName) => {
    if (
      !window.confirm(
        `Retirer "${leadName}" de cette campagne ?\nSes messages planifiés seront annulés.`
      )
    )
      return;
    setRemovingLeadId(leadId);
    try {
      await campaignsApi.removeLead(campaignId, leadId);
      setMessages((prev) => prev.filter((m) => m.lead_id !== leadId));
      onRemoved?.(`"${leadName}" retiré de la campagne`);
    } catch (err) {
      onRemoved?.(err.response?.data?.detail || 'Impossible de retirer ce lead (déjà envoyé ?)');
    } finally {
      setRemovingLeadId(null);
    }
  };

  const STATUS_MSG = {
    draft: { label: 'Brouillon', cls: 'bg-gray-100 text-gray-600' },
    queued: { label: 'Planifié', cls: 'bg-amber-100 text-amber-700' },
    sent: { label: 'Envoyé', cls: 'bg-blue-100 text-blue-700' },
    opened: { label: 'Ouvert', cls: 'bg-green-100 text-green-700' },
    failed: { label: 'Échec', cls: 'bg-red-100 text-red-600' },
  };

  if (loading)
    return (
      <div className="flex justify-center py-4">
        <Loader2 className="w-5 h-5 text-accent-500 animate-spin" />
      </div>
    );
  if (messages.length === 0)
    return (
      <p className="text-sm text-primary-400 py-3 text-center">Aucun message dans cette campagne</p>
    );

  // Grouper par lead pour n'afficher qu'une ligne par lead
  const byLead = messages.reduce((acc, msg) => {
    if (!acc[msg.lead_id]) acc[msg.lead_id] = { msgs: [], hasQueued: false };
    acc[msg.lead_id].msgs.push(msg);
    if (msg.status === 'queued') acc[msg.lead_id].hasQueued = true;
    return acc;
  }, {});

  return (
    <div className="mt-4 border-t border-gray-100 pt-4 space-y-2">
      <p className="text-xs font-semibold text-primary-500 uppercase tracking-wider mb-3">
        {Object.keys(byLead).length} lead{Object.keys(byLead).length > 1 ? 's' : ''} ·{' '}
        {messages.length} message{messages.length > 1 ? 's' : ''}
      </p>
      {Object.entries(byLead).map(([leadId, { msgs, hasQueued }]) => {
        const lid = parseInt(leadId);
        const latestMsg = msgs[msgs.length - 1];
        const s = STATUS_MSG[latestMsg.status] || STATUS_MSG.draft;
        const name = leadNames[lid] || `Lead #${lid}`;
        return (
          <div
            key={leadId}
            className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5 text-sm group"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="font-medium text-primary-800 truncate max-w-[200px]">{name}</span>
              {msgs.length > 1 && (
                <span className="text-xs text-primary-400 bg-primary-100 px-1.5 py-0.5 rounded-md">
                  {msgs.length} msg
                </span>
              )}
              {latestMsg.subject && (
                <span className="text-primary-400 truncate max-w-[220px] hidden md:block text-xs">
                  — {latestMsg.subject}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${s.cls}`}>
                {s.label}
              </span>
              {hasQueued && (
                <button
                  onClick={() => handleRemoveLead(lid, name)}
                  disabled={removingLeadId === lid}
                  title="Retirer ce lead de la campagne"
                  className="p-1 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors
                             opacity-0 group-hover:opacity-100 disabled:opacity-50"
                >
                  {removingLeadId === lid ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <X className="w-3.5 h-3.5" />
                  )}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Modal prévisualisation des leads ─────────────────────────────────────────
function PreviewLeadsModal({ campaign, onClose, onConfirm }) {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    campaignsApi
      .previewLeads(campaign.id, { limit: 100 })
      .then((r) => setLeads(r.data.leads || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [campaign.id]);

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-bold text-primary-900">Aperçu de la campagne</h2>
            <p className="text-sm text-primary-500 mt-0.5">
              <span className="font-medium text-primary-700">{campaign.name}</span>
              {!loading &&
                ` · ${leads.length} lead${leads.length > 1 ? 's' : ''} éligible${leads.length > 1 ? 's' : ''}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4 text-primary-500" />
          </button>
        </div>

        {/* Corps */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-6 h-6 text-accent-500 animate-spin" />
            </div>
          ) : leads.length === 0 ? (
            <div className="text-center py-12">
              <Users className="w-10 h-10 text-primary-300 mx-auto mb-3" />
              <p className="text-primary-600 font-medium">Aucun lead éligible</p>
              <p className="text-sm text-primary-400 mt-1">
                Enrichissez des leads et ajoutez des emails pour lancer une campagne
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-primary-500 uppercase tracking-wider mb-3">
                Leads qui recevront les messages
              </p>
              {leads.map((lead) => (
                <div
                  key={lead.id}
                  className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs flex-shrink-0
                      ${lead.has_website === false ? 'bg-red-100 text-red-600' : 'bg-accent-100 text-accent-600'}`}
                    >
                      {lead.has_website === false ? '🔥' : '🏨'}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-primary-900 truncate">{lead.name}</p>
                      <p className="text-xs text-primary-400">
                        {lead.city || '—'} · {lead.email}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0 ml-3">
                    <Star className="w-3 h-3 text-accent-500" />
                    <span className="text-sm font-bold text-primary-800">{lead.score}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t border-gray-100">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-primary-200 text-primary-600 text-sm font-medium hover:bg-primary-50 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={onConfirm}
            disabled={leads.length === 0}
            className="flex-1 py-2.5 rounded-xl bg-accent-500 text-white text-sm font-semibold hover:bg-accent-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4" /> Démarrer ({leads.length} leads)
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────
export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [previewCampaign, setPreviewCampaign] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  const { toast, showToast } = useToast(4000);
  const [editingName, setEditingName] = useState(null); // { id, name }

  const fetchCampaigns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await campaignsApi.list();
      setCampaigns(res.data.campaigns || []);
    } catch {
      setError('Impossible de charger les campagnes. Vérifiez que le backend tourne.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-refresh toutes les 30s
  useEffect(() => {
    fetchCampaigns();
    const interval = setInterval(fetchCampaigns, 30000);
    return () => clearInterval(interval);
  }, [fetchCampaigns]);

  const handleCreate = (newCampaign) => {
    if (newCampaign && newCampaign.id) {
      setCampaigns((prev) => [newCampaign, ...prev]);
    } else {
      fetchCampaigns();
    }
    showToast('Campagne créée avec succès');
  };

  const handleToggle = async (campaign) => {
    if (campaign.status === 'running') {
      // Pause directe, pas besoin de prévisualisation
      setActionLoading(campaign.id);
      try {
        await campaignsApi.pause(campaign.id);
        setCampaigns((prev) =>
          prev.map((c) => (c.id === campaign.id ? { ...c, status: 'paused' } : c))
        );
        showToast('Campagne mise en pause');
      } catch (err) {
        showToast(err.response?.data?.detail || 'Erreur lors de la mise en pause');
      } finally {
        setActionLoading(null);
      }
    } else {
      showToast("Démarrage en masse désactivé : ajoutez les leads un par un depuis l'onglet Leads");
    }
  };

  const handleRename = async (id, newName) => {
    if (!newName.trim()) return;
    try {
      await campaignsApi.update(id, { name: newName.trim() });
      setCampaigns((prev) => prev.map((c) => (c.id === id ? { ...c, name: newName.trim() } : c)));
      showToast('Campagne renommée');
    } catch (err) {
      showToast(err.response?.data?.detail || 'Erreur lors du renommage');
    }
    setEditingName(null);
  };

  const handleDelete = async (campaign) => {
    if (
      !window.confirm(`Supprimer la campagne "${campaign.name}" ?\nCette action est irréversible.`)
    )
      return;
    setActionLoading(campaign.id);
    try {
      await campaignsApi.delete(campaign.id);
      setCampaigns((prev) => prev.filter((c) => c.id !== campaign.id));
      showToast(`Campagne "${campaign.name}" supprimée`);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Erreur lors de la suppression');
    } finally {
      setActionLoading(null);
    }
  };

  const handleConfirmStart = async () => {
    if (!previewCampaign) return;
    const campaign = previewCampaign;
    setPreviewCampaign(null);
    setActionLoading(campaign.id);
    try {
      const res = await campaignsApi.start(campaign.id);
      setCampaigns((prev) =>
        prev.map((c) => (c.id === campaign.id ? { ...c, status: 'running' } : c))
      );
      showToast(
        res.data.queued > 0
          ? `${res.data.queued} messages planifiés`
          : res.data.message || 'Campagne démarrée'
      );
    } catch (err) {
      showToast(err.response?.data?.detail || 'Erreur lors du démarrage');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-8">
      <AnimatePresence>
        {showModal && (
          <NewCampaignModal onClose={() => setShowModal(false)} onCreate={handleCreate} />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {previewCampaign && (
          <PreviewLeadsModal
            campaign={previewCampaign}
            onClose={() => setPreviewCampaign(null)}
            onConfirm={handleConfirmStart}
          />
        )}
      </AnimatePresence>

      {/* En-tête */}
      <motion.div {...fadeUp} className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-primary-900">Campagnes</h1>
          <p className="mt-1 text-primary-500">Gérez vos séquences de prospection</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchCampaigns}
            className="p-2 rounded-xl border border-primary-200 hover:bg-primary-50 transition-colors"
            title="Rafraîchir"
          >
            <RefreshCw className="w-4 h-4 text-primary-500" />
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 transition-colors flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" /> Nouvelle campagne
          </button>
        </div>
      </motion.div>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="fixed top-6 right-6 z-50 flex items-center gap-2 bg-green-600 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg"
          >
            <CheckCircle className="w-4 h-4" />
            {toast.msg || toast.message || toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Erreur */}
      {error && (
        <motion.div
          {...fadeUp}
          className="p-4 rounded-2xl border border-red-200 bg-red-50 flex items-center gap-3 text-red-600"
        >
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{error}</p>
        </motion.div>
      )}

      {/* File d'attente */}
      <QueuePanel onToast={showToast} onRefreshCampaigns={fetchCampaigns} />

      {/* Campagnes */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 text-accent-500 animate-spin" />
        </div>
      ) : campaigns.length === 0 ? (
        <motion.div
          {...fadeUp}
          className="bg-white rounded-2xl shadow-sm border border-gray-100 p-16 flex flex-col items-center justify-center text-center"
        >
          <div className="p-4 rounded-2xl bg-accent-50 mb-4">
            <Target className="w-10 h-10 text-accent-400" />
          </div>
          <p className="font-semibold text-primary-700 text-lg mb-1">Aucune campagne</p>
          <p className="text-primary-400 text-sm mb-6">
            Créez votre première campagne pour démarrer la prospection
          </p>
          <button
            onClick={() => setShowModal(true)}
            className="px-5 py-2.5 rounded-xl bg-accent-500 text-white font-semibold text-sm hover:bg-accent-600 transition-colors flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Créer une campagne
          </button>
        </motion.div>
      ) : (
        <div className="space-y-4">
          {campaigns.map((c, idx) => {
            const status = STATUS_STYLE[c.status] || STATUS_STYLE.draft;
            const responseRate =
              c.emails_sent > 0 ? ((c.responses_received / c.emails_sent) * 100).toFixed(1) : '—';
            return (
              <motion.div
                key={c.id}
                {...fadeUp}
                transition={{ duration: 0.3, delay: idx * 0.06 }}
                className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-accent-100 text-accent-600">
                      {c.channel === 'email' ? (
                        <Mail className="w-5 h-5" />
                      ) : (
                        <Linkedin className="w-5 h-5" />
                      )}
                    </div>
                    <div>
                      {editingName?.id === c.id ? (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            handleRename(c.id, editingName.name);
                          }}
                          className="flex items-center gap-2"
                        >
                          <input
                            autoFocus
                            value={editingName.name}
                            onChange={(e) => setEditingName({ id: c.id, name: e.target.value })}
                            onBlur={() => handleRename(c.id, editingName.name)}
                            onKeyDown={(e) => {
                              if (e.key === 'Escape') setEditingName(null);
                            }}
                            className="font-semibold text-primary-900 bg-primary-50 border border-accent-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-accent-400"
                          />
                        </form>
                      ) : (
                        <h3
                          className="font-semibold text-primary-900 flex items-center gap-1.5 group/name cursor-pointer"
                          onClick={() => setEditingName({ id: c.id, name: c.name })}
                          title="Cliquez pour renommer"
                        >
                          {c.name}
                          <Pencil className="w-3.5 h-3.5 text-primary-300 opacity-0 group-hover/name:opacity-100 transition-opacity" />
                        </h3>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-semibold ${status.bg}`}
                        >
                          {status.label}
                        </span>
                        <span className="text-sm text-primary-400 capitalize">{c.channel}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Leads planifiés (en attente d'envoi) */}
                    {c.messages_queued > 0 && (
                      <div
                        className="text-center"
                        title="Messages générés, en attente d'être envoyés"
                      >
                        <p className="text-2xl font-bold text-amber-500">{c.messages_queued}</p>
                        <p className="text-xs text-primary-500">Planifiés</p>
                      </div>
                    )}
                    <div className="text-center" title="Emails effectivement envoyés">
                      <p className="text-2xl font-bold text-primary-900">{c.emails_sent}</p>
                      <p className="text-xs text-primary-500">Envoyés</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-primary-900">{c.emails_opened}</p>
                      <p className="text-xs text-primary-500">Ouverts</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-primary-900">{c.responses_received}</p>
                      <p className="text-xs text-primary-500">Réponses</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-accent-600">
                        {responseRate}
                        {responseRate !== '—' ? '%' : ''}
                      </p>
                      <p className="text-xs text-primary-500">Taux rép.</p>
                    </div>

                    <div className="flex gap-2 items-center">
                      <button
                        onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary-200 text-xs font-medium text-primary-600 hover:bg-primary-50 transition-colors"
                      >
                        <MessageSquare className="w-3.5 h-3.5" />
                        Messages
                        {expandedId === c.id ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <button
                        onClick={() => setEditingName({ id: c.id, name: c.name })}
                        title="Renommer la campagne"
                        className="p-2 rounded-lg text-gray-400 hover:text-accent-600 hover:bg-accent-50 transition-colors"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      {c.status === 'running' && (
                        <button
                          onClick={() => handleToggle(c)}
                          disabled={actionLoading === c.id}
                          className="p-2 rounded-lg hover:bg-green-100 text-gray-400 hover:text-green-600 transition-colors disabled:opacity-50"
                        >
                          {actionLoading === c.id ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                          ) : (
                            <Pause className="w-5 h-5" />
                          )}
                        </button>
                      )}
                      {c.status !== 'running' && c.status !== 'completed' && (
                        <span
                          title="Mode test : ajoutez les leads un par un depuis l'onglet Leads"
                          className="px-2.5 py-1.5 rounded-lg bg-accent-50 text-accent-700 text-xs font-semibold"
                        >
                          Un par un
                        </span>
                      )}
                      {c.status === 'completed' && (
                        <CheckCircle className="w-5 h-5 text-green-400 m-2" />
                      )}
                      <button
                        onClick={() => handleDelete(c)}
                        disabled={actionLoading === c.id || c.status === 'running'}
                        title={
                          c.status === 'running'
                            ? 'Mettez en pause avant de supprimer'
                            : 'Supprimer la campagne'
                        }
                        className="p-2 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
                <AnimatePresence>
                  {expandedId === c.id && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      style={{ overflow: 'hidden' }}
                    >
                      <CampaignMessages campaignId={c.id} onRemoved={showToast} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
