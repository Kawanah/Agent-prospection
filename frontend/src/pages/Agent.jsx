import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bot,
  Send,
  Loader2,
  AlertCircle,
  Zap,
  Search,
  Mail,
  BarChart2,
  RefreshCw,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import axios from 'axios';
import { API_URL } from '../config';
const SESSION_ID = 'default';

const EXAMPLE_PROMPTS = [
  { icon: Search, text: 'Trouve des hôtels sans site web', category: 'Recherche' },
  { icon: BarChart2, text: 'Montre-moi les statistiques', category: 'Stats' },
  { icon: Zap, text: 'Quels sont les leads chauds ?', category: 'Priorité' },
  { icon: Mail, text: 'Génère un email pour le lead 1', category: 'Prospection' },
];

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (isSystem) {
    return (
      <div className="flex items-center gap-2 text-xs text-primary-400 py-1 px-3">
        <div className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-pulse" />
        {msg.content}
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} gap-3`}
    >
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent-400 to-accent-600 flex items-center justify-center flex-shrink-0 mt-1">
          <Bot className="w-4 h-4 text-white" />
        </div>
      )}
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-accent-500 text-white rounded-tr-sm'
            : 'bg-white border border-primary-100 text-primary-800 rounded-tl-sm shadow-sm'
        }`}
      >
        {msg.content}
        <p className={`text-xs mt-1.5 ${isUser ? 'text-accent-200' : 'text-primary-400'}`}>
          {msg.timestamp
            ? new Date(msg.timestamp).toLocaleTimeString('fr-FR', {
                hour: '2-digit',
                minute: '2-digit',
              })
            : ''}
        </p>
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-xl bg-primary-200 flex items-center justify-center flex-shrink-0 mt-1 text-xs font-bold text-primary-600">
          Vous
        </div>
      )}
    </motion.div>
  );
}

const WELCOME_MSG = {
  role: 'assistant',
  content: `👋 **Bonjour ! Je suis votre agent de prospection Kawanah Travel.**\n\nJe peux vous aider à :\n🔍 Rechercher des leads selon vos critères\n📊 Analyser les statistiques\n✉️ Générer des messages personnalisés\n\nQue voulez-vous faire ?`,
  timestamp: new Date().toISOString(),
};

function loadMessages() {
  try {
    const saved = sessionStorage.getItem('agent_messages');
    return saved ? JSON.parse(saved) : [WELCOME_MSG];
  } catch {
    return [WELCOME_MSG];
  }
}

