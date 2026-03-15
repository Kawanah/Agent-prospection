import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Copy,
  Send,
  Mail,
  Linkedin,
  Loader2,
  AlertCircle,
  X,
  CheckCircle,
  RefreshCw,
  MessageSquare,
  Plus,
} from 'lucide-react';
import axios from 'axios';
import { API_URL } from '../config';

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

const STATUS_STYLE = {
  draft: { label: 'Brouillon', cls: 'bg-gray-100 text-gray-600' },
  queued: { label: 'En attente', cls: 'bg-amber-100 text-amber-700' },
  sent: { label: 'Envoyé', cls: 'bg-blue-100 text-blue-700' },
  delivered: { label: 'Livré', cls: 'bg-green-100 text-green-700' },
  opened: { label: 'Ouvert', cls: 'bg-green-100 text-green-700' },
  failed: { label: 'Échec', cls: 'bg-red-100 text-red-600' },
  cancelled: { label: 'Annulé', cls: 'bg-gray-100 text-gray-500' },
};

const SENTIMENT_STYLE = {
  positive: { label: 'Intérêt détecté', cls: 'bg-green-100 text-green-700' },
  negative: { label: 'Rejet', cls: 'bg-red-100 text-red-600' },
  neutral: { label: 'Neutre', cls: 'bg-gray-100 text-gray-600' },
  unknown: { label: '', cls: '' },
};

