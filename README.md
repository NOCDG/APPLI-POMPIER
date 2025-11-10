<<<<<<< HEAD
# APPLI-POMPIER
=======
# 🚒 FEUILLE_DE_GARDE

Application web de gestion des **feuilles de garde** pour une caserne de sapeurs-pompiers.  
Le projet permet de gérer le **personnel**, les **compétences**, les **équipes**, les **piquets**, et les **plannings mensuels de garde**, avec stockage en base de données et export des statistiques.

---

## 🧱 Architecture du projet

L’application est divisée en deux parties principales :

| Composant | Description | Technologies |
|------------|--------------|---------------|
| **Frontend** | Interface utilisateur pour la gestion des gardes et du calendrier | React + TailwindCSS + @dnd-kit (drag & drop) |
| **Backend** | API REST pour la gestion des données et la logique métier | FastAPI (Python) |
| **Base de données** | Stockage des données persistantes | PostgreSQL |
| **Déploiement** | Serveur Debian, CI/CD GitHub Actions | Nginx + systemd + GitHub Actions |

---

## 📂 Structure du projet

FEUILLE_DE_GARDE/
│
├── BACKEND/
│ ├── main.py # Point d'entrée FastAPI
│ ├── models/ # Modèles SQLAlchemy / Tortoise ORM
│ ├── routers/ # Routes (personnel, compétences, équipes, plannings)
│ ├── schemas/ # Schémas Pydantic
│ ├── database.py # Connexion PostgreSQL
│ ├── alembic/ # Migrations de base de données
│ └── requirements.txt # Dépendances Python
│
├── FRONTEND/
│ ├── src/
│ │ ├── components/ # Composants React (tableaux, calendrier, drag & drop)
│ │ ├── pages/ # Pages (Personnel, Compétences, Équipes, Calendrier)
│ │ ├── services/ # Appels API
│ │ ├── context/ # Contexte global (auth, thème, etc.)
│ │ └── App.jsx # Composant principal
│ ├── package.json
│ └── vite.config.js
│
├── .github/workflows/
│ └── ci-cd.yml # Pipeline GitHub Actions
│
├── docker-compose.yml # Optionnel : conteneurisation
├── README.md
└── .env.example # Variables d’environnement


---

## ⚙️ Installation et configuration

### 1️⃣ Prérequis

- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL**
- **Git**
- (Optionnel) Docker + Docker Compose

---

### 2️⃣ Cloner le dépôt

```bash
git clone https://github.com/<ton-utilisateur>/FEUILLE_DE_GARDE.git
cd FEUILLE_DE_GARDE
3️⃣ Configuration de la base de données

Créer la base PostgreSQL :

sudo -u postgres psql
CREATE DATABASE feuille_garde;
CREATE USER feuille_user WITH PASSWORD 'motdepasse';
GRANT ALL PRIVILEGES ON DATABASE feuille_garde TO feuille_user;


Puis configure ton fichier .env :

# .env
DATABASE_URL=postgresql://feuille_user:motdepasse@localhost/feuille_garde

4️⃣ Installation du backend (FastAPI)
cd BACKEND
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt

# Initialiser la base de données
alembic upgrade head

# Lancer le serveur
uvicorn main:app --reload


Accès API : http://localhost:8000/docs

5️⃣ Installation du frontend (React)
cd ../FRONTEND
npm install
npm run dev


Accès UI : http://localhost:5173

📅 Fonctionnalités principales
🔹 Gestion du personnel

Création, modification, suppression d’agents

Suivi des statuts : professionnel, volontaire, mixte

Compétences associées à chaque agent (SOG, INC2, CAUE, PL, etc.)

Affectation à une équipe (A, B, C, D)

🔹 Gestion des compétences

Liste centralisée des compétences

Date d’obtention et date limite de validité

Association à des piquets spécifiques

🔹 Gestion des équipes

Vue globale par équipe

Liste des membres avec leur statut et compétences

Affectation aux gardes via calendrier

🔹 Planning des gardes

Calendrier mensuel avec affichage jour/nuit

Samedi et dimanche = jour + nuit

En semaine = nuit uniquement

Système de drag & drop pour assigner les agents

Règles automatiques :

Pas de séquence jour + nuit + jour

Pas de séquence nuit + jour + nuit

Sauvegarde automatique en base de données

🔹 Statistiques

Taux de participation par agent et par équipe

Répartition des gardes par compétence

Export des rapports mensuels

🧪 CI/CD avec GitHub Actions

Pipeline automatisé dans .github/workflows/ci-cd.yml :

✅ Tests du backend (pytest)

✅ Build du frontend

✅ Déploiement automatique sur serveur Debian (via SSH)

✅ Redémarrage du service systemd

🚀 Déploiement (Linux/Debian)

Configurer Nginx comme reverse proxy :

server {
    server_name feuilledegarde.macasernex.fr;

    location /api {
        proxy_pass http://127.0.0.1:8000;
    }

    location / {
        root /var/www/feuilledegarde/frontend/dist;
        index index.html;
    }
}


Créer un service systemd :

sudo nano /etc/systemd/system/feuille_garde.service

[Unit]
Description=Feuille de Garde API
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/feuilledegarde/BACKEND
ExecStart=/var/www/feuilledegarde/BACKEND/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target


Activer et lancer :

sudo systemctl daemon-reload
sudo systemctl enable feuille_garde
sudo systemctl start feuille_garde
>>>>>>> 218ff39 (version 1.0)
