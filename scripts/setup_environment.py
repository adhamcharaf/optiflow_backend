#!/usr/bin/env python3
"""
Script d'initialisation de l'environnement OptiFlow
Configure et teste les connexions Odoo et Supabase
"""

import os
import sys
import subprocess
from dotenv import load_dotenv
from pathlib import Path


def install_requirements():
    """Installe les dépendances Python"""
    print("📦 Installation des dépendances...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✅ Dépendances installées avec succès")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'installation des dépendances: {e}")
        return False
    
    return True


def check_env_file():
    """Vérifie l'existence du fichier .env"""
    env_path = Path(".env")
    env_example_path = Path(".env.example")
    
    if not env_path.exists():
        if env_example_path.exists():
            print("⚠️ Fichier .env manquant!")
            print(f"📋 Copiez {env_example_path} vers {env_path} et configurez vos variables")
            return False
        else:
            print("❌ Aucun fichier de configuration trouvé")
            return False
    
    print("✅ Fichier .env trouvé")
    return True


def test_odoo_connection():
    """Teste la connexion Odoo"""
    print("\n🔗 Test de connexion Odoo...")
    
    try:
        from scripts.test_connection import OdooConnector
        
        # Charger les variables d'environnement
        load_dotenv()
        
        config = {
            'host': os.getenv('ODOO_HOST', 'localhost'),
            'port': int(os.getenv('ODOO_PORT', 8069)),
            'db': os.getenv('ODOO_DB', 'odoo'),
            'username': os.getenv('ODOO_USERNAME', 'admin'),
            'password': os.getenv('ODOO_PASSWORD', 'admin')
        }
        
        connector = OdooConnector(**config)
        connector.connect()
        
        print("✅ Connexion Odoo réussie")
        return True
        
    except Exception as e:
        print(f"❌ Erreur connexion Odoo: {e}")
        return False


def test_supabase_connection():
    """Teste la connexion Supabase"""
    print("\n☁️ Test de connexion Supabase...")
    
    try:
        from supabase import create_client
        
        # Charger les variables d'environnement
        load_dotenv()
        
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        
        if not url or not key:
            print("❌ Variables SUPABASE_URL ou SUPABASE_KEY manquantes")
            return False
        
        supabase = create_client(url, key)
        
        # Test simple avec une requête
        response = supabase.table('products').select('count', count='exact').execute()
        
        print(f"✅ Connexion Supabase réussie")
        print(f"📊 {response.count} produits dans la base")
        return True
        
    except Exception as e:
        print(f"❌ Erreur connexion Supabase: {e}")
        return False


def run_data_generation():
    """Lance la génération de données"""
    print("\n🎯 Génération des données d'entraînement...")
    
    try:
        # Test de connexion d'abord
        print("1. Test des connexions...")
        subprocess.check_call([sys.executable, "scripts/test_connection.py"])
        
        # ETL Odoo vers Supabase
        print("\n2. Extraction des données Odoo...")
        subprocess.check_call([sys.executable, "scripts/etl_odoo_to_supabase.py"])
        
        # Génération des données d'entraînement
        print("\n3. Génération des données d'entraînement...")
        subprocess.check_call([sys.executable, "scripts/generate_supabase_data.py"])
        
        print("✅ Génération des données terminée avec succès!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de la génération: {e}")
        return False


def main():
    """Fonction principale"""
    print("🚀 Configuration de l'environnement OptiFlow")
    print("=" * 50)
    
    # Vérifications préliminaires
    if not check_env_file():
        print("\n❌ Configuration incomplète")
        return False
    
    # Installation des dépendances
    if not install_requirements():
        print("\n❌ Impossible d'installer les dépendances")
        return False
    
    # Tests de connexion
    odoo_ok = test_odoo_connection()
    supabase_ok = test_supabase_connection()
    
    if not (odoo_ok and supabase_ok):
        print("\n❌ Certaines connexions ont échoué")
        print("Vérifiez votre configuration dans .env")
        return False
    
    # Génération des données
    print("\n" + "=" * 50)
    generate = input("🎯 Lancer la génération des données d'entraînement? (y/N): ")
    
    if generate.lower() in ['y', 'yes', 'oui']:
        if run_data_generation():
            print("\n🎉 Environnement configuré avec succès!")
            print("💡 Vous pouvez maintenant utiliser OptiFlow")
        else:
            print("\n⚠️ Génération des données échouée")
    else:
        print("\n✅ Environnement prêt (sans données d'entraînement)")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 