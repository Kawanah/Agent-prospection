# Agent de Prospection Automatisé — Kawanah Tourisme

Plateforme de prospection commerciale B2B automatisée, dédiée au secteur de l'hospitalité (hôtels, hébergements, campings, prestataires d'activités). L'outil identifie des établissements, enrichit leurs contacts, évalue leur présence web, puis génère et orchestre des messages de prospection personnalisés pour proposer des services de création web.

---

## Le problème résolu

La prospection commerciale manuelle est lente et peu qualifiée : trouver les bons établissements, récupérer les coordonnées des décideurs, analyser leur site existant, puis rédiger un message pertinent pour chacun représente des heures de travail répétitif.

Cet agent automatise l'intégralité de la chaîne :

1. **Sourcing** — collecte d'établissements depuis plusieurs sources (import CSV/Excel, Google Places, DATAtourisme, SIRENE, Pappers, BODACC, data.gouv.fr).
2. **Enrichissement** — recherche automatique du site web, des contacts, des emails et des réseaux sociaux à partir du seul nom de structure.
3. **Analyse & scoring** — audit du site existant (ou constat de son absence), scoring et segmentation des leads (chaud / tiède / froid).
4. **Génération de messages** — rédaction de messages de prospection personnalisés par IA, fondés sur l'audit réel du prospect.
5. **Exécution multicanale** — séquençage, planification et envoi des emails avec gestion des quotas et des relances.

Le résultat : un pipeline qui transforme une simple liste de noms d'établissements en campagnes de prospection ciblées et argumentées.

---

## Fonctionnement de l'agent

Le cœur du produit est un **agent autonome** (`app/agent/`) qui s'appuie sur Claude (Anthropic) via le mécanisme de **Tool Use**. Plutôt que de suivre un script figé, l'agent raisonne et décide lui-même des actions à mener parmi un ensemble d'outils qui lui sont exposés : rechercher des leads par segment, enrichir un contact, vérifier un site web, analyser les avis Google, générer un message, envoyer un email.

Modes de fonctionnement :