export default function Agent() {
  const [messages, setMessages] = useState(loadMessages);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showExamples, setShowExamples] = useState(true);
  // État human-in-the-loop : quand l'agent attend une décision
  const [requiresHumanInput, setRequiresHumanInput] = useState(false);
  const [humanQuestion, setHumanQuestion] = useState(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Persister la conversation pour ne pas la perdre en naviguant
  useEffect(() => {
    try {
      sessionStorage.setItem('agent_messages', JSON.stringify(messages));
    } catch {
      /* sessionStorage indisponible */
    }
  }, [messages]);

  const sendMessage = async (text) => {
    const messageText = text || input.trim();
    if (!messageText || loading) return;

    setInput('');
    setShowExamples(false);
    setError(null);

    // Ajouter le message utilisateur
    const userMsg = { role: 'user', content: messageText, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      let res;
      if (requiresHumanInput) {
        // L'agent attend une décision humaine → utiliser /respond
        setRequiresHumanInput(false);
        setHumanQuestion(null);
        res = await axios.post(`${API_URL}/api/agent/respond`, {
          session_id: SESSION_ID,
          response: messageText,
        });
      } else {
        res = await axios.post(`${API_URL}/api/agent/chat`, {
          message: messageText,
          session_id: SESSION_ID,
          mode: 'supervised',
        });
      }

      // Ajouter les réponses de l'agent
      const agentMessages = res.data.messages || [];
      setMessages((prev) => [...prev, ...agentMessages]);

      // Mettre à jour l'état human-in-the-loop
      if (res.data.requires_human_input) {
        setRequiresHumanInput(true);
        setHumanQuestion(res.data.human_question);
      } else {
        setRequiresHumanInput(false);
        setHumanQuestion(null);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setError(`Erreur de connexion à l'agent : ${detail}`);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `❌ Impossible de joindre l'agent. Vérifiez que le backend tourne sur le port 8000.\n\nErreur : ${detail}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  // Réponse rapide à une décision humaine (Oui/Non)
  const respondHuman = (response) => sendMessage(response);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetSession = async () => {
    try {
      await axios.delete(`${API_URL}/api/agent/session/${SESSION_ID}`);
    } catch {
      /* session déjà absente */
    }
    sessionStorage.removeItem('agent_messages');
    setMessages([
      {
        role: 'assistant',
        content: `🔄 **Conversation réinitialisée.**\n\nComment puis-je vous aider ?`,
        timestamp: new Date().toISOString(),
      },
    ]);
    setShowExamples(true);
    setError(null);
    setRequiresHumanInput(false);
    setHumanQuestion(null);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col"
      style={{ height: 'calc(100vh - 10rem)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-primary-900">Agent Autonome</h1>
          <p className="mt-1 text-primary-500">Discutez avec votre agent de prospection IA</p>
        </div>
        <button
          onClick={resetSession}
          className="flex items-center gap-2 px-3 py-2 rounded-xl border border-primary-200 text-primary-500 hover:bg-primary-50 text-sm transition-colors"
          title="Nouvelle conversation"
        >
          <RefreshCw className="w-4 h-4" /> Réinitialiser
        </button>
      </div>

      {/* Zone de chat */}
      <div className="card flex-1 flex flex-col overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}

          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3"
            >
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent-400 to-accent-600 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white border border-primary-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                <Loader2 className="w-4 h-4 text-accent-500 animate-spin" />
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Exemples de prompts */}
        <AnimatePresence>
          {showExamples && messages.length <= 1 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="px-6 pb-3"
            >
              <p className="text-xs text-primary-400 mb-2">Essayez :</p>
              <div className="grid grid-cols-2 gap-2">
                {EXAMPLE_PROMPTS.map((ex) => (
                  <button
                    key={ex.text}
                    onClick={() => sendMessage(ex.text)}
                    className="flex items-center gap-2 p-3 rounded-xl bg-primary-50 hover:bg-accent-50 hover:border-accent-200 border border-primary-100 text-left text-sm text-primary-700 transition-all"
                  >
                    <ex.icon className="w-4 h-4 text-accent-500 flex-shrink-0" />
                    <span className="truncate">{ex.text}</span>
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Bannière décision humaine */}
        <AnimatePresence>
          {requiresHumanInput && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="border-t border-amber-200 bg-amber-50 px-6 py-3"
            >
              <p className="text-sm font-medium text-amber-800 mb-2">
                ⏸️ L'agent attend votre décision
              </p>
              {humanQuestion && <p className="text-xs text-amber-700 mb-3">{humanQuestion}</p>}
              <div className="flex gap-2">
                <button
                  onClick={() => respondHuman('Oui, envoyer')}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                  <CheckCircle className="w-3.5 h-3.5" /> Oui, confirmer
                </button>
                <button
                  onClick={() => respondHuman('Non, annuler')}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500 text-white text-xs font-medium hover:bg-red-600 disabled:opacity-50 transition-colors"
                >
                  <XCircle className="w-3.5 h-3.5" /> Non, annuler
                </button>
                <span className="text-xs text-amber-600 self-center ml-1">
                  ou tapez votre réponse ↓
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Zone de saisie */}
        <div className="border-t border-primary-100 p-4">
          {error && (
            <div className="flex items-center gap-2 text-xs text-red-600 mb-2">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              {error}
            </div>
          )}
          <div className="flex items-end gap-3">
            <div className="flex-1 flex items-end gap-2 px-4 py-3 rounded-xl bg-primary-50 border border-primary-200 focus-within:border-accent-400 focus-within:bg-white transition-all">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  requiresHumanInput
                    ? "Répondez à la question de l'agent..."
                    : 'Demandez quelque chose à votre agent...'
                }
                rows={1}
                className="flex-1 bg-transparent text-sm text-primary-900 placeholder-primary-400 outline-none resize-none max-h-32"
                style={{ lineHeight: '1.5' }}
              />
            </div>
            <button
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
              className="p-3 rounded-xl bg-accent-500 text-white hover:bg-accent-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex-shrink-0"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-xs text-primary-400 mt-2 text-center">
            Entrée pour envoyer · Maj+Entrée pour nouvelle ligne
          </p>
        </div>
      </div>
    </motion.div>
  );
}
