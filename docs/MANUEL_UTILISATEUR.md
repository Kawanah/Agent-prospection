# Manuel Utilisateur — Agent Prospection Kawanah Tourisme

## Introduction

L'**Agent Prospection Kawanah Tourisme** est un outil de prospection automatisé pour le secteur de l'hospitalité (hôtels, campings, gîtes, résidences). Il permet d'identifier, enrichir et contacter des prospects pour leur proposer les services de création web de Kawanah Tourisme.

---

## Démarrage

### Lancer l'application

Ouvrir **deux terminaux** à chaque utilisation.

**Terminal 1 — Backend**
```bash
cd "/Users/martinlaetitia/Documents/CLAUDE TEST/Agent"
source venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 — Frontend**
```bash
cd "/Users/martinlaetitia/Documents/CLAUDE TEST/Agent/frontend"
npm run dev
```

Puis ouvrir **http://localhost:5173** dans le navigateur.

### Connexion

Utiliser l'identifiant admin configuré dans `.env` (`ADMIN_USERNAME` et `ADMIN_PASSWORD_HASH`).

Le token de session dure 24h. Passé ce délai, la page de connexion réapparaît automatiquement.

---

## Les 7 fonctionnalités

### 1. Import de Leads

**But :** Importer une liste d'établissements à prospecter.

**Formats acceptés :** CSV, Excel (.xlsx, .xls)

**Colonnes reconnues automatiquement :**
| Colonne | Obligatoire | Description |
|---------|-------------|-------------|
| `nom` ou `name` | Oui | Nom de l'établissement |
| `ville` ou `city` | Non | Ville |
| `email` | Non | Email de contact |
| `telephone` | Non | Numéro de téléphone |
| `site_web` ou `website` | Non | Site web existant |
| `code_postal` | Non | Code postal |

**Comment faire :**
1. Aller dans **Import** dans la navigation
2. Glisser-déposer ou cliquer pour uploader le fichier
3. Vérifier le résumé (leads importés, ignorés, doublons)
4. Les leads apparaissent immédiatement dans la section **Leads**

**Bon à savoir :** Les doublons (même nom + même ville) sont détectés automatiquement et ignorés.

---

### 2. Leads

**But :** Consulter, filtrer et gérer les prospects importés.

**Filtres disponibles :**
- Par statut (nouveau, enrichi, contacté, a répondu, converti, rejeté)
- Par type (hôtel, camping, gîte, résidence, activité)
- Par score minimum
- Par ville
- Par présence de site web

**Actions disponibles par lead :**
- Voir le détail complet
- Lancer l'enrichissement individuel (bouton Enrichir)
- Modifier le statut manuellement

**Export CSV :**
Le bouton **Exporter CSV** en haut de la liste télécharge tous les leads filtrés.

---

### 3. Enrichissement

**But :** Récupérer automatiquement des informations complémentaires sur chaque établissement.

**Données récupérées :**
- Note Google et nombre d'avis (via Google Places API)
- Analyse du site web existant (qualité, SEO)
- Emails de contact
- Réseaux sociaux

**Comment faire :**
1. Aller dans **Enrichissement**
2. Sélectionner un lead ou lancer un enrichissement en lot
3. Patienter — les données s'affichent en temps réel

**Prérequis :** La clé `GOOGLE_PLACES_API_KEY` doit être configurée dans `.env` ou dans **Paramètres**.

---

### 4. Scoring & Priorisation

**But :** Attribuer un score de 0 à 100 pour identifier les meilleurs prospects.

**Critères de scoring :**
| Critère | Impact |
|---------|--------|
| Pas de site web | +30 pts (opportunité création) |
| Site de mauvaise qualité | +20 pts (opportunité refonte) |
| Beaucoup d'avis Google | +15 pts (établissement actif) |
| Bonne note Google (>4.0) | +10 pts |
| Tendance avis croissante | +10 pts |
| Email disponible | +10 pts |

**Segments automatiques :**
| Segment | Score | Action recommandée |
|---------|-------|-------------------|
| SANS SITE | — | Priorité absolue |
| CHAUD | 80-100 | Contacter rapidement |
| TIEDE | 50-79 | File d'attente normale |
| FROID | < 50 | Relance future |
| À VÉRIFIER | — | Site inaccessible |

---

### 5. Campagnes

**But :** Organiser les actions de prospection par vague.

**Statuts :**
| Statut | Signification |
|--------|---------------|
| Brouillon | Créée, pas encore lancée |
| Active | En cours |
| En pause | Suspendue temporairement |
| Terminée | Terminée |

**Comment créer une campagne :**
1. Aller dans **Campagnes**
2. Cliquer **Nouvelle campagne** (bouton en haut à droite)
3. Nommer la campagne et choisir le canal (Email ou LinkedIn)
4. Avant de démarrer, un aperçu des leads éligibles s'affiche
5. Confirmer pour lancer

**Indicateurs affichés :** Emails envoyés / Ouverts / Réponses / Taux de réponse

---

### 6. Messages

**But :** Générer, personnaliser et envoyer des emails aux prospects.

**Génération IA :**
L'IA Claude génère des messages personnalisés selon :
- Le segment du lead (sans site, chaud, tiède…)
- Le canal choisi (email ou LinkedIn)
- Le ton demandé (professionnel, amical, direct)
- Les données d'enrichissement (note Google, présence web, etc.)

**Comment générer un message :**
1. Aller dans **Messages**
2. Choisir un lead et cliquer **Générer**
3. Sélectionner le ton et le canal
4. Modifier si nécessaire dans la zone de texte
5. Cliquer **Envoyer** ou **Email de test** (pour tester sur ta propre adresse)

**Email de test :** Envoie le message à une adresse de votre choix sans affecter le statut du lead. Limité à 5 par minute.

**Bonnes pratiques :**
- Ne pas dépasser 50 emails/jour (risque de spam)
- Envoyer entre 9h et 11h (meilleur taux d'ouverture)
- Toujours tester avant d'envoyer à un vrai prospect

---

### 7. Agent Autonome

**But :** Déléguer des tâches à l'agent IA qui les exécute en autonomie.

**Comment l'utiliser :**
1. Aller dans **Agent**
2. Taper une instruction en français, par exemple :
   - *"Trouve les 5 meilleurs leads sans site web"*
   - *"Génère un message professionnel pour le lead 42"*
   - *"Quels sont les leads les plus chauds cette semaine ?"*
3. L'agent répond et exécute les actions nécessaires

**Modes de fonctionnement :**
| Mode | Comportement |
|------|-------------|
| Autonome | Agit seul dans les limites configurées |
| Supervisé | Demande validation avant chaque action |
| Manuel | Suggère uniquement, n'exécute pas |

---

## Paramètres

Accessible via **Paramètres** dans la navigation.

**Ce que vous pouvez configurer :**
- Clés API (Claude, Google Places, Hunter.io)
- Configuration SMTP (email d'envoi)
- Email LinkedIn (optionnel)

**Test email :** Un bouton permet d'envoyer un email de test pour vérifier la configuration SMTP avant d'utiliser l'outil en production.

---

## Comprendre les statuts des leads

| Statut | Signification |
|--------|---------------|
| `new` | Importé, non traité |
| `enriched` | Données récupérées |
| `contacted` | Email envoyé |
| `replied` | Le prospect a répondu |
| `converted` | Devenu client |
| `rejected` | Refus ou désintérêt |

---

## FAQ

**Q: L'enrichissement ne trouve rien pour un lead ?**
R: Vérifiez que la clé Google Places est valide (section Paramètres). Certains petits établissements ne sont pas référencés sur Google Maps.

**Q: Mon email arrive en spam ?**
- Vérifiez que votre domaine a un enregistrement SPF et DKIM
- Limitez-vous à 30-50 emails/jour au démarrage (warm-up)
- Personnalisez chaque message — évitez les messages identiques en masse

**Q: Comment changer le mot de passe admin ?**
R: Dans un terminal (venv activé) :
```bash
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('nouveau-mdp'))"
```
Coller le résultat dans `ADMIN_PASSWORD_HASH` dans le fichier `.env`, puis redémarrer le backend.

**Q: Puis-je importer des données depuis data.gouv.fr ?**
R: Oui, via la section **Import** ou directement via l'API `/api/gouv`.

---

## Support

- Logs en temps réel : terminal backend (uvicorn)
- Documentation technique : `docs/DOCUMENTATION_TECHNIQUE.md`
- API interactive : http://localhost:8000/docs
