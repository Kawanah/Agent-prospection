# Documentation Technique — Agent Prospection Kawanah Travel

## Vue d'ensemble

Application Python/React de prospection B2B automatisée pour le secteur de l'hospitalité.

**Stack :**
- Backend : FastAPI (async) + SQLAlchemy 2.0 + SQLite
- Frontend : React 19 + Vite + Tailwind CSS
- IA : Claude API (Anthropic)
- Auth : JWT (Bearer token, 24h)
- Tests : pytest (backend) + Vitest (frontend)

---

## Structure du projet

```
Agent/
├── app/
│   ├── main.py              # Point d'entrée FastAPI + middlewares
│   ├── config.py            # Settings (pydantic-settings, chargé depuis .env)
│   ├── database.py          # Moteur SQLAlchemy async + session
│   ├── auth.py              # JWT : create_access_token, get_current_user
│   │
│   ├── models/              # Tables SQLAlchemy
│   │   ├── lead.py          # Lead, LeadStatus, LeadType
│   │   ├── contact.py       # Contact
│   │   ├── campaign.py      # Campaign, CampaignStatus
│   │   ├── message.py       # Message, MessageChannel, MessageDirection
│   │   └── gouv_import_job.py
│   │
│   ├── schemas/             # Schémas Pydantic (validation entrées/sorties API)
│   │
│   ├── api/                 # Routers FastAPI
│   │   ├── auth.py          # POST /api/auth/login, GET /api/auth/me
│   │   ├── leads.py         # CRUD + import + export CSV + stats
│   │   ├── contacts.py      # CRUD contacts
│   │   ├── campaigns.py     # CRUD + preview leads + start/pause
│   │   ├── messages.py      # CRUD + queue + mark-sent + send-test
│   │   ├── enrichment.py    # Enrichissement individuel et en lot
│   │   ├── scoring.py       # Calcul scores
│   │   ├── ai_messages.py   # Génération messages IA
│   │   ├── agent.py         # Agent autonome (Claude + Tool Use)
│   │   ├── reviews.py       # Avis Google
│   │   ├── settings.py      # Lecture/écriture .env
│   │   └── gouv_data.py     # Import data.gouv.fr
│   │
│   ├── services/            # Logique métier
│   │   ├── import_service.py
│   │   ├── enrichment_service.py
│   │   ├── web_verification_service.py
│   │   ├── google_reviews_service.py
│   │   ├── scoring_service.py
│   │   ├── ai_service.py
│   │   ├── email_service.py
│   │   ├── sequence_service.py
│   │   └── gouv_data_service.py
│   │
│   └── agent/               # Agent autonome
│       ├── agent_service.py # Logique Claude + Tool Use
│       └── agent_tools.py   # Définition des outils
│
├── frontend/                # Dashboard React
│   ├── src/
│   │   ├── App.jsx          # Routeur principal + garde auth
│   │   ├── pages/           # Dashboard, Leads, Campaigns, Messages, etc.
│   │   ├── components/      # Layout, ErrorBoundary
│   │   ├── hooks/
│   │   │   └── useAuth.js   # Token JWT, intercepteurs axios, logout
│   │   └── test/            # Vitest + @testing-library/react
│   ├── .prettierrc
│   └── vite.config.js
│
├── tests/                   # Tests pytest
│   ├── conftest.py          # DB in-memory + fixtures client HTTP
│   ├── test_auth.py
│   ├── test_leads.py
│   └── test_services.py
│
├── data/                    # SQLite + fichiers d'import
├── docs/                    # Documentation
├── .husky/                  # Git hooks
│   ├── pre-commit           # Prettier + ESLint + Ruff + Black
│   └── pre-push             # Vitest
├── .env                     # Variables d'environnement (non commité)
├── pytest.ini
├── requirements.txt
└── CLAUDE.md
```

---

## Modèles de données

