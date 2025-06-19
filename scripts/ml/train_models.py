"""
OptiFlow - Entraînement des modèles Prophet
==========================================

Ce module crée et entraîne des modèles Prophet pour chaque produit.
Prophet va apprendre les patterns de vente et générer des prédictions.

Fonctionnalités :
- Entraînement d'un modèle par produit
- Détection automatique de saisonnalité 
- Validation des performances (MAPE, RMSE)
- Sauvegarde des modèles entraînés

Auteur : Équipe OptiFlow
Date : Décembre 2024
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import logging
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Imports de nos utilitaires
from utils import (
    get_supabase_connection, 
    load_sales_data, 
    prepare_prophet_data,
    load_stock_levels
)

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptiFlowPredictor:
    """
    Classe principale pour gérer les modèles Prophet d'OptiFlow.
    
    🎯 POURQUOI UNE CLASSE ?
    - Organiser le code de manière professionnelle
    - Stocker les paramètres de configuration
    - Faciliter la réutilisation et les tests
    - Préparer l'ajout de fonctionnalités avancées
    """
    
    def __init__(self, models_dir: str = "models"):
        """
        Initialise le prédicteur OptiFlow.
        
        Args:
            models_dir (str): Dossier où sauvegarder les modèles entraînés
        """
        self.models_dir = models_dir
        self.models = {}  # Stockage des modèles en mémoire
        self.model_metrics = {}  # Métriques de performance
        
        # Créer le dossier modèles s'il n'existe pas
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Configuration Prophet par défaut pour mobilier
        self.prophet_params = {
            'seasonality_mode': 'multiplicative',  # Saisonnalité multiplicative (+ réaliste pour ventes)
            'yearly_seasonality': True,            # Saisonnalité annuelle (Noël, rentrée, etc.)
            'weekly_seasonality': True,            # Saisonnalité hebdomadaire (weekend vs semaine)
            'daily_seasonality': False,            # Pas de saisonnalité quotidienne pour mobilier
            'interval_width': 0.80,               # Intervalle de confiance 80%
            'changepoint_prior_scale': 0.05       # Sensibilité aux changements de tendance
        }
        
        logger.info(f"🤖 OptiFlowPredictor initialisé")
        logger.info(f"📁 Dossier modèles : {self.models_dir}")

    def get_product_list(self) -> list:
        """
        Récupère la liste des produits avec des données de vente.
        
        Returns:
            list: Liste des dictionnaires {'id': int, 'name': str, 'sales_count': int}
        """
        try:
            supabase = get_supabase_connection()
            
            # Requête pour récupérer produits avec comptage des ventes
            query = """
            SELECT p.id, p.name, COUNT(sh.id) as sales_count
            FROM products p
            LEFT JOIN sales_history sh ON p.id = sh.product_id
            WHERE p.is_active = true
            GROUP BY p.id, p.name
            HAVING COUNT(sh.id) > 0
            ORDER BY sales_count DESC
            """
            
            response = supabase.table('products').select('*').execute()
            # Note: La requête complexe nécessiterait rpc(), simplifions
            
            products = []
            for product in response.data:
                if product['is_active']:
                    # Vérifier si le produit a des ventes
                    sales = load_sales_data(product_id=product['id'])
                    if not sales.empty:
                        products.append({
                            'id': product['id'],
                            'name': product['name'],
                            'sales_count': len(sales)
                        })
            
            logger.info(f"📦 {len(products)} produits avec données de vente trouvés")
            return products
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération produits : {e}")
            return []

    def train_product_model(self, product_id: int, product_name: str = None) -> dict:
        """
        Entraîne un modèle Prophet pour un produit spécifique.
        
        🎯 ÉTAPES D'ENTRAÎNEMENT :
        1. Charger les données de vente
        2. Préparer au format Prophet
        3. Créer et entraîner le modèle
        4. Calculer les métriques de validation
        5. Sauvegarder le modèle
        
        Args:
            product_id (int): ID du produit
            product_name (str, optional): Nom du produit (pour logging)
            
        Returns:
            dict: Résultats d'entraînement et métriques
        """
        try:
            logger.info(f"🎯 Entraînement modèle pour produit {product_id} ({product_name})")
            
            # ÉTAPE 1 : Charger les données
            sales_data = load_sales_data(product_id=product_id)
            
            if sales_data.empty:
                logger.warning(f"⚠️ Aucune donnée pour produit {product_id}")
                return {'success': False, 'error': 'Pas de données de vente'}
            
            # ÉTAPE 2 : Préparer pour Prophet
            prophet_data = prepare_prophet_data(sales_data)
            
            if len(prophet_data) < 10:  # Minimum requis pour Prophet
                logger.warning(f"⚠️ Pas assez de données ({len(prophet_data)} jours) pour produit {product_id}")
                return {'success': False, 'error': 'Données insuffisantes (< 10 jours)'}
            
            # ÉTAPE 3 : Créer et entraîner le modèle Prophet
            logger.info(f"🧠 Création modèle Prophet...")
            model = Prophet(**self.prophet_params)
            
            # Entraînement (ça peut prendre quelques secondes)
            logger.info(f"⏳ Entraînement en cours...")
            model.fit(prophet_data)
            
            # ÉTAPE 4 : Validation croisée (optionnel mais recommandé)
            metrics = self._validate_model(model, prophet_data)
            
            # ÉTAPE 5 : Sauvegarde
            model_path = os.path.join(self.models_dir, f"model_product_{product_id}.pkl")
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            # Stocker en mémoire aussi
            self.models[product_id] = model
            self.model_metrics[product_id] = metrics
            
            logger.info(f"✅ Modèle entraîné et sauvé : {model_path}")
            logger.info(f"📊 MAPE: {metrics['mape']:.1f}% | RMSE: {metrics['rmse']:.2f}")
            
            return {
                'success': True,
                'product_id': product_id,
                'data_points': len(prophet_data),
                'model_path': model_path,
                'metrics': metrics,
                'training_period': {
                    'start': prophet_data['ds'].min().strftime('%Y-%m-%d'),
                    'end': prophet_data['ds'].max().strftime('%Y-%m-%d')
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur entraînement produit {product_id} : {e}")
            return {'success': False, 'error': str(e)}

    def _validate_model(self, model: Prophet, data: pd.DataFrame) -> dict:
        """
        Valide la performance du modèle avec validation croisée.
        
        🎯 MÉTHODE DE VALIDATION :
        - Utilise 80% des données pour entraîner
        - Teste sur les 20% les plus récents
        - Calcule MAPE et RMSE pour mesurer la précision
        
        Args:
            model (Prophet): Modèle Prophet entraîné
            data (pd.DataFrame): Données d'entraînement
            
        Returns:
            dict: Métriques de validation
        """
        try:
            # Division train/test adaptée aux petits datasets
            if len(data) < 15:  # Très petit dataset
                split_point = max(len(data) - 5, int(len(data) * 0.7))
            else:
                split_point = int(len(data) * 0.8)
            
            train_data = data[:split_point].copy()
            test_data = data[split_point:].copy()
            
            if len(test_data) < 2:  # Minimum absolu
                return {'mape': 0, 'rmse': 0, 'validation': 'insufficient_test_data'}
            
            # Ré-entraîner sur train_data seulement
            temp_model = Prophet(**self.prophet_params)
            temp_model.fit(train_data)
            
            # Prédire sur la période de test
            future = temp_model.make_future_dataframe(periods=len(test_data), freq='D')
            forecast = temp_model.predict(future)
            
            # Comparer prédictions vs réalité
            test_predictions = forecast.tail(len(test_data))['yhat'].values
            test_actual = test_data['y'].values
            
            # Calcul des métriques avec protection contre les divisions par zéro
            # MAPE avec protection pour les valeurs très petites
            epsilon = 0.1  # Évite division par zéro
            mape = np.mean(np.abs((test_actual - test_predictions) / np.maximum(test_actual, epsilon))) * 100
            rmse = np.sqrt(mean_squared_error(test_actual, test_predictions))
            
            # Limiter MAPE à 999% pour éviter des valeurs aberrantes
            mape = min(mape, 999)
            
            return {
                'mape': round(mape, 2),
                'rmse': round(rmse, 2),
                'validation': 'success',
                'test_points': len(test_data),
                'note': 'high_mape' if mape > 50 else 'acceptable'
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur validation : {e}")
            return {'mape': 0, 'rmse': 0, 'validation': 'error'}

    def train_all_products(self) -> dict:
        """
        Entraîne des modèles pour tous les produits avec données.
        
        Returns:
            dict: Résumé de l'entraînement de tous les produits
        """
        logger.info("🚀 Début entraînement de tous les produits")
        
        products = self.get_product_list()
        results = {
            'total_products': len(products),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for product in products:
            logger.info(f"\n{'='*50}")
            result = self.train_product_model(
                product_id=product['id'], 
                product_name=product['name']
            )
            
            if result['success']:
                results['successful'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append(result)
        
        logger.info(f"\n🎉 RÉSUMÉ ENTRAÎNEMENT")
        logger.info(f"✅ Succès : {results['successful']}")
        logger.info(f"❌ Échecs : {results['failed']}")
        
        return results

    def load_model(self, product_id: int):
        """
        Charge un modèle sauvegardé depuis le disque.
        
        Args:
            product_id (int): ID du produit
            
        Returns:
            Prophet: Modèle chargé ou None si erreur
        """
        try:
            model_path = os.path.join(self.models_dir, f"model_product_{product_id}.pkl")
            
            if not os.path.exists(model_path):
                logger.error(f"❌ Modèle introuvable : {model_path}")
                return None
            
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            
            self.models[product_id] = model
            logger.info(f"✅ Modèle chargé : produit {product_id}")
            return model
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement modèle {product_id} : {e}")
            return None


def main():
    """
    Fonction principale pour tester l'entraînement.
    """
    print("🚀 OptiFlow - Entraînement des modèles Prophet")
    print("=" * 60)
    
    # Créer le prédicteur
    predictor = OptiFlowPredictor()
    
    # Option 1 : Entraîner un seul produit (pour test)
    print("\n🧪 TEST : Entraînement d'un produit")
    products = predictor.get_product_list()
    
    if products:
        first_product = products[0]
        result = predictor.train_product_model(
            product_id=first_product['id'],
            product_name=first_product['name']
        )
        print(f"Résultat : {result}")
    
    # Option 2 : Entraîner tous les produits (décommentez si souhaité)
    # print("\n🎯 PRODUCTION : Entraînement de tous les produits")
    # all_results = predictor.train_all_products()
    

if __name__ == "__main__":
    main()