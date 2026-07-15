# Lancement du serveur

Guide rapide pour démarrer le projet en local.

## Backend (API FastAPI)

```bash
# Depuis la racine du projet
source venv/bin/activate        # active l'environnement Python
uvicorn app.main:app --reload   # démarre l'API (redémarre auto quand on modifie le code)
```

- API : http://127.0.0.1:8000
- Docs API : http://127.0.0.1:8000/docs

> Si `uvicorn: command not found`, lance directement : `venv/bin/uvicorn app.main:app --reload`

## Frontend (Dashboard React + Vite)

```bash
cd frontend
npm install    # une seule fois, pour installer les dépendances
npm run dev    # démarre le dashboard
```

- Dashboard : http://localhost:5173

## En cas de venv cassé

Si le projet a été déplacé de dossier, le venv garde d'anciens chemins et plante.
Le recréer :

```bash
rm -rf venv
python3.11 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```