### Lead

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int | Clé primaire |
| `name` | str | Nom de l'établissement |
| `lead_type` | LeadType | hotel, camping, gite, residence, activity, other |
| `city` | str | Ville |
| `postal_code` | str | Code postal |
| `email` | str | Email principal |
| `phone` | str | Téléphone |
| `website` | str | URL site web |
| `has_website` | bool/None | None = non vérifié, True/False = vérifié |
| `website_quality_score` | int | Score qualité 0-100 |
| `score` | int | Score de priorisation 0-100 |
| `priority_level` | str | SANS SITE, CHAUD, TIEDE, FROID, À VÉRIFIER |
| `status` | LeadStatus | new, enriched, contacted, replied, converted, rejected |
| `google_place_id` | str | ID Google Places |
| `google_rating` | float | Note Google |
| `google_reviews_count` | int | Nombre d'avis |

### Campaign

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int | Clé primaire |
| `name` | str | Nom de la campagne |
| `channel` | MessageChannel | email, linkedin |
| `status` | CampaignStatus | draft, active, paused, completed |
| `sent_count` | int | Emails envoyés |
| `opened_count` | int | Emails ouverts |
| `replied_count` | int | Réponses reçues |

### Message

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int | Clé primaire |
| `lead_id` | int | FK → Lead |
| `campaign_id` | int | FK → Campaign (optionnel) |
| `channel` | MessageChannel | email, linkedin |
| `direction` | MessageDirection | outbound, inbound |
| `status` | MessageStatus | draft, queued, sent, delivered, opened, failed |
| `subject` | str | Objet |
| `body` | str | Corps du message |
| `sentiment` | SentimentType | positive, neutral, negative, unknown |

---

## API Endpoints

Toutes les routes (sauf `/`, `/health`, `/api/auth/login`) requièrent un header :
```
Authorization: Bearer <token>
```

### Authentification

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/auth/login` | Login → retourne JWT (form-data: username, password) |
| `GET` | `/api/auth/me` | Vérifie le token, retourne l'utilisateur |

Rate limit : 10 requêtes/minute sur `/login`.

### Leads

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/leads/` | Liste paginée (filtres: status, type, score, city, has_website) |
| `GET` | `/api/leads/stats` | Statistiques globales |
| `GET` | `/api/leads/export` | Export CSV (utf-8-sig) |
| `GET` | `/api/leads/{id}` | Détail d'un lead |
| `POST` | `/api/leads/import` | Import depuis data/ (query: file_path) |
| `POST` | `/api/leads/upload` | Import par upload multipart |
| `DELETE` | `/api/leads/{id}` | Supprimer un lead |
| `DELETE` | `/api/leads/` | Supprimer tous les leads (double confirmation requise) |

### Campaigns

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/campaigns/` | Liste toutes les campagnes |
| `POST` | `/api/campaigns/` | Créer une campagne |
| `GET` | `/api/campaigns/{id}` | Détail |
| `PATCH` | `/api/campaigns/{id}` | Modifier |
| `POST` | `/api/campaigns/{id}/start` | Démarrer |
| `POST` | `/api/campaigns/{id}/pause` | Mettre en pause |
| `GET` | `/api/campaigns/{id}/preview-leads` | Leads éligibles (avant démarrage) |

### Messages

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/messages/` | Liste paginée |
| `GET` | `/api/messages/{id}` | Détail |
| `POST` | `/api/messages/` | Créer (brouillon) |
| `PATCH` | `/api/messages/{id}` | Modifier |
| `POST` | `/api/messages/{id}/queue` | Mettre en file d'attente |
| `POST` | `/api/messages/{id}/mark-sent` | Marquer comme envoyé |
| `POST` | `/api/messages/{id}/mark-opened` | Marquer comme ouvert |
| `POST` | `/api/messages/{id}/send-test` | Envoyer en test (5/min max) |
| `DELETE` | `/api/messages/{id}` | Supprimer (brouillon/file uniquement) |
| `GET` | `/api/messages/by-lead/{lead_id}` | Historique d'un lead |
| `POST` | `/api/messages/inbound` | Enregistrer une réponse reçue |

### Génération IA

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/ai/generate/{lead_id}` | Générer un message pour un lead |
| `POST` | `/api/ai/generate/batch` | Générer pour un segment |
| `POST` | `/api/ai/variations/{lead_id}` | 3 variations A/B |
| `GET` | `/api/ai/templates` | Stratégies par segment |

### Agent

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/agent/chat` | Envoyer une instruction à l'agent |
| `GET` | `/api/agent/status` | État de l'agent |

