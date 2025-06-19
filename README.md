# OptiFlow Extension

Extension d'optimisation de flux pour Odoo avec intelligence artificielle et analyse prédictive.

## 🚀 Fonctionnalités

- **Connexion Odoo** : Extraction automatique des données ERP
- **Base de données Supabase** : Stockage et analyse des données
- **Génération de données d'entraînement** : Création de datasets réalistes
- **Scripts ETL** : Transfer automatisé Odoo → Supabase

## 📋 Pré-requis

- Python 3.8+
- Odoo CE/EE (avec accès RPC)
- Compte Supabase
- Git

## 🛠️ Installation

### 1. Cloner le repo
```bash
git clone https://github.com/adhamcharaf/optiflow_extension.git
cd optiflow_extension
```

### 2. Créer l'environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Configuration
```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer avec vos vraies données
nano .env
```

Configurer les variables dans `.env` :
```bash
# Configuration Odoo
ODOO_HOST=localhost
ODOO_PORT=8069
ODOO_DB=your_odoo_database_name
ODOO_USERNAME=your_odoo_username
ODOO_PASSWORD=your_odoo_password

# Configuration Supabase
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_supabase_service_role_key_here
```

### 4. Initialisation automatique
```bash
python scripts/setup_environment.py
```

Ce script va :
- ✅ Installer les dépendances
- ✅ Tester les connexions Odoo/Supabase
- ✅ Proposer la génération des données d'entraînement

## 📊 Scripts disponibles

### Test de connexion
```bash
python scripts/test_connection.py
```
Vérifie la connectivité Odoo et affiche les données disponibles.

### ETL Odoo → Supabase
```bash
python scripts/etl_odoo_to_supabase.py
```
Extrait les données d'Odoo et les charge dans Supabase.

### Génération de données d'entraînement
```bash
python scripts/generate_supabase_data.py
```
Crée 11 mois de données réalistes pour l'entraînement IA.

### Génération de données de test
```bash
python scripts/generate_test_data.py
```
Génère des données de test pour validation.

## 🗂️ Structure du projet

```
optiflow_extension/
├── models/                      
├── scripts/
|   ├── ml/                      # Script de machin learning
│   ├── setup_environment.py     # Script d'initialisation
│   ├── test_connection.py       # Test connexions
│   ├── etl_odoo_to_supabase.py  # ETL principal
│   ├── generate_supabase_data.py # Génération données
│   └── generate_test_data.py    # Données de test
├── supabase/                    # Configuration Supabase
├── odoo-addons/                 # Modules Odoo custom
├── .env.example                 # Template configuration
├── .gitignore                   # Fichiers à ignorer
├── requirements.txt             # Dépendances Python
└── README.md                    # Documentation
```

## 🔧 Configuration Supabase

### Tables requises
- `products` : Produits Odoo
- `sales_data` : Historique des ventes
- `stock_data` : Données de stock
- `customers` : Clients/Partenaires

### Permissions
Assurez-vous que votre clé Supabase a les permissions :
- `SELECT`, `INSERT`, `UPDATE`, `DELETE` sur toutes les tables
- Accès à l'API REST

## 🚦 Utilisation

### 1. Configuration initiale
```bash
python scripts/setup_environment.py
```

### 2. Extraction des données Odoo
```bash
python scripts/etl_odoo_to_supabase.py
```

### 3. Génération des données d'entraînement
```bash
python scripts/generate_supabase_data.py
```

## 🛡️ Sécurité

- ❌ Le fichier `.env` est exclu du repo (.gitignore)
- ✅ Utilisez `.env.example` comme template
- ✅ Utilisez des clés Supabase avec permissions minimales
- ✅ Vérifiez les accès Odoo (utilisateur dédié recommandé)

## 📈 Données générées

Le script de génération crée :
- **11 mois** de données historiques (Jan-Nov 2024)
- **Saisonnalité réaliste** (pic septembre, creux été)
- **Variations par jour** de la semaine
- **Profils produits** adaptés (rotation, stock, prix)
- **Cohérence** entre ventes et mouvements de stock

## 🔍 Dépannage

### Erreur de connexion Odoo
```bash
# Vérifier la configuration
python scripts/test_connection.py

# Erreurs courantes :
# - Port incorrect (8069 par défaut)
# - Base de données inexistante
# - Identifiants invalides
```

### Erreur Supabase
```bash
# Vérifier les clés
python -c "from supabase import create_client; print('OK')"

# Erreurs courantes :
# - URL projet incorrecte
# - Clé service_role manquante
# - Permissions insuffisantes
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing-feature`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Pull Request

## 📄 License

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙋‍♂️ Support

Pour toute question ou problème :
- Ouvrir une issue sur GitHub
- Vérifier la documentation Odoo/Supabase
- Consulter les logs des scripts

---

**OptiFlow Extension** - Optimisation intelligente de vos flux Odoo 🚀