// ─── Modal génération IA ──────────────────────────────────────────────────────
function GenerateModal({ onClose, onSaved }) {
  const [leads, setLeads] = useState([]);
  const [selectedLead, setSelectedLead] = useState('');
  const [channel, setChannel] = useState('email');
  const [tone, setTone] = useState('friendly');
  const [generated, setGenerated] = useState(null);
  const [editedBody, setEditedBody] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    axios
      .get(`${API_URL}/api/leads/`, { params: { per_page: 100, page: 1 } })
      .then((r) => setLeads(r.data.leads || []))
      .catch(() => {});
  }, []);

  const handleGenerate = async () => {
    if (!selectedLead) return;
    setLoading(true);
    setError(null);
    setGenerated(null);
    try {
      const res = await axios.post(`${API_URL}/api/ai/generate/${selectedLead}`, {
        channel,
        tone,
        sender_name: "L'équipe Kawanah Travel",
      });
      setGenerated(res.data);
      setEditedBody(res.data.body);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la génération');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!generated) return;
    setSaving(true);
    try {
      await axios.post(`${API_URL}/api/messages/`, {
        lead_id: generated.lead_id,
        channel,
        subject: generated.subject,
        body: editedBody,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(editedBody);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <h2 className="text-lg font-bold text-primary-900 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-accent-500" /> Générer un message IA
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4 text-primary-500" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Sélection lead */}
          <div>
            <label className="block text-sm font-medium text-primary-700 mb-1.5">
              Prospect cible
            </label>
            <select
              value={selectedLead}
              onChange={(e) => setSelectedLead(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl border border-primary-200 text-sm text-primary-900 bg-white focus:outline-none focus:ring-2 focus:ring-accent-400"
            >
              <option value="">Sélectionnez un prospect...</option>
              {leads.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                  {l.city ? ` — ${l.city}` : ''} (score: {l.score})
                </option>
              ))}
            </select>
          </div>

          {/* Canal + Ton */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-primary-700 mb-1.5">Canal</label>
              <div className="flex gap-2">
                {[
                  { v: 'email', label: 'Email' },
                  { v: 'linkedin', label: 'LinkedIn' },
                ].map(({ v, label }) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setChannel(v)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl border text-sm font-medium transition-colors
                      ${channel === v ? 'bg-accent-500 text-white border-accent-500' : 'bg-gray-50 text-primary-600 border-gray-200 hover:bg-gray-100'}`}
                  >
                    {v === 'email' ? (
                      <Mail className="w-4 h-4" />
                    ) : (
                      <Linkedin className="w-4 h-4" />
                    )}
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-primary-700 mb-1.5">Ton</label>
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-primary-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent-400"
              >
                <option value="friendly">Amical</option>
                <option value="professional">Professionnel</option>
                <option value="direct">Direct</option>
              </select>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-600 text-sm p-3 bg-red-50 rounded-xl border border-red-200">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <button
            onClick={handleGenerate}
            disabled={!selectedLead || loading}
            className="w-full py-2.5 rounded-xl bg-accent-500 text-white font-semibold text-sm hover:bg-accent-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {loading ? 'Génération en cours...' : "Générer avec l'IA"}
          </button>

          {/* Résultat généré */}
          {generated && (
            <motion.div {...fadeUp} className="space-y-3 pt-2 border-t border-gray-100">
              <div>
                <label className="block text-xs font-medium text-primary-500 mb-1">Objet</label>
                <p className="text-sm font-semibold text-primary-900 bg-gray-50 px-3 py-2 rounded-lg">
                  {generated.subject}
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-primary-500 mb-1">
                  Corps du message (modifiable)
                </label>
                <textarea
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  rows={10}
                  className="w-full px-3 py-2.5 rounded-xl border border-primary-200 text-sm text-primary-900 resize-y focus:outline-none focus:ring-2 focus:ring-accent-400"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-sm text-primary-600 hover:bg-gray-50 transition-colors"
                >
                  {copied ? (
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                  {copied ? 'Copié !' : 'Copier'}
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 transition-colors disabled:opacity-50"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                  Sauvegarder comme brouillon
                </button>
              </div>
            </motion.div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────
export default function Messages() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [toast, setToast] = useState(null);
  const [copied, setCopied] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [testEmail, setTestEmail] = useState('');
  const [testSending, setTestSending] = useState(false);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState('');
  const [leadNames, setLeadNames] = useState({});
  const [expandedId, setExpandedId] = useState(null);

  const fetchMessages = useCallback(async (campaignId = '') => {
    setLoading(true);
    setError(null);
    try {
      const params = { per_page: 100, page: 1 };
      if (campaignId) params.campaign_id = campaignId;
      const res = await axios.get(`${API_URL}/api/messages/`, { params });
      const msgs = res.data.messages || [];
      setMessages(msgs);
      // Charger les noms des leads
      const uniqueLeadIds = [...new Set(msgs.map((m) => m.lead_id).filter(Boolean))];
      const names = {};
      await Promise.all(
        uniqueLeadIds.map(async (id) => {
          try {
            const r = await axios.get(`${API_URL}/api/leads/${id}`);
            names[id] = r.data.name || `Lead #${id}`;
          } catch {
            names[id] = `Lead #${id}`;
          }
        })
      );
      setLeadNames(names);
    } catch {
      setError('Impossible de charger les messages. Vérifiez que le backend tourne.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    axios
      .get(`${API_URL}/api/campaigns/`, { params: { per_page: 50 } })
      .then((r) => setCampaigns(r.data.campaigns || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchMessages(selectedCampaign);
  }, [fetchMessages, selectedCampaign]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleCopy = (id, body) => {
    navigator.clipboard.writeText(body);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleQueue = async (id) => {
    try {
      await axios.post(`${API_URL}/api/messages/${id}/queue`);
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, status: 'queued' } : m)));
      showToast("Message mis en file d'attente");
    } catch (err) {
      showToast('Erreur : ' + (err.response?.data?.detail || 'inconnue'));
    }
  };

  const handleSendTest = async (id) => {
    if (!testEmail.trim()) return;
    setTestSending(true);
    try {
      await axios.post(`${API_URL}/api/messages/${id}/send-test`, { to_email: testEmail });
      showToast(`Email de test envoyé à ${testEmail}`);
      setTestingId(null);
      setTestEmail('');
    } catch (err) {
      showToast(
        'Erreur : ' + (err.response?.data?.detail || 'Vérifiez la config SMTP dans Paramètres')
      );
    } finally {
      setTestSending(false);
    }
  };

  return (
    <div className="space-y-8">
      <AnimatePresence>
        {showModal && (
          <GenerateModal
            onClose={() => setShowModal(false)}
            onSaved={() => {
              fetchMessages();
              showToast('Message sauvegardé comme brouillon');
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
            className="fixed top-6 right-6 z-50 flex items-center gap-2 bg-green-600 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg"
          >
            <CheckCircle className="w-4 h-4" />
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* En-tête */}
      <motion.div {...fadeUp} className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-primary-900">Messages</h1>
          <p className="mt-1 text-primary-500">Génération et suivi de vos messages IA</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchMessages(selectedCampaign)}
            className="p-2 rounded-xl border border-primary-200 hover:bg-primary-50 transition-colors"
            title="Rafraîchir"
          >
            <RefreshCw className="w-4 h-4 text-primary-500" />
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 transition-colors flex items-center gap-2 text-sm"
          >
            <Sparkles className="w-4 h-4" /> Générer un message
          </button>
        </div>
      </motion.div>

      {/* Filtre par campagne */}
      <motion.div {...fadeUp} className="flex items-center gap-3">
        <select
          value={selectedCampaign}
          onChange={(e) => setSelectedCampaign(e.target.value)}
          className="px-3 py-2 rounded-xl border border-primary-200 text-sm text-primary-800 bg-white focus:outline-none focus:ring-2 focus:ring-accent-400 min-w-[220px]"
        >
          <option value="">Toutes les campagnes</option>
          {campaigns.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        {selectedCampaign && (
          <button
            onClick={() => setSelectedCampaign('')}
            className="text-xs text-primary-400 hover:text-primary-600 underline"
          >
            Effacer le filtre
          </button>
        )}
        <span className="text-sm text-primary-400">
          {messages.length} message{messages.length > 1 ? 's' : ''}
        </span>
      </motion.div>

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

      {/* Contenu */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 text-accent-500 animate-spin" />
        </div>
      ) : messages.length === 0 ? (
        <motion.div
          {...fadeUp}
          className="bg-white rounded-2xl shadow-sm border border-gray-100 p-16 flex flex-col items-center justify-center text-center"
        >
          <div className="p-4 rounded-2xl bg-accent-50 mb-4">
            <MessageSquare className="w-10 h-10 text-accent-400" />
          </div>
          <p className="font-semibold text-primary-700 text-lg mb-1">Aucun message</p>
          <p className="text-primary-400 text-sm mb-6">Générez votre premier message avec l'IA</p>
          <button
            onClick={() => setShowModal(true)}
            className="px-5 py-2.5 rounded-xl bg-accent-500 text-white font-semibold text-sm hover:bg-accent-600 transition-colors flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" /> Générer un message
          </button>
        </motion.div>
      ) : (
        <div className="space-y-4">
          {messages.map((msg, idx) => {
            const status = STATUS_STYLE[msg.status] || STATUS_STYLE.draft;
            const sentiment = SENTIMENT_STYLE[msg.sentiment] || SENTIMENT_STYLE.unknown;
            const date = msg.sent_at || msg.created_at;
            const dateStr = date
              ? new Date(date).toLocaleDateString('fr-FR', {
                  day: '2-digit',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : '—';
            return (
              <motion.div
                key={msg.id}
                {...fadeUp}
                transition={{ duration: 0.3, delay: idx * 0.05 }}
                className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-xl bg-accent-50 text-accent-500 mt-0.5">
                      {msg.channel === 'email' ? (
                        <Mail className="w-4 h-4" />
                      ) : (
                        <Linkedin className="w-4 h-4" />
                      )}
                    </div>
                    <div>
                      <p className="font-semibold text-primary-900 text-sm">
                        {leadNames[msg.lead_id] || `Lead #${msg.lead_id}`}
                      </p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-semibold ${status.cls}`}
                        >
                          {status.label}
                        </span>
                        {sentiment.label && (
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-semibold ${sentiment.cls}`}
                          >
                            {sentiment.label}
                          </span>
                        )}
                        {msg.subject && (
                          <span className="text-xs text-primary-500 truncate max-w-xs">
                            — {msg.subject}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-primary-400 flex-shrink-0 ml-4">{dateStr}</span>
                </div>

                <div
                  className="text-sm text-primary-600 bg-gray-50 rounded-xl p-4 cursor-pointer"
                  onClick={() => setExpandedId(expandedId === msg.id ? null : msg.id)}
                >
                  <p
                    className={`italic whitespace-pre-wrap ${expandedId === msg.id ? '' : 'line-clamp-2'}`}
                  >
                    "{msg.body}"
                  </p>
                  <p className="text-xs text-primary-400 mt-1 text-right">
                    {expandedId === msg.id ? '▲ Réduire' : '▼ Voir le message complet'}
                  </p>
                </div>

                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => handleCopy(msg.id, msg.body)}
                      className="p-2 rounded-lg hover:bg-gray-100 text-primary-400 hover:text-primary-600 transition-colors"
                      title="Copier"
                    >
                      {copied === msg.id ? (
                        <CheckCircle className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={() => {
                        setTestingId(testingId === msg.id ? null : msg.id);
                        setTestEmail('');
                      }}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors
                        ${
                          testingId === msg.id
                            ? 'border-accent-300 bg-accent-50 text-accent-700'
                            : 'border-gray-200 text-primary-500 hover:bg-gray-50'
                        }`}
                      title="Envoyer en test"
                    >
                      <Send className="w-3.5 h-3.5" /> Envoyer en test
                    </button>
                    {msg.status === 'draft' && (
                      <button
                        onClick={() => handleQueue(msg.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-500 text-white text-xs font-medium hover:bg-accent-600 transition-colors"
                      >
                        <Plus className="w-3.5 h-3.5" /> Mettre en file
                      </button>
                    )}
                  </div>

                  {testingId === msg.id && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      className="flex gap-2 pt-1"
                    >
                      <input
                        type="email"
                        value={testEmail}
                        onChange={(e) => setTestEmail(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSendTest(msg.id)}
                        placeholder="votre-test@email.com"
                        autoFocus
                        className="flex-1 px-3 py-1.5 rounded-lg border border-primary-200 text-sm text-primary-900 placeholder-primary-400
                                   focus:outline-none focus:border-accent-400 focus:ring-2 focus:ring-accent-100 transition"
                      />
                      <button
                        onClick={() => handleSendTest(msg.id)}
                        disabled={testSending || !testEmail.trim()}
                        className="px-4 py-1.5 rounded-lg bg-accent-500 text-white text-xs font-semibold hover:bg-accent-600
                                   disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
                      >
                        {testSending ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Send className="w-3.5 h-3.5" />
                        )}
                        Envoyer
                      </button>
                    </motion.div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