- **Autonome** — l'agent enchaîne les actions de bout en bout.
- **Human-in-the-loop** — les actions sensibles (comme l'envoi) sont soumises à validation humaine depuis le dashboard.

La génération de messages repose sur un audit réel du prospect (présence web, SEO, avis) afin de produire un argumentaire commercial adapté et non générique. En l'absence de clé API, un mode démonstration fournit des messages prédéfinis.

Un **scheduler d'envoi** (désactivé par défaut) traite la file des emails planifiés à intervalle régulier, dans la limite du quota journalier. Plusieurs garde-fous encadrent les actions à risque : l'envoi d'emails réel, la purge de données et la modification des paramètres à chaud sont désactivés par défaut et ne s'activent que par opt-in explicite.

---

## Stack technique

### Backend
- **Python 3.11+**
- **FastAPI** — API REST, documentation OpenAPI automatique
- **SQLAlchemy 2.0** (async) + **SQLite** (dev) / PostgreSQL (prod)
- **Pydantic v2** — validation des données
- **Anthropic (Claude API)** — agent autonome, génération de messages, scoring
- **httpx · BeautifulSoup · lxml** — scraping et appels d'API
- **pandas · openpyxl** — traitement des imports CSV/Excel
- **Celery + Redis** — traitement asynchrone
- **JWT (python-jose) · passlib/bcrypt** — authentification
- **slowapi** — rate limiting
- **loguru** — logs

### Frontend
- **React 19** + **Vite 7**
- **React Router 7**
- **Tailwind CSS 3**
- **Recharts** — graphiques et statistiques
- **Framer Motion** — animations
- **axios** — client HTTP
- **Vitest** + Testing Library — tests

### Sources de données & enrichissement
Google Places, DATAtourisme, SIRENE, Pappers, BODACC, data.gouv.fr, DataForSEO (SEO), Google Reviews, Hunter.io, Dropcontact.

---

## Prérequis

- **Python 3.11+**
- **Node.js 18+** (pour le dashboard frontend)
- **Redis** (optionnel — requis uniquement pour Celery et le traitement asynchrone)
- **Clé API Anthropic** (fonctionnalités IA ; sinon mode démonstration)
- Clés API optionnelles selon les sources activées (Google Places, Pappers, DATAtourisme, DataForSEO, etc.)

---

## Installation

### 1. Backend

```bash
python -m venv venv
source venv/bin/activate          # Linux/Mac
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
```

Puis renseigner les variables dans `.env`. Deux valeurs sont **obligatoires** et doivent être générées :

```bash
# Clé secrète JWT
python -c "import secrets; print(secrets.token_hex(32))"

# Hash du mot de passe admin
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('votre-mdp'))"
```

Reporter les valeurs obtenues dans `SECRET_KEY` et `ADMIN_PASSWORD_HASH`, puis ajouter votre `ANTHROPIC_API_KEY`.

> Les garde-fous `ENABLE_EMAIL_DELIVERY`, `ENABLE_AUTO_QUEUE`, `ENABLE_ADMIN_PURGE` et `ENABLE_RUNTIME_SETTINGS` restent à `false` par défaut. En phase de développement/test, aucun email n'est envoyé réellement.

### 3. Frontend

```bash
cd frontend
npm install
```

---

## Lancement

Deux terminaux sont nécessaires.

**Terminal 1 — Backend (API)**
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

- API : http://localhost:8000
- Documentation interactive : http://localhost:8000/docs
- Vérification santé : http://localhost:8000/health

**Terminal 2 — Frontend (dashboard)**
```bash
cd frontend
npm run dev
```

Le dashboard est accessible sur http://localhost:5173. Identifiant admin : voir `ADMIN_USERNAME` et `ADMIN_PASSWORD_HASH` dans `.env`.

**Worker asynchrone (optionnel)**
```bash
celery -A app.worker worker --loglevel=info
```

---

## Développement

```bash
# Tests backend
pytest tests/ -v

# Qualité de code (backend)
ruff check .
black --check .

# Tests & qualité frontend
cd frontend
npm run test
npm run lint
```

---

## Structure du projet

```
Agent/
├── app/
│   ├── main.py            # Point d'entrée FastAPI
│   ├── config.py          # Configuration & variables d'environnement
│   ├── database.py        # Connexion base de données (async)
│   ├── auth.py            # Authentification JWT
│   ├── models/            # Modèles SQLAlchemy (Lead, Contact, Campaign, Message…)
│   ├── schemas/           # Schémas Pydantic
│   ├── api/               # Routes API (leads, campaigns, agent, sources…)
│   ├── agent/             # Agent autonome (Tool Use Claude)
│   └── services/          # Logique métier (enrichissement, scoring, IA, envoi…)
├── frontend/              # Dashboard React + Vite
│   └── src/pages/         # Dashboard, Leads, Campaigns, Agent, Messages…
├── data/                  # Base SQLite & fichiers d'import
├── docs/                  # Documentation détaillée
├── requirements.txt
└── .env.example
```

---

## Sécurité & conformité

- Authentification JWT obligatoire sur toutes les routes (hors login).
- Aucune clé API n'est versionnée : tout passe par `.env` (ignoré par git).
- En-têtes de sécurité HTTP et rate limiting activés côté API.
- Respect du RGPD (opt-out) et des conditions d'utilisation des plateformes tierces.
- Garde-fous par défaut sur les actions irréversibles (envoi réel, purge de données).

---

## Documentation

- [Manuel Utilisateur](docs/MANUEL_UTILISATEUR.md) — utilisation du dashboard
- [Documentation Technique](docs/DOCUMENTATION_TECHNIQUE.md) — architecture, API, sécurité
- [Plan de Développement & Test](docs/PLAN_DEVELOPPEMENT_TEST.md)
- API interactive : http://localhost:8000/docs (backend démarré)
