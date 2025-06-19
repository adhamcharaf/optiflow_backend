"""
OptiFlow - Génération des prédictions et calculs métier
======================================================

Ce module utilise les modèles Prophet entraînés pour :
- Générer des prédictions 30 jours
- Calculer les dates de rupture
- Recommander les quantités de commande
- Sauvegarder dans Supabase

Auteur : Équipe OptiFlow
Date : Décembre 2024
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional

# Imports de nos modules
from utils import (
    get_supabase_connection,
    load_stock_levels,
    calculate_days_until_stockout,
    calculate_reorder_quantity
)
from train_models import OptiFlowPredictor

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptiFlowForecast:
    """
    Classe pour générer et gérer les prédictions OptiFlow.
    
    🎯 RESPONSABILITÉS :
    - Charger les modèles entraînés
    - Générer prédictions 30 jours
    - Calculer métriques business (rupture, commande)
    - Sauvegarder dans Supabase
    """
    
    def __init__(self, predictor: OptiFlowPredictor = None):
        """
        Initialise le générateur de prévisions.
        
        Args:
            predictor (OptiFlowPredictor, optional): Instance du prédicteur
        """
        self.predictor = predictor or OptiFlowPredictor()
        self.supabase = get_supabase_connection()
        
        # Configuration business par défaut
        self.default_params = {
            'forecast_days': 30,
            'lead_time_days': 7,      # Délai fournisseur standard
            'safety_stock_days': 5,   # Stock sécurité standard
            'minimum_order_qty': 1    # MOQ par défaut
        }
        
        logger.info("🔮 OptiFlowForecast initialisé")

    def generate_product_forecast(
        self, 
        product_id: int, 
        forecast_days: int = None,
        save_to_db: bool = True
    ) -> Dict:
        """
        Génère une prévision complète pour un produit.
        
        🎯 PIPELINE COMPLET :
        1. Charger le modèle Prophet
        2. Générer prédictions 30 jours
        3. Récupérer stock actuel
        4. Calculer date rupture
        5. Recommander quantité commande
        6. Sauvegarder en base
        
        Args:
            product_id (int): ID du produit
            forecast_days (int): Nombre de jours à prédire
            save_to_db (bool): Sauvegarder en base ?
            
        Returns:
            dict: Prédiction complète avec alertes
        """
        try:
            forecast_days = forecast_days or self.default_params['forecast_days']
            logger.info(f"🎯 Génération prévision produit {product_id} ({forecast_days} jours)")
            
            # ÉTAPE 1 : Charger le modèle
            model = self.predictor.load_model(product_id)
            if model is None:
                return {
                    'success': False,
                    'error': f'Modèle non trouvé pour produit {product_id}'
                }
            
            # ÉTAPE 2 : Générer les prédictions
            future_dates = model.make_future_dataframe(periods=forecast_days, freq='D')
            forecast = model.predict(future_dates)
            
            # Prendre seulement les prédictions futures (pas l'historique)
            future_forecast = forecast.tail(forecast_days).copy()
            future_forecast = future_forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
            
            # Nettoyer les prédictions négatives
            future_forecast['yhat'] = future_forecast['yhat'].clip(lower=0)
            future_forecast['yhat_lower'] = future_forecast['yhat_lower'].clip(lower=0)
            future_forecast['yhat_upper'] = future_forecast['yhat_upper'].clip(lower=0)
            
            # ÉTAPE 3 : Stock actuel
            stock_data = load_stock_levels(product_id, latest_only=True)
            current_stock = 0
            if not stock_data.empty:
                current_stock = float(stock_data['quantity_available'].iloc[0])
            
            logger.info(f"📦 Stock actuel : {current_stock} unités")
            
            # ÉTAPE 4 : Calcul date de rupture
            stockout_info = calculate_days_until_stockout(current_stock, future_forecast)
            
            # ÉTAPE 5 : Recommandation commande
            reorder_info = calculate_reorder_quantity(
                future_forecast,
                lead_time_days=self.default_params['lead_time_days'],
                safety_stock_days=self.default_params['safety_stock_days'],
                minimum_order_qty=self.default_params['minimum_order_qty']
            )
            
            # ÉTAPE 6 : Compilation des résultats
            result = {
                'success': True,
                'product_id': product_id,
                'generated_at': datetime.now().isoformat(),
                'forecast_period': {
                    'start_date': future_forecast['ds'].min().strftime('%Y-%m-%d'),
                    'end_date': future_forecast['ds'].max().strftime('%Y-%m-%d'),
                    'days': forecast_days
                },
                'current_stock': current_stock,
                'predictions': {
                    'total_demand_30d': round(future_forecast['yhat'].sum(), 2),
                    'avg_daily_demand': round(future_forecast['yhat'].mean(), 2),
                    'peak_demand_day': future_forecast.loc[future_forecast['yhat'].idxmax(), 'ds'].strftime('%Y-%m-%d'),
                    'peak_demand_value': round(future_forecast['yhat'].max(), 2)
                },
                'stockout_analysis': stockout_info,
                'reorder_recommendation': reorder_info,
                'alert_level': self._calculate_alert_level(stockout_info, current_stock),
                'forecast_data': future_forecast.to_dict('records')  # Données complètes
            }
            
            # ÉTAPE 7 : Sauvegarde en base
            if save_to_db:
                self._save_forecast_to_db(result)
            
            logger.info(f"✅ Prévision générée")
            logger.info(f"📊 Demande 30j : {result['predictions']['total_demand_30d']} unités")
            logger.info(f"⚠️ Rupture : {stockout_info['days_until_stockout']} jours")
            logger.info(f"📦 Recommandation : {reorder_info['recommended_quantity']} unités")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur génération prévision {product_id} : {e}")
            return {'success': False, 'error': str(e)}

    def _calculate_alert_level(self, stockout_info: Dict, current_stock: float) -> str:
        """
        Détermine le niveau d'alerte basé sur les prédictions.
        
        🎯 LOGIQUE D'ALERTE :
        - CRITICAL : Rupture dans < 7 jours
        - HIGH : Rupture dans 7-14 jours  
        - MEDIUM : Rupture dans 15-30 jours
        - LOW : Pas de rupture prévue
        
        Args:
            stockout_info (dict): Informations de rupture
            current_stock (float): Stock actuel
            
        Returns:
            str: Niveau d'alerte
        """
        if current_stock <= 0:
            return 'CRITICAL'
        
        days_until_stockout = stockout_info.get('days_until_stockout', 999)
        
        if days_until_stockout <= 7:
            return 'CRITICAL'
        elif days_until_stockout <= 14:
            return 'HIGH'
        elif days_until_stockout <= 30:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _save_forecast_to_db(self, forecast_result: Dict) -> bool:
        """
        Sauvegarde la prévision dans Supabase.
        
        Args:
            forecast_result (dict): Résultats de prévision
            
        Returns:
            bool: Succès de la sauvegarde
        """
        try:
            # Préparer les données pour la table forecasts
            forecast_records = []
            
            for prediction in forecast_result['forecast_data']:
                record = {
                    'product_id': forecast_result['product_id'],
                    'forecast_date': prediction['ds'].strftime('%Y-%m-%d') if hasattr(prediction['ds'], 'strftime') else str(prediction['ds']),
                    'predicted_demand': float(prediction['yhat']),
                    'confidence_level': 0.8,  # Par défaut Prophet 80%
                    'rupture_risk': self._calculate_rupture_risk(
                        forecast_result['stockout_analysis']['days_until_stockout']
                    ),
                    'recommended_order_qty': forecast_result['reorder_recommendation']['recommended_quantity'],
                    'model_version': 'prophet_v1.0'
                }
                forecast_records.append(record)
            
            # Supprimer les anciennes prédictions pour ce produit
            self.supabase.table('forecasts').delete().eq(
                'product_id', forecast_result['product_id']
            ).execute()
            
            # Insérer les nouvelles prédictions
            self.supabase.table('forecasts').insert(forecast_records).execute()
            
            # Créer une alerte si nécessaire
            if forecast_result['alert_level'] in ['CRITICAL', 'HIGH']:
                self._create_alert(forecast_result)
            
            logger.info(f"💾 Prévisions sauvegardées : {len(forecast_records)} enregistrements")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde : {e}")
            return False

    def _calculate_rupture_risk(self, days_until_stockout: int) -> float:
        """
        Calcule un score de risque de rupture (0-100%).
        
        Args:
            days_until_stockout (int): Jours avant rupture
            
        Returns:
            float: Score de risque (0-100)
        """
        if days_until_stockout <= 0:
            return 100.0
        elif days_until_stockout <= 7:
            return 90.0
        elif days_until_stockout <= 14:
            return 70.0
        elif days_until_stockout <= 30:
            return 40.0
        else:
            return 10.0

    def _create_alert(self, forecast_result: Dict) -> bool:
        """
        Crée une alerte en base si risque élevé.
        
        Args:
            forecast_result (dict): Résultats de prévision
            
        Returns:
            bool: Succès création alerte
        """
        try:
            stockout_days = forecast_result['stockout_analysis']['days_until_stockout']
            alert_type = 'rupture_imminente' if stockout_days <= 7 else 'rupture_prevue'
            
            alert_data = {
                'product_id': forecast_result['product_id'],
                'alert_type': alert_type,
                'severity': forecast_result['alert_level'],
                'message': f"Rupture prévue dans {stockout_days} jours",
                'recommended_action': f"Commander {forecast_result['reorder_recommendation']['recommended_quantity']} unités",
                'is_resolved': False
            }
            
            # Vérifier si une alerte similaire existe déjà
            existing = self.supabase.table('alerts').select('id').eq(
                'product_id', forecast_result['product_id']
            ).eq('is_resolved', False).execute()
            
            if not existing.data:  # Pas d'alerte existante
                self.supabase.table('alerts').insert(alert_data).execute()
                logger.info(f"🚨 Alerte créée : {alert_type} pour produit {forecast_result['product_id']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur création alerte : {e}")
            return False

    def generate_all_forecasts(self) -> Dict:
        """
        Génère des prévisions pour tous les produits.
        
        Returns:
            dict: Résumé des prévisions générées
        """
        logger.info("🚀 Génération prévisions pour tous les produits")
        
        products = self.predictor.get_product_list()
        results = {
            'total_products': len(products),
            'successful': 0,
            'failed': 0,
            'alerts_created': 0,
            'details': []
        }
        
        for product in products:
            logger.info(f"\n{'='*40}")
            forecast_result = self.generate_product_forecast(
                product_id=product['id'],
                save_to_db=True
            )
            
            if forecast_result['success']:
                results['successful'] += 1
                if forecast_result.get('alert_level') in ['CRITICAL', 'HIGH']:
                    results['alerts_created'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'product_id': product['id'],
                'product_name': product['name'],
                'success': forecast_result['success'],
                'alert_level': forecast_result.get('alert_level', 'UNKNOWN')
            })
        
        logger.info(f"\n🎉 RÉSUMÉ PRÉVISIONS")
        logger.info(f"✅ Succès : {results['successful']}")
        logger.info(f"❌ Échecs : {results['failed']}")
        logger.info(f"🚨 Alertes : {results['alerts_created']}")
        
        return results


def main():
    """
    Fonction principale pour tester les prédictions.
    """
    print("🔮 OptiFlow - Génération des prédictions")
    print("=" * 50)
    
    # Créer le générateur de prévisions
    forecaster = OptiFlowForecast()
    
    # Test sur un produit
    predictor = OptiFlowPredictor()
    products = predictor.get_product_list()
    
    if products:
        # Prendre le produit avec le plus de données
        best_product = max(products, key=lambda x: x['sales_count'])
        
        print(f"\n🧪 TEST : Prévision pour {best_product['name']} (ID: {best_product['id']})")
        result = forecaster.generate_product_forecast(
            product_id=best_product['id'],
            save_to_db=False  # Test sans sauvegarde
        )
        
        if result['success']:
            print(f"✅ Prévision générée !")
            print(f"📊 Demande 30j : {result['predictions']['total_demand_30d']} unités")
            print(f"⚠️ Rupture dans : {result['stockout_analysis']['days_until_stockout']} jours")
            print(f"📦 Recommandation : {result['reorder_recommendation']['recommended_quantity']} unités")
            print(f"🚨 Niveau alerte : {result['alert_level']}")
        else:
            print(f"❌ Erreur : {result.get('error')}")


if __name__ == "__main__":
    main()