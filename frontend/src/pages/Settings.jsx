import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Settings as SettingsIcon,
  Key,
  Mail,
  Linkedin,
  Save,
  CheckCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Send,
} from 'lucide-react';
import { settingsApi } from '../api/settings';

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3 },
};

function Section({ icon: Icon, title, children, badge }) {
  return (
    <motion.div {...fadeUp} className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-100 text-accent-600">
            <Icon className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-primary-900">{title}</h3>
        </div>
        {badge}
      </div>
      {children}
    </motion.div>
  );
}

function StatusBadge({ configured }) {
  return configured ? (
    <span className="flex items-center gap-1.5 text-xs font-medium text-success-600 bg-success-50 px-2.5 py-1 rounded-full border border-success-200">
      <CheckCircle className="w-3.5 h-3.5" /> Configuré
    </span>
  ) : (
    <span className="flex items-center gap-1.5 text-xs font-medium text-warning-600 bg-warning-50 px-2.5 py-1 rounded-full border border-warning-200">
      <AlertCircle className="w-3.5 h-3.5" /> Non configuré
    </span>
  );
}

function Field({ label, value, onChange, placeholder, type = 'text', masked = false, hint }) {
  const [show, setShow] = useState(false);
  const inputType = masked ? (show ? 'text' : 'password') : type;

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-primary-700 mb-1">{label}</label>
      <div className="relative">
        <input
          type={inputType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full px-3 py-2 rounded-lg border border-primary-200 text-primary-900 placeholder-primary-400 focus:outline-none focus:border-accent-400 focus:ring-2 focus:ring-accent-100 transition pr-10"
        />
        {masked && (
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-primary-400 hover:text-primary-600"
          >
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
      {hint && <p className="text-xs text-primary-400 mt-1">{hint}</p>}
    </div>
  );
}

function TestEmailButton() {
  const [testEmail, setTestEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  const handleTest = async () => {
    if (!testEmail.trim()) return;
    setSending(true);
    setResult(null);
    try {
      await settingsApi.sendTestEmail(testEmail);
      setResult({ ok: true, msg: `Email de test envoyé à ${testEmail}` });
    } catch (err) {
      setResult({ ok: false, msg: err.response?.data?.detail || "Erreur lors de l'envoi" });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-2 pt-4 border-t border-primary-100">
      <label className="block text-sm font-medium text-primary-700 mb-1.5">
        Tester la configuration
      </label>
      <div className="flex gap-2">
        <input
          type="email"
          value={testEmail}
          onChange={(e) => setTestEmail(e.target.value)}
          placeholder="email-de-test@exemple.com"
          className="flex-1 px-3 py-2 rounded-lg border border-primary-200 text-primary-900 placeholder-primary-400 text-sm
                     focus:outline-none focus:border-accent-400 focus:ring-2 focus:ring-accent-100 transition"
        />
        <button
          onClick={handleTest}
          disabled={sending || !testEmail.trim()}
          className="px-4 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Tester
        </button>
      </div>
      {result && (
        <p
          className={`mt-2 text-xs flex items-center gap-1.5 ${result.ok ? 'text-green-600' : 'text-red-600'}`}
        >
          {result.ok ? (
            <CheckCircle className="w-3.5 h-3.5" />
          ) : (
            <AlertCircle className="w-3.5 h-3.5" />
          )}
          {result.msg}
        </p>
      )}
    </div>
  );
}

export default function Settings() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);

  // Champs modifiables (vides = ne pas toucher à la valeur actuelle)
  const [fields, setFields] = useState({
    anthropic_api_key: '',
    hunter_api_key: '',
    google_places_api_key: '',
    smtp_host: '',
    smtp_port: '',
    smtp_user: '',
    smtp_password: '',
    email_from: '',
    linkedin_email: '',
    linkedin_password: '',
  });

  useEffect(() => {
    settingsApi
      .get()
      .then((res) => {
        setConfig(res.data);
        // Pré-remplir les champs non-sensibles
        setFields((f) => ({
          ...f,
          smtp_host: res.data.smtp_host || '',
          smtp_port: res.data.smtp_port ? String(res.data.smtp_port) : '587',
          smtp_user: res.data.smtp_user || '',
          email_from: res.data.email_from || '',
          linkedin_email: res.data.linkedin_email || '',
        }));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const set = (key) => (val) => setFields((f) => ({ ...f, [key]: val }));

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      const payload = {};
      Object.entries(fields).forEach(([k, v]) => {
        if (v !== '') payload[k] = k === 'smtp_port' ? Number(v) : v;
      });
      const res = await settingsApi.save(payload);
      setSaveMsg({ type: 'success', text: `Sauvegardé : ${res.data.updated.join(', ')}` });
      // Recharger la config
      const updated = await settingsApi.get();
      setConfig(updated.data);
      // Vider les champs de mot de passe
      setFields((f) => ({
        ...f,
        anthropic_api_key: '',
        hunter_api_key: '',
        google_places_api_key: '',
        smtp_password: '',
        linkedin_password: '',
      }));
    } catch (err) {
      setSaveMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Erreur lors de la sauvegarde',
      });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 4000);
    }
  };

  if (loading)
    return (
      <div className="flex items-center justify-center h-40">
        <Loader2 className="w-6 h-6 animate-spin text-accent-500" />
      </div>
    );

  return (
    <div className="space-y-8">
      <motion.div {...fadeUp}>
        <h1 className="text-3xl font-display font-bold text-primary-900">Paramètres</h1>
        <p className="mt-1 text-primary-500">Configuration de l'agent et des intégrations</p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* IA Claude */}
        <Section
          icon={Key}
          title="IA — Claude (Anthropic)"
          badge={config && <StatusBadge configured={config.anthropic_configured} />}
        >
          {config?.anthropic_configured && (
            <p className="text-xs text-primary-500 mb-3 font-mono bg-primary-50 px-2 py-1 rounded">
              Clé actuelle : {config.anthropic_api_key_masked}
            </p>
          )}
          <Field
            label="Nouvelle clé API Anthropic"
            value={fields.anthropic_api_key}
            onChange={set('anthropic_api_key')}
            placeholder="sk-ant-..."
            masked
            hint="Laissez vide pour conserver la clé actuelle"
          />
        </Section>

        {/* Email */}
        <Section
          icon={Mail}
          title="Configuration Email (SMTP)"
          badge={config && <StatusBadge configured={config.smtp_configured} />}
        >
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Serveur SMTP"
              value={fields.smtp_host}
              onChange={set('smtp_host')}
              placeholder="smtp.gmail.com"
            />
            <Field
              label="Port"
              value={fields.smtp_port}
              onChange={set('smtp_port')}
              placeholder="587"
              type="number"
            />
          </div>
          <Field
            label="Adresse email"
            value={fields.smtp_user}
            onChange={set('smtp_user')}
            placeholder="votre@email.com"
          />
          <Field
            label="Email expéditeur"
            value={fields.email_from}
            onChange={set('email_from')}
            placeholder="votre@email.com"
          />
          <Field
            label="Mot de passe SMTP"
            value={fields.smtp_password}
            onChange={set('smtp_password')}
            placeholder="Laisser vide pour conserver"
            masked
          />
          <TestEmailButton />
        </Section>

        {/* Enrichissement */}
        <Section
          icon={SettingsIcon}
          title="APIs d'Enrichissement"
          badge={
            config && (
              <StatusBadge configured={config.hunter_configured || config.google_configured} />
            )
          }
        >
          {config?.hunter_configured && (
            <p className="text-xs text-primary-500 mb-1 font-mono bg-primary-50 px-2 py-1 rounded">
              Hunter.io : {config.hunter_api_key_masked}
            </p>
          )}
          <Field
            label="Hunter.io API Key"
            value={fields.hunter_api_key}
            onChange={set('hunter_api_key')}
            placeholder="hunter_..."
            masked
            hint="Pour trouver des emails professionnels"
          />

          {config?.google_configured && (
            <p className="text-xs text-primary-500 mb-1 font-mono bg-primary-50 px-2 py-1 rounded">
              Google Places : {config.google_places_api_key_masked}
            </p>
          )}
          <Field
            label="Google Places API Key"
            value={fields.google_places_api_key}
            onChange={set('google_places_api_key')}
            placeholder="AIza..."
            masked
            hint="Pour les avis Google et la géolocalisation"
          />
        </Section>

        {/* LinkedIn */}
        <Section icon={Linkedin} title="LinkedIn">
          <Field
            label="Email LinkedIn"
            value={fields.linkedin_email}
            onChange={set('linkedin_email')}
            placeholder="votre@email.com"
          />
          <Field
            label="Mot de passe LinkedIn"
            value={fields.linkedin_password}
            onChange={set('linkedin_password')}
            placeholder="Laisser vide pour conserver"
            masked
            hint="Stocké localement, jamais partagé"
          />
          <div className="mb-2">
            <label className="block text-sm font-medium text-primary-700 mb-1">
              Limite d'actions par jour
            </label>
            <input
              type="range"
              min="10"
              max="100"
              defaultValue="50"
              className="w-full accent-accent-500"
            />
            <div className="flex justify-between text-xs text-primary-400 mt-1">
              <span>10</span>
              <span>50 (recommandé)</span>
              <span>100</span>
            </div>
          </div>
        </Section>
      </div>

      {/* Sauvegarde */}
      <motion.div {...fadeUp} className="flex items-center justify-between">
        {saveMsg && (
          <div
            className={`flex items-center gap-2 text-sm px-4 py-2 rounded-xl ${saveMsg.type === 'success' ? 'bg-success-50 text-success-700 border border-success-200' : 'bg-error-50 text-error-700 border border-error-200'}`}
          >
            {saveMsg.type === 'success' ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <AlertCircle className="w-4 h-4" />
            )}
            {saveMsg.text}
          </div>
        )}
        <div className="ml-auto">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-3 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Sauvegarde...' : 'Sauvegarder les paramètres'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
