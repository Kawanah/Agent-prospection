# Agent de Prospection — Kawanah Tourisme

Outil de prospection B2B automatisé pour le secteur de l'hospitalité. Identifie, enrichit et contacte des prospects pour leur proposer des services de création web.

---

## Prérequis

- Python 3.11+
- Node.js 18+
- Un compte Anthropic (clé API Claude)

---

## Installation

```bash
# 1. Cloner le projet
cd "/Users/martinlaetitia/Documents/CLAUDE TEST/Agent"

# 2. Créer l'environnement Python
python -m venv venv
source venv/bin/activate

# 3. Installer les dépendances Python
pip install -r requirements.txt

# 4. Installer les dépendances frontend
cd frontend && npm install && cd ..

# 5. Configurer les variables d'environnement
# Éditer le fichier .env à la racine (déjà configuré)
```

---

## Lancer l'application

Deux terminaux sont nécessaires à chaque démarrage.

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

Identifiant admin : voir `ADMIN_USERNAME` et `ADMIN_PASSWORD_HASH` dans `.env`.

---

## Lancer les tests

```bash
source venv/bin/activate
pytest tests/ -v
```

---

## Variables d'environnement clés

| Variable | Description | Obligatoire |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | Clé API Claude | Oui |
| `GOOGLE_PLACES_API_KEY` | Clé API Google Places | Oui |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | Envoi email | Pour emails |
| `SECRET_KEY` | Clé JWT (32 hex chars) | Oui |
| `ADMIN_PASSWORD_HASH` | Hash bcrypt du mot de passe admin | Oui |
| `ALLOWED_ORIGINS` | Origines CORS autorisées en prod | Production |

Pour changer le mot de passe admin :
```bash
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('nouveau-mdp'))"
```
Puis coller le résultat dans `ADMIN_PASSWORD_HASH` dans `.env`.

---

## Documentation

- [Manuel Utilisateur](docs/MANUEL_UTILISATEUR.md) — comment utiliser le dashboard
- [Documentation Technique](docs/DOCUMENTATION_TECHNIQUE.md) — architecture, API, sécurité
- API interactive : http://localhost:8000/docs (backend démarré)
