# Documentation Technique — Agent de Prospection Kawanah Tourisme

> Dernière mise à jour : 27 avril 2026

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture technique](#2-architecture-technique)
3. [Base de données — Modèles](#3-base-de-données--modèles)
4. [API — Tous les endpoints](#4-api--tous-les-endpoints)
5. [Services — Logique métier](#5-services--logique-métier)
6. [Agent autonome](#6-agent-autonome)
7. [Frontend — Interface](#7-frontend--interface)
8. [Flux de données — Workflows](#8-flux-de-données--workflows)
9. [Algorithmes clés](#9-algorithmes-clés)
10. [Sécurité](#10-sécurité)
11. [Configuration](#11-configuration)
12. [Tests](#12-tests)
13. [Git Hooks](#13-git-hooks)
14. [Commandes utiles](#14-commandes-utiles)

---

## 1. Vue d'ensemble

### Objectif

Automatiser la prospection commerciale B2B pour proposer des services de **création web** aux établissements du secteur hospitalité (hôtels, campings, gîtes, etc.).

### Offre commerciale (Kawanah Tourisme)

| Service | Description |
|---------|-------------|
| Sites internet | Sites vitrines, sites de réservation — avec socle SEO & IA natif |
| Landing pages | Pages de conversion optimisées pour Google et IA |
| SEO | Référencement naturel (Google, Bing) |
| GEO | Generative Engine Optimization — optimisation pour les IA (ChatGPT, Perplexity, Claude) |

### Cible

| Critère | Valeur |
|---------|--------|
| Secteur | Hospitalité |
| Types | Hôtels, campings, gîtes, chambres d'hôtes, résidences, activités |
| Décideurs | Dirigeants (CEO, DG) + Responsables métier |
| Zone | France + Francophonie |

### Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async) |
| Base de données | SQLite (dev) / PostgreSQL (prod) |
| Frontend | React 19 / Vite / Tailwind CSS |
| IA | Claude API (Anthropic) — génération de messages + agent autonome |
| Scraping | httpx / BeautifulSoup |
| Email | SMTP (configurable) |
| Tests | pytest (backend) / Vitest + @testing-library/react (frontend) |

---

## 2. Architecture technique

```
Agent/
├── app/
│   ├── main.py                 # Point d'entrée FastAPI + middlewares
│   ├── config.py               # Variables d'environnement (Pydantic Settings)
│   ├── database.py             # Moteur SQLAlchemy async + sessions
│   ├── auth.py                 # JWT (création, validation, bcrypt)
│   ├── models/                 # Modèles ORM (tables)
│   │   ├── lead.py             # Lead (prospect)
│   │   ├── contact.py          # Contact (décideur)
│   │   ├── campaign.py         # Campagne de prospection
│   │   ├── message.py          # Message envoyé/reçu
│   │   └── gouv_import_job.py  # Job d'import data.gouv.fr
│   ├── schemas/                # Schémas Pydantic (validation API)
│   │   ├── lead.py
│   │   ├── contact.py
│   │   ├── campaign.py
│   │   └── message.py
│   ├── api/                    # Routes API (endpoints)
│   │   ├── auth.py             # Login / me
│   │   ├── leads.py            # CRUD leads + import + export
│   │   ├── contacts.py         # CRUD contacts
│   │   ├── campaigns.py        # CRUD campagnes + lancement
│   │   ├── messages.py         # CRUD messages + envoi + tracking
│   │   ├── enrichment.py       # Enrichissement des leads
│   │   ├── scoring.py          # Analyse web + scoring
│   │   ├── ai_messages.py      # Génération IA de messages
│   │   ├── reviews.py          # Analyse avis Google
│   │   ├── agent.py            # Chat avec l'agent IA
│   │   ├── gouv_data.py        # Import data.gouv.fr
│   │   └── settings.py         # Configuration (clés API, SMTP)
│   ├── services/               # Logique métier
│   │   ├── import_service.py         # Import CSV/Excel
│   │   ├── enrichment_service.py     # Scraping + APIs tierces
│   │   ├── scoring_service.py        # Analyse de site web
│   │   ├── ai_service.py            # Génération de messages (Claude)
│   │   ├── sequence_service.py       # Séquençage + file d'envoi
│   │   ├── email_service.py          # Envoi SMTP
│   │   ├── google_reviews_service.py # Google Places API
│   │   └── web_verification_service.py # Vérification d'URL
│   └── agent/                  # Agent autonome
│       ├── agent_service.py    # Cerveau de l'agent (Claude Tool Use)
│       └── agent_tools.py      # Définitions des outils
├── frontend/
│   └── src/
│       ├── App.jsx             # Routes + layout + garde auth
│       ├── config.js           # URL API
│       ├── hooks/useAuth.js    # Authentification (JWT), intercepteurs axios, logout
│       ├── components/
│       │   ├── Layout.jsx      # Sidebar + navigation
│       │   └── ErrorBoundary.jsx
│       ├── pages/
│       │   ├── Login.jsx       # Page de connexion
│       │   ├── Dashboard.jsx   # Tableau de bord
│       │   ├── Leads.jsx       # Gestion des leads
│       │   ├── Campaigns.jsx   # Gestion des campagnes
│       │   ├── Import.jsx      # Import de fichiers
│       │   ├── Enrichment.jsx  # Enrichissement
│       │   ├── Messages.jsx    # Messages envoyés/reçus
│       │   ├── Agent.jsx       # Chat avec l'agent IA
│       │   └── Settings.jsx    # Configuration
│       └── test/               # Vitest + @testing-library/react
│           └── ...
├── tests/                      # Tests pytest
│   ├── conftest.py             # DB in-memory + fixtures client HTTP
│   ├── test_auth.py
│   ├── test_leads.py
│   └── test_services.py
├── data/                       # Fichiers CSV + base SQLite
├── docs/                       # Documentation
├── .husky/                     # Git hooks
│   ├── pre-commit              # Prettier + ESLint + Ruff + Black
│   └── pre-push                # Vitest
├── .env                        # Variables d'environnement (non commité)
├── pytest.ini
├── requirements.txt
└── CLAUDE.md
```

---

## 3. Base de données — Modèles

### 3.1 Lead (table `leads`)

> Un lead = un établissement prospect.

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Identifiant unique |
| `name` | str(255) | Nom de l'établissement |
| `lead_type` | enum | hotel, camping, gite, chambre_hotes, residence, activite, other |
| `status` | enum | new, enriched, contacted, responded, interested, not_interested, converted, invalid |
| **Taille** | | |
| `capacity` | int? | Capacité d'accueil (personnes) |
| `room_count` | int? | Nombre de chambres (hôtels) |
| `pitch_count` | int? | Nombre d'emplacements (campings) |
| `star_rating` | str? | Classement étoiles |
| **Localisation** | | |
| `address` | str? | Adresse postale |
| `city` | str? | Ville |
| `postal_code` | str? | Code postal |
| `region` | str? | Région |
| `country` | str | Pays (défaut: "France") |
| **Contact** | | |
| `website` | str? | URL du site web |
| `phone` | str? | Téléphone |
| `email` | str? | Email |
| **Réseaux sociaux** | | |
| `linkedin_url` | str? | URL LinkedIn |
| `facebook_url` | str? | URL Facebook |
| `instagram_url` | str? | URL Instagram |
| **Analyse web** | | |
| `has_website` | bool? | A un site web fonctionnel (confirmé) |
| `website_quality_score` | int? | Qualité du site (0-100) |
| `has_booking_system` | bool? | Système de réservation en ligne |
| `is_mobile_friendly` | bool? | Compatible mobile |
| `seo_score` | int? | Score SEO (0-100) |
| `geo_score` | int? | Score GEO/IA (0-100) |
| **Avis Google** | | |
| `google_place_id` | str? | ID Google Places |
| `google_rating` | float? | Note moyenne (1.0-5.0) |
| `google_reviews_count` | int? | Nombre d'avis |
| `google_reviews_frequency` | float? | Avis par mois |
| `google_reviews_trend` | str? | "growing", "stable", "declining" |
| **Scoring** | | |
| `score` | int | Score global 0-100 (défaut: 0) |
| **Métadonnées** | | |
| `source` | str? | Origine ("csv_import", "data.gouv.fr") |
| `external_id` | str? | ID officiel Atout France |
| `notes` | text? | Notes libres |
| `created_at` | datetime | Date de création |
| `updated_at` | datetime | Dernière modification |
| `enriched_at` | datetime? | Date d'enrichissement |

**Index** : `name`, `city`, `status`, `score`, `external_id`, `google_place_id`, composite `(status, score)`

**Relations** : → contacts (1:N), → messages (1:N)

**Cycle de vie du statut** :
```
NEW → ENRICHED → CONTACTED → RESPONDED → INTERESTED → CONVERTED
                                       → NOT_INTERESTED
                              → INVALID
```

### 3.2 Contact (table `contacts`)

> Un contact = un décideur au sein d'un établissement.

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Identifiant |
| `lead_id` | int (FK) | Lien vers le lead |
| `first_name` | str? | Prénom |
| `last_name` | str? | Nom |
| `full_name` | str | Nom complet |
| `job_title` | str? | Poste |
| `role` | enum | owner, director, manager, marketing, it, other |
| `email` | str? | Email professionnel |
| `phone` | str? | Téléphone |
| `mobile` | str? | Mobile |
| `linkedin_url` | str? | Profil LinkedIn |
| `email_verified` | bool | Email vérifié (défaut: false) |
| `email_confidence` | int? | Confiance email 0-100 |
| `source` | str? | Source (hunter, linkedin, website) |

**Relations** : → lead (N:1), → messages (1:N)

### 3.3 Campaign (table `campaigns`)

> Une campagne = une séquence de prospection vers un groupe de leads.

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Identifiant |
| `name` | str(255) | Nom de la campagne |
| `description` | text? | Description |
| `status` | enum | draft, scheduled, running, paused, completed, cancelled |
| `channel` | enum | email, linkedin, multi |
| **Ciblage** | | |
| `lead_types` | str? | Types ciblés (JSON) |
| `regions` | str? | Régions ciblées (JSON) |
| `min_score` | int | Score minimum (défaut: 0) |
| **Templates** | | |
| `email_subject_template` | str? | Template objet email |
| `email_body_template` | text? | Template corps email |
| `linkedin_message_template` | text? | Template message LinkedIn |
| **IA** | | |
| `use_ai_generation` | bool | Générer via IA (défaut: true) |
| `ai_personalization_level` | str | low, medium, high (défaut: medium) |
| **Séquençage** | | |
| `follow_up_days` | int | Jours avant relance (défaut: 7) |
| `max_follow_ups` | int | Nombre max de relances (défaut: 2) |
| **Statistiques** | | |
| `total_leads` | int | Leads ciblés |
| `emails_sent` | int | Emails envoyés |
| `emails_opened` | int | Emails ouverts |
| `emails_clicked` | int | Emails cliqués |
| `responses_received` | int | Réponses reçues |
| `positive_responses` | int | Réponses positives |

**Propriétés calculées** : `open_rate` (%), `response_rate` (%)

### 3.4 Message (table `messages`)

> Un message = un email ou message LinkedIn envoyé ou reçu.

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Identifiant |
| `campaign_id` | int? (FK) | Campagne parente |
| `lead_id` | int (FK) | Lead concerné |
| `contact_id` | int? (FK) | Contact destinataire |
| `channel` | enum | email, linkedin |
| `direction` | enum | outbound (envoyé), inbound (reçu) |
| `status` | enum | draft, queued, sent, delivered, opened, clicked, replied, bounced, failed |
| `subject` | str? | Objet |
| `body` | text | Corps du message (texte) |
| `body_html` | text? | Corps HTML |
| `sequence_number` | int | 1 = premier contact, 2+ = relances |
| `parent_message_id` | int? (FK) | Message parent (pour les réponses) |
| **Analyse** | | |
| `sentiment` | enum? | positive, neutral, negative, unknown |
| `sentiment_score` | float? | Score -1.0 à 1.0 |
| `ai_analysis` | text? | Analyse IA complète |
| **Tracking** | | |
| `external_id` | str? | ID fournisseur (SendGrid) |
| `scheduled_at` | datetime? | Date d'envoi programmée |
| `sent_at` | datetime? | Date d'envoi effective |
| `opened_at` | datetime? | Date d'ouverture |
| `received_at` | datetime? | Date de réception (inbound) |

### 3.5 GouvImportJob (table `gouv_import_jobs`)

> Un job d'import depuis l'API data.gouv.fr.

| Champ | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Identifiant |
| `status` | enum | pending, running, paused, completed, failed |
| `dataset_id` | str | ID du dataset data.gouv.fr |
| `resource_id` | str? | ID de la ressource |
| `current_page` | int | Page courante (pour reprise) |
| `total_pages` | int? | Pages totales |
| `total_fetched` | int | Enregistrements récupérés |
| `total_created` | int | Leads créés |
| `total_skipped` | int | Doublons ignorés |
| `total_errors` | int | Erreurs |
| `lead_types_json` | str? | Types à importer |
| `region_filter` | str? | Filtre région |
| `department_filter` | str? | Filtre département |
| `error_message` | text? | Dernier message d'erreur |

**Propriété** : `progress_pct` (%) — supporte la reprise après interruption.

---

## 4. API — Tous les endpoints

### 4.1 Authentification (`/api/auth`) — PUBLIC

| Méthode | Route | Description | Rate limit |
|---------|-------|-------------|------------|
| POST | `/login` | Connexion (retourne JWT) | 10/min |
| GET | `/me` | Utilisateur connecté | — |

### 4.2 Leads (`/api/leads`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Liste paginée + filtres (status, type, score, city, has_website) |
| GET | `/names?ids=1,2,3` | Noms en batch (max 200) — évite les requêtes N+1 |
| GET | `/export` | Export CSV filtré |
| GET | `/stats` | Statistiques globales |
| GET | `/{lead_id}` | Détail d'un lead |
| POST | `/import` | Import depuis fichier local (dossier `data/` uniquement) |
| POST | `/upload` | Upload + import Excel/CSV |
| DELETE | `/{lead_id}` | Supprimer un lead |
| DELETE | `/` | Supprimer tous les leads (confirmation requise) |

### 4.3 Contacts (`/api/contacts`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Liste + filtres (lead_id, role, email_verified) |
| GET | `/{contact_id}` | Détail |
| POST | `/` | Créer un contact |
| PATCH | `/{contact_id}` | Modifier |
| DELETE | `/{contact_id}` | Supprimer |
| GET | `/by-lead/{lead_id}` | Contacts d'un lead |

### 4.4 Campagnes (`/api/campaigns`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Liste paginée |
| GET | `/queue-stats` | Statistiques de la file d'envoi |
| POST | `/process-queue` | Traiter la file d'envoi |
| GET | `/{id}` | Détail |
| GET | `/{id}/stats` | Statistiques détaillées |
| GET | `/{id}/preview-leads` | Aperçu des leads éligibles |
| POST | `/` | Créer une campagne |
| PATCH | `/{id}` | Modifier |
| POST | `/{id}/start` | Lancer (génère les messages) |
| POST | `/{id}/pause` | Mettre en pause |
| POST | `/{id}/stop` | Terminer |
| DELETE | `/{id}` | Supprimer |

### 4.5 Messages (`/api/messages`) — JWT requis

| Méthode | Route | Description | Rate limit |
|---------|-------|-------------|------------|
| GET | `/` | Liste + filtres (campaign, lead, channel, direction, status) | — |
| GET | `/{id}` | Détail | — |
| POST | `/` | Créer (brouillon) | — |
| POST | `/inbound` | Enregistrer une réponse reçue | — |
| PATCH | `/{id}` | Modifier | — |
| POST | `/{id}/queue` | Mettre en file d'envoi | — |
| POST | `/{id}/mark-sent` | Marquer comme envoyé | — |
| POST | `/{id}/mark-opened` | Marquer comme ouvert (tracking) | — |
| POST | `/{id}/send-test` | Envoyer un test | 5/min |
| DELETE | `/{id}` | Supprimer | — |
| GET | `/by-lead/{lead_id}` | Messages d'un lead | — |

### 4.6 Enrichissement (`/api/enrichment`) — JWT requis

| Méthode | Route | Description | Rate limit |
|---------|-------|-------------|------------|
| GET | `/stats` | Statistiques d'enrichissement | — |
| POST | `/batch` | Lancer un job d'enrichissement (async) | 5/min |
| GET | `/job/{job_id}` | Progression du job | — |
| GET | `/status/{lead_id}` | Statut d'enrichissement d'un lead | — |
| POST | `/{lead_id}` | Enrichir un lead (free ou paid APIs) | — |

### 4.7 Scoring (`/api/scoring`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/analyze/{lead_id}` | Analyser le site web + mettre à jour les scores |
| POST | `/analyze/batch` | Analyse en lot |
| GET | `/priority` | Leads par segment de priorité |
| GET | `/stats` | Statistiques de scoring |
| POST | `/recalculate` | Recalculer tous les scores |

### 4.8 Génération IA (`/api/ai`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/generate/{lead_id}` | Générer un message personnalisé |
| POST | `/generate/batch` | Génération en lot (par segment) |
| POST | `/variations/{lead_id}` | Générer 3 variations A/B test |
| GET | `/templates` | Templates par segment |

### 4.9 Avis Google (`/api/reviews`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/{lead_id}/analyze` | Analyser les avis Google |
| GET | `/{lead_id}` | Données d'avis (cache) |
| POST | `/batch` | Analyse en lot |
| GET | `/stats/overview` | Vue d'ensemble |

### 4.10 Agent IA (`/api/agent`) — JWT requis

| Méthode | Route | Description | Rate limit |
|---------|-------|-------------|------------|
| POST | `/chat` | Envoyer un message à l'agent | 20/min |
| POST | `/chat/stream` | Version streaming (SSE) | 20/min |
| POST | `/respond` | Répondre à une question de l'agent | 20/min |
| GET | `/session/{id}` | État de la session |  — |
| DELETE | `/session/{id}` | Réinitialiser la session | — |
| GET | `/tools` | Outils disponibles | — |
| GET | `/examples` | Exemples de prompts | — |

### 4.11 data.gouv.fr (`/api/gouv`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/jobs` | Créer un job d'import |
| POST | `/jobs/{id}/start` | Lancer/reprendre |
| POST | `/jobs/{id}/pause` | Mettre en pause |
| GET | `/jobs` | Liste des jobs |
| GET | `/jobs/{id}` | Détail d'un job |
| GET | `/datasets/search` | Rechercher des datasets |

### 4.12 Paramètres (`/api/settings`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Configuration actuelle (clés masquées) |
| PUT | `/` | Sauvegarder la configuration |
| POST | `/test-email` | Tester la configuration SMTP |

### 4.13 Admin (`/api/admin`) — JWT requis

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/purge` | Vider toutes les données (garde la structure) |

---

## 5. Services — Logique métier

### 5.1 Import Service (`import_service.py`)

**Rôle** : Importer des leads depuis des fichiers CSV/Excel.

**Flux** :
1. Lecture du fichier avec Pandas (Excel ou CSV)
2. Validation de chaque ligne avec le schéma `LeadImportRow`
3. Normalisation : accents, formats de téléphone, codes postaux
4. Déduplication par nom d'établissement
5. Création ou mise à jour des leads en base

**Classe `TextNormalizer`** :
- `normalize_text()` — Nettoie les caractères spéciaux
- `normalize_name()` — Met en forme les noms propres
- `normalize_city()` — Standardise les noms de ville
- `normalize_postal_code()` — Formate les codes postaux (5 chiffres)
- `normalize_phone()` — Formate les numéros français

### 5.2 Enrichment Service (`enrichment_service.py`)

**Rôle** : Trouver automatiquement les informations de contact à partir du nom d'établissement.

**Sources gratuites** :
- Site web de l'établissement (scraping : email, téléphone, réseaux sociaux)
- PagesJaunes (téléphone, email)
- Societe.com (noms des dirigeants)
- DuckDuckGo (recherche email/contact)
- Génération de patterns d'email (prenom.nom@domaine.com)

**Sources payantes** (optionnelles) :
- Hunter.io (contacts avec emails vérifiés)

**Parallélisation** : `asyncio.Semaphore(3)` — max 3 enrichissements simultanés avec 1s de pause entre chaque (anti rate-limiting).

### 5.3 Scoring Service (`scoring_service.py`)

**Rôle** : Analyser le site web d'un établissement et calculer les scores.

**3 dimensions d'analyse** :

| Score | Cible | Mesure |
|-------|-------|--------|
| Quality (0-100) | Site web | Design, modernité, navigation |
| SEO (0-100) | Google | Title, meta, H1, alt text, schema.org |
| GEO (0-100) | IA (ChatGPT, Perplexity) | Données structurées, FAQ, LocalBusiness |

**Détections supplémentaires** :
- Mobile-friendly (responsive)
- Système de réservation (Booking.com, Reservit, etc.)
- HTTPS
- Temps de chargement

**Cache** : Si `website_quality_score` existe et `updated_at < 7 jours` → analyse web ignorée (sauf `force=True`).

### 5.4 AI Service (`ai_service.py`)

**Rôle** : Générer des messages de prospection personnalisés avec Claude.

**Templates par segment** :

| Segment | Stratégie |
|---------|-----------|
| SANS SITE | "Créez votre présence web" |
| À VÉRIFIER | "Votre site a un problème" |
| CHAUD | "Refonte nécessaire" |
| TIÈDE + mauvais GEO | "Optimisez pour les IA" |
| FROID + mauvais GEO | "Avantage GEO" |

**Personnalisation** :
- Contexte lead complet (scores, avis Google, taille, type)
- Canal adapté (email long vs LinkedIn court)
- Ton ajustable (professional, friendly, direct)
- Instructions custom (avec protection anti-injection de prompt)

**A/B Testing** : `generate_variations()` → 3 versions (professional, friendly, direct).

### 5.5 Sequence Service (`sequence_service.py`)

**Rôle** : Orchestrer l'envoi des messages de campagne.

**Contraintes** :
| Paramètre | Valeur |
|-----------|--------|
| Emails max/jour | 50 (warm-up progressif) |
| Délai entre emails | 60 secondes minimum |
| Relances | Configurable (défaut: J+7, max 2 relances) |

**Flux** :
1. `launch_campaign()` → trouve les leads éligibles, génère les messages, programme les envois
2. `process_queue()` → envoie les messages programmés en respectant les quotas
3. `schedule_followup()` → planifie les relances automatiques

### 5.6 Email Service (`email_service.py`)

**Rôle** : Envoyer des emails via SMTP.

- Validation du format email avant envoi
- Support texte brut + HTML
- Configuration SMTP flexible (Gmail, SendGrid, Mailgun, etc.)

### 5.7 Google Reviews Service (`google_reviews_service.py`)

**Rôle** : Analyser les avis Google d'un établissement via Google Places API.

**Données collectées** :
- `place_id` — Identifiant Google
- `rating` — Note moyenne (1.0-5.0)
- `reviews_count` — Nombre total d'avis
- `frequency` — Avis par mois
- `trend` — Tendance : growing / stable / declining

---

## 6. Agent autonome

### Architecture

L'agent utilise **Claude avec Tool Use** pour agir de façon autonome ou semi-autonome.

### Modes de fonctionnement

| Mode | Comportement |
|------|-------------|
| **Supervisé** (défaut) | L'agent propose des actions, attend validation humaine avant envoi |
| **Autonome** | L'agent exécute les actions sans validation (emails envoyés automatiquement) |
| **Manuel** | L'agent conseille uniquement, n'exécute rien |

### Outils disponibles

| Outil | Description |
|-------|-------------|
| `search_leads` | Chercher des prospects (par segment, ville, type) |
| `get_lead_details` | Détails complets d'un lead |
| `analyze_lead_website` | Analyser et scorer un site web |
| `analyze_google_reviews` | Analyser les avis Google |
| `generate_message` | Générer un email personnalisé |
| `queue_email` | Mettre un email en file d'envoi |
| `get_statistics` | Métriques globales |
| `request_human_decision` | Demander une décision humaine |

### Sessions

- TTL de 30 minutes d'inactivité
- Nettoyage automatique des sessions expirées
- Historique de conversation persisté par session
- Stockage en mémoire (`agent_sessions` dict)

### Mode démo

Si la clé API Claude n'est pas configurée, l'agent fonctionne en **mode démo** avec des réponses simulées. Un message système avertit l'utilisateur.

---

## 7. Frontend — Interface

### Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | Connexion avec JWT |
| Dashboard | `/` | Vue d'ensemble (stats, graphiques, leads récents) |
| Leads | `/leads` | Gestion des leads (tableau, filtres, détail, export) |
| Campagnes | `/campaigns` | Création, lancement, suivi des campagnes |
| Import | `/import` | Upload fichiers CSV/Excel + import data.gouv.fr |
| Enrichissement | `/enrichment` | Lancement et suivi de l'enrichissement |
| Messages | `/messages` | Historique des messages envoyés/reçus |
| Agent | `/agent` | Chat interactif avec l'agent IA |
| Settings | `/settings` | Configuration (clés API, SMTP, etc.) |

### Navigation

Sidebar repliable (280px → 80px) avec icônes Lucide React et animations Framer Motion.

### Validations côté client

- **Import** : Extensions autorisées (.csv, .xlsx, .xls), taille max 10 Mo
- **Formulaires** : Validation en temps réel
- **Erreurs** : ErrorBoundary sur chaque page + page 404

### Optimisations

- **Batch API** (`/api/leads/names`) pour éviter les requêtes N+1 dans Messages et Campaigns
- **Auto-refresh** du Dashboard toutes les 30 secondes
- **SessionStorage** pour l'historique agent (nettoyé au logout)

---

## 8. Flux de données — Workflows

### 8.1 Import → Enrichissement → Scoring → Campagne

```
┌─────────────────────────────────────────────────────┐
│  1. IMPORT                                          │
│                                                     │
│  CSV/Excel ──→ Normalisation ──→ Déduplication      │
│  data.gouv.fr ──→ API paginée ──→ Leads (NEW)      │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  2. ENRICHISSEMENT                                  │
│                                                     │
│  Lead (NEW) ──→ Scraping web ──→ Email, Téléphone   │
│              ──→ Réseaux sociaux                    │
│              ──→ Contacts (dirigeants)              │
│              ──→ Lead (ENRICHED)                    │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  3. SCORING & ANALYSE                               │
│                                                     │
│  Lead ──→ Analyse site web (Quality, SEO, GEO)      │
│       ──→ Avis Google (note, tendance)              │
│       ──→ Score 0-100 ──→ Segment de priorité       │
│                                                     │
│  🔥 SANS SITE  │  ⚠️ À VÉRIFIER  │  🔥 CHAUD       │
│  😐 TIÈDE      │  ❄️ FROID                          │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  4. CAMPAGNE                                        │
│                                                     │
│  Sélection leads ──→ Génération IA ──→ File d'envoi │
│                  ──→ Envoi SMTP (50/jour max)       │
│                  ──→ Relances automatiques (J+7)    │
│                  ──→ Lead (CONTACTED)               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  5. SUIVI DES RÉPONSES                              │
│                                                     │
│  Réponse reçue ──→ Analyse de sentiment             │
│               ──→ RESPONDED → INTERESTED/NOT_INT.   │
│               ──→ Suggestion de réponse IA          │
└─────────────────────────────────────────────────────┘
```

### 8.2 Flux Agent Autonome

```
Utilisateur : "Trouve des hôtels sans site à Paris et propose-leur un email"
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  AGENT (Claude Tool Use)                            │
│                                                     │
│  1. search_leads(type=hotel, city=Paris, sans_site) │
│  2. get_lead_details(lead_id=42)                    │
│  3. analyze_google_reviews(lead_id=42)              │
│  4. generate_message(lead_id=42, channel=email)     │
│                                                     │
│  Mode SUPERVISÉ :                                   │
│  → "Voici l'email généré. Dois-je l'envoyer ?"     │
│  → Attente validation humaine                       │
│                                                     │
│  Mode AUTONOME :                                    │
│  → queue_email() → envoi automatique                │
└─────────────────────────────────────────────────────┘
```

---

## 9. Algorithmes clés

### 9.1 Scoring des leads (0-100)

Le score détermine la priorité de prospection. Plus le score est élevé, plus l'établissement a besoin de nos services.

```
PRÉSENCE WEB                                    POINTS
├─ Pas de site web (confirmé)                    +30
├─ URL connue mais site inaccessible             +35
├─ Site web qualité < 40/100                     +40  ← Priorité max !
├─ Site web qualité 40-60                        +20
├─ Site non mobile-friendly                      +15
├─ Pas de réservation en ligne                   +10
│
SEO & GEO
├─ SEO < 40/100                                  +20
├─ SEO 40-60                                     +10
├─ GEO < 40/100 (pas optimisé pour les IA)       +15
├─ GEO 40-60                                     +8
│
TYPE D'ÉTABLISSEMENT
├─ Hôtel                                         +15
├─ Camping / Résidence                           +10
├─ Gîte / Chambre d'hôtes                        +8
├─ Activité                                      +5
│
TAILLE (chambres / emplacements / capacité)
├─ Très grand (100+ chambres, 200+ emplacements) +15
├─ Grand                                         +12
├─ Moyen                                         +8
├─ Petit                                         +5
│
AVIS GOOGLE
├─ 100+ avis (très populaire)                    +10
├─ 50+ avis                                      +7
├─ 20+ avis                                      +5
├─ Fréquence 5+/mois                             +8
├─ Fréquence 2-5/mois                            +5
├─ Fréquence < 0.5/mois                          +3
├─ Tendance "declining"                          +8
├─ Tendance "growing"                            +5
├─ Note < 3.5                                    +10
├─ Note >= 4.5                                   +3
│
                                    TOTAL plafonné à 100
```

### 9.2 Segments de priorité

| Segment | Condition | Signification |
|---------|-----------|---------------|
| 🔥 SANS SITE | Pas d'URL de site web | Meilleur prospect — besoin évident |
| ⚠️ À VÉRIFIER | URL valide mais `has_website=False` | Site inaccessible/expiré |
| 🔥 CHAUD | Score >= 80 | Forte probabilité de conversion |
| 😐 TIÈDE | Score 50-79 | Potentiel à développer |
| ❄️ FROID | Score < 50 | Faible priorité |

### 9.3 Logique importante du scoring

- `has_website=None` (non enrichi) → **aucun bonus**. On ne suppose jamais l'absence de site tant que l'enrichissement n'a pas confirmé.
- Seul `has_website=False` (confirmé après enrichissement) déclenche les bonus "pas de site".
- Le score est recalculé après chaque enrichissement et chaque analyse.

---

## 10. Sécurité

### Authentification

| Mécanisme | Détail |
|-----------|--------|
| JWT | HS256, expiration 24h |
| Mots de passe | Hashés avec bcrypt |
| Route publique | Uniquement `/api/auth/login` |
| Toutes autres routes | JWT obligatoire (Bearer token) |

### Protection des endpoints

| Protection | Détail |
|------------|--------|
| Rate limiting | slowapi — Login 10/min, Agent 20/min, Email test 5/min, Enrichment batch 5/min |
| CORS | Origins explicites (dev + prod) |
| Headers sécurité | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy |
| Path traversal | Import limité au dossier `data/` — vérification `startswith` |
| Injection SQL | SQLAlchemy ORM (requêtes paramétrées) |
| XSS email | `html.escape()` sur le body avant injection dans template HTML |
| Injection SMTP | Regex validation sur toutes les adresses email |
| Injection de prompt | Sanitisation des instructions custom IA (500 chars max + patterns bloqués) |
| SSL/TLS | `ssl.create_default_context(cafile=certifi.where())` |
| Debug | `DEBUG=false` en production (no SQL logs) |

### Session agent

| Mécanisme | Détail |
|-----------|--------|
| TTL | 30 minutes d'inactivité |
| Nettoyage | Automatique à chaque requête |
| Stockage | En mémoire (non persisté) |
| Logout | Nettoyage sessionStorage côté client |

---

## 11. Configuration

### Variables d'environnement (`.env`)

```bash
# Application
APP_NAME="Agent Prospection Kawanah Tourisme"
APP_ENV="development"          # development | production
DEBUG=False

# Base de données
DATABASE_URL=sqlite+aiosqlite:///./data/prospection.db

# IA — Claude API
ANTHROPIC_API_KEY=sk-ant-...   # Requis pour l'agent et la génération de messages

# Enrichissement
HUNTER_API_KEY=...             # Optionnel — enrichissement payant
GOOGLE_PLACES_API_KEY=...      # Optionnel — avis Google

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=...
EMAIL_FROM=Kawanah Tourisme <team@kawanah.com>

# Authentification
SECRET_KEY=...                 # Clé de signature JWT (openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440        # 24h
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=...        # Hash bcrypt du mot de passe

# CORS
ALLOWED_ORIGINS=http://localhost:5173

# Redis (optionnel, pour Celery)
REDIS_URL=redis://localhost:6379/0
```

Générer `SECRET_KEY` :
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Générer `ADMIN_PASSWORD_HASH` :
```bash
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('votre-mdp'))"
```

---

## 12. Tests

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

| Fichier | Contenu |
|---------|---------|
| `test_auth.py` | Protection JWT, routes publiques |
| `test_leads.py` | Liste, pagination, filtres, 404, stats, sécurité import |
| `test_services.py` | Validation email, SMTP injection, prompt injection |

**Frontend :**
```bash
cd frontend && npm run test
```

---

## 13. Git Hooks

| Hook | Déclencheur | Actions |
|------|-------------|---------|
| pre-commit | `git commit` | Prettier + ESLint (JS/JSX), Ruff + Black (Python) |
| pre-push | `git push` | Vitest (tests frontend) |

---

## 14. Commandes utiles

### Démarrage

```bash
# Backend
cd Agent
source venv/bin/activate
uvicorn app.main:app --reload        # → http://localhost:8000

# Frontend
cd frontend
npm run dev                          # → http://localhost:5173
```

### Maintenance

```bash
# Vider les données (garder la structure)
# POST /api/admin/purge (via l'API, authentifié)

# Tests
pytest
pytest tests/test_specific.py -v

# Linting
ruff check .
black --check .

# Formatage
black .
ruff --fix .
```

### Documentation API

Accessible à `http://localhost:8000/docs` (Swagger UI) ou `http://localhost:8000/redoc` (ReDoc) quand le backend tourne.

---

## Conventions

- **Code** : Anglais (variables, fonctions, commentaires techniques)
- **Contenu** : Français (messages de prospection, logs utilisateur)
- **Style** : PEP 8 + Black + Ruff (Python), Prettier + ESLint (JS)
- **Commits** : Format conventionnel (`feat:`, `fix:`, `docs:`, `test:`)
- **Branches** : `main` (prod), `develop` (dev), `feature/*`, `fix/*`