### Enrichissement

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/enrichment/{lead_id}` | Enrichir un lead |
| `POST` | `/api/enrichment/batch` | Enrichir plusieurs leads |

### Paramètres

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/settings/` | Lire la config (clés masquées) |
| `PUT` | `/api/settings/` | Sauvegarder dans .env |
| `POST` | `/api/settings/test-email` | Envoyer un email de test SMTP |

---

## Authentification JWT

```
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=kawanah2026

→ { "access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400 }
```

Le token expire après 24h (configurable via `JWT_EXPIRE_MINUTES`).

Toutes les requêtes protégées nécessitent :
```
Authorization: Bearer eyJ...
```

---

## Sécurité

| Mesure | Détail |
|--------|--------|
| JWT Bearer | Toutes les routes API sauf login et health |
| Rate limiting | Login : 10/min — Send-test : 5/min (slowapi) |
| CORS | Origines explicites uniquement (env `ALLOWED_ORIGINS`) |
| HTTP Headers | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy |
| SQL Injection | SQLAlchemy ORM — requêtes paramétrées exclusivement |
| XSS email | `html.escape()` sur le body avant injection dans template HTML |
| SMTP injection | Regex validation sur toutes les adresses email |
| Prompt injection | Validation `custom_instructions` : 500 chars max + patterns bloqués |
| Path traversal | `Path(__file__).parent...` absolu + vérification `startswith` |
| SSL/TLS | `ssl.create_default_context(cafile=certifi.where())` |
| Debug | `DEBUG=false` en production (no SQL logs) |

---

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `APP_ENV` | development | Environnement |
| `DEBUG` | false | Logs SQL SQLAlchemy |
| `DATABASE_URL` | sqlite+aiosqlite:///./data/prospection.db | Base de données |
| `ANTHROPIC_API_KEY` | — | Clé API Claude (obligatoire) |
| `GOOGLE_PLACES_API_KEY` | — | API Google Places |
| `HUNTER_API_KEY` | — | Hunter.io (optionnel) |
| `SMTP_HOST` | smtp.gmail.com | Serveur SMTP |
| `SMTP_PORT` | 587 | Port SMTP |
| `SMTP_USER` | — | Utilisateur SMTP |
| `SMTP_PASSWORD` | — | Mot de passe SMTP |
| `EMAIL_FROM` | — | Adresse d'expédition |
| `SECRET_KEY` | — | Clé JWT (32 hex, obligatoire) |
| `JWT_ALGORITHM` | HS256 | Algorithme JWT |
| `JWT_EXPIRE_MINUTES` | 1440 | Durée token (24h) |
| `ADMIN_USERNAME` | admin | Identifiant admin |
| `ADMIN_PASSWORD_HASH` | — | Hash bcrypt du mot de passe |
| `ALLOWED_ORIGINS` | (vide = localhost) | Origines CORS prod (virgule-séparées) |

Générer `SECRET_KEY` :
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Générer `ADMIN_PASSWORD_HASH` :
```bash
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('votre-mdp'))"
```

---

## Tests

```bash
source venv/bin/activate

# Tous les tests
pytest tests/ -v

# Un fichier uniquement
pytest tests/test_auth.py -v

# Avec affichage des print()
pytest tests/ -s
```

**Couverture actuelle : 32 tests**

| Fichier | Tests |
|---------|-------|
| `test_auth.py` | Protection JWT, routes publiques |
| `test_leads.py` | Liste, pagination, filtres, 404, stats, sécurité import |
| `test_services.py` | Validation email, SMTP injection, prompt injection |

**Frontend :**
```bash
cd frontend && npm run test
```

---

## Git Hooks (automatiques)

| Hook | Déclencheur | Actions |
|------|-------------|---------|
| pre-commit | `git commit` | Prettier + ESLint (JS/JSX), Ruff + Black (Python) |
| pre-push | `git push` | Vitest (tests frontend) |

---

## Conventions

- **Code** : Anglais (variables, fonctions)
- **Contenu** : Français (messages, logs utilisateur)
- **Style** : PEP 8 + Black + Ruff (Python), Prettier + ESLint (JS)
- **Commits** : Format conventionnel (`feat:`, `fix:`, `docs:`, `test:`)
