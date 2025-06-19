"""
OptiFlow - Évaluation des performances des modèles
=================================================

Ce module mesure et analyse les performances des modèles Prophet :
- Métriques de précision (MAPE, RMSE, MAE)
- Comparaison entre produits
- Analyse de la qualité des prédictions
- Recommandations d'amélioration

Auteur : Équipe OptiFlow
Date : Décembre 2024
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import json

# Imports de nos modules
from utils import get_supabase_connection, load_sales_data, prepare_prophet_data
from train_models import OptiFlowPredictor

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptiFlowEvaluator:
    """
    Classe pour évaluer et analyser les performances des modèles OptiFlow.
    
    🎯 OBJECTIFS :
    - Mesurer la précision des prédictions
    - Identifier les produits les plus/moins fiables
    - Proposer des améliorations
    - Générer des rapports de performance
    """
    
    def __init__(self, predictor: OptiFlowPredictor = None):
        """
        Initialise l'évaluateur de performances.
        
        Args:
            predictor (OptiFlowPredictor, optional): Instance du prédicteur
        """
        self.predictor = predictor or OptiFlowPredictor()
        self.supabase = get_supabase_connection()
        self.evaluation_results = {}
        
        logger.info("📊 OptiFlowEvaluator initialisé")

    def evaluate_single_product(self, product_id: int, test_days: int = 14) -> Dict:
        """
        Évalue un modèle sur un produit avec validation temporelle.
        
        🎯 MÉTHODE D'ÉVALUATION :
        1. Divise les données : train (80%) vs test (20%)
        2. Entraîne sur les données train
        3. Prédit sur la période test
        4. Compare prédictions vs réalité
        5. Calcule métriques de performance
        
        Args:
            product_id (int): ID du produit à évaluer
            test_days (int): Nombre de jours pour le test
            
        Returns:
            dict: Métriques et analyse détaillée
        """
        try:
            logger.info(f"📊 Évaluation produit {product_id}")
            
            # ÉTAPE 1 : Charger toutes les données
            sales_data = load_sales_data(product_id)
            if sales_data.empty:
                return {
                    'success': False,
                    'error': 'Pas de données de vente',
                    'product_id': product_id
                }
            
            prophet_data = prepare_prophet_data(sales_data)
            if len(prophet_data) < 30:  # Minimum pour évaluation
                return {
                    'success': False,
                    'error': f'Données insuffisantes ({len(prophet_data)} jours)',
                    'product_id': product_id
                }
            
            # ÉTAPE 2 : Division train/test temporelle
            split_point = len(prophet_data) - test_days
            train_data = prophet_data[:split_point].copy()
            test_data = prophet_data[split_point:].copy()
            
            if len(train_data) < 20 or len(test_data) < 3:
                return {
                    'success': False,
                    'error': 'Division train/test impossible',
                    'product_id': product_id
                }
            
            # ÉTAPE 3 : Entraîner modèle sur données train
            from prophet import Prophet
            model = Prophet(**self.predictor.prophet_params)
            model.fit(train_data)
            
            # ÉTAPE 4 : Prédire sur période test
            future = model.make_future_dataframe(periods=test_days, freq='D')
            forecast = model.predict(future)
            
            # Extraire prédictions pour période test
            test_predictions = forecast.tail(len(test_data))
            
            # ÉTAPE 5 : Calculer métriques
            metrics = self._calculate_detailed_metrics(
                test_data['y'].values,
                test_predictions['yhat'].values,
                test_predictions.get('yhat_lower', test_predictions['yhat']).values,
                test_predictions.get('yhat_upper', test_predictions['yhat']).values
            )
            
            # ÉTAPE 6 : Analyse qualitative
            quality_analysis = self._analyze_prediction_quality(metrics, len(prophet_data))
            
            result = {
                'success': True,
                'product_id': product_id,
                'data_summary': {
                    'total_days': len(prophet_data),
                    'train_days': len(train_data),
                    'test_days': len(test_data),
                    'total_sales': prophet_data['y'].sum(),
                    'avg_daily_sales': prophet_data['y'].mean(),
                    'period': {
                        'start': prophet_data['ds'].min().strftime('%Y-%m-%d'),
                        'end': prophet_data['ds'].max().strftime('%Y-%m-%d')
                    }
                },
                'metrics': metrics,
                'quality_analysis': quality_analysis,
                'test_predictions': {
                    'actual': test_data['y'].tolist(),
                    'predicted': test_predictions['yhat'].tolist(),
                    'dates': test_data['ds'].dt.strftime('%Y-%m-%d').tolist()
                }
            }
            
            logger.info(f"✅ Évaluation terminée - MAPE: {metrics['mape']:.1f}%")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur évaluation produit {product_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'product_id': product_id
            }

    def _calculate_detailed_metrics(
        self, 
        y_true: np.array, 
        y_pred: np.array,
        y_lower: np.array,
        y_upper: np.array
    ) -> Dict:
        """
        Calcule des métriques détaillées de performance.
        
        Args:
            y_true (np.array): Valeurs réelles
            y_pred (np.array): Prédictions
            y_lower (np.array): Borne inférieure confiance
            y_upper (np.array): Borne supérieure confiance
            
        Returns:
            dict: Métriques complètes
        """
        # Éviter divisions par zéro
        y_true_safe = np.maximum(y_true, 0.1)
        
        # Métriques de base
        mae = np.mean(np.abs(y_true - y_pred))
        mse = np.mean((y_true - y_pred) ** 2)
        rmse = np.sqrt(mse)
        mape = np.mean(np.abs((y_true - y_pred) / y_true_safe)) * 100
        
        # Métriques avancées
        # Bias (tendance à sur/sous-estimer)
        bias = np.mean(y_pred - y_true)
        bias_percentage = (bias / np.mean(y_true_safe)) * 100
        
        # Précision directionnelle (prédictions dans la bonne direction)
        if len(y_true) > 1:
            true_direction = np.diff(y_true) > 0
            pred_direction = np.diff(y_pred) > 0
            direction_accuracy = np.mean(true_direction == pred_direction) * 100
        else:
            direction_accuracy = 0
        
        # Couverture des intervalles de confiance
        coverage = np.mean((y_true >= y_lower) & (y_true <= y_upper)) * 100
        
        # Largeur moyenne des intervalles
        interval_width = np.mean(y_upper - y_lower)
        
        return {
            'mae': round(mae, 3),
            'mse': round(mse, 3),
            'rmse': round(rmse, 3),
            'mape': round(mape, 2),
            'bias': round(bias, 3),
            'bias_percentage': round(bias_percentage, 2),
            'direction_accuracy': round(direction_accuracy, 2),
            'confidence_coverage': round(coverage, 2),
            'avg_interval_width': round(interval_width, 3),
            'r_squared': round(np.corrcoef(y_true, y_pred)[0, 1] ** 2, 3) if len(y_true) > 1 else 0
        }

    def _analyze_prediction_quality(self, metrics: Dict, data_points: int) -> Dict:
        """
        Analyse qualitative de la performance du modèle.
        
        Args:
            metrics (dict): Métriques calculées
            data_points (int): Nombre de points de données
            
        Returns:
            dict: Analyse qualitative
        """
        mape = metrics['mape']
        rmse = metrics['rmse']
        coverage = metrics['confidence_coverage']
        direction_acc = metrics['direction_accuracy']
        
        # Classification de la qualité selon MAPE
        if mape <= 20:
            quality_level = 'excellent'
            recommendation = 'Modèle très fiable, automatisation possible'
        elif mape <= 50:
            quality_level = 'good'
            recommendation = 'Modèle fiable, bon pour alertes et aide décision'
        elif mape <= 100:
            quality_level = 'acceptable'
            recommendation = 'Modèle acceptable, utile pour tendances générales'
        elif mape <= 200:
            quality_level = 'poor'
            recommendation = 'Modèle peu fiable, monitoring seulement'
        else:
            quality_level = 'very_poor'
            recommendation = 'Modèle non recommandé, plus de données nécessaires'
        
        # Analyse des points forts/faibles
        strengths = []
        weaknesses = []
        
        if direction_acc >= 70:
            strengths.append("Bonne prédiction des tendances")
        else:
            weaknesses.append("Difficulté à prédire la direction des ventes")
        
        if coverage >= 75:
            strengths.append("Intervalles de confiance fiables")
        else:
            weaknesses.append("Intervalles de confiance peu calibrés")
        
        if abs(metrics['bias_percentage']) <= 10:
            strengths.append("Prédictions non biaisées")
        elif metrics['bias_percentage'] > 10:
            weaknesses.append("Tendance à surestimer les ventes")
        else:
            weaknesses.append("Tendance à sous-estimer les ventes")
        
        if data_points >= 100:
            strengths.append("Dataset suffisant pour Prophet")
        else:
            weaknesses.append("Dataset limité, plus de données amélioreraient le modèle")
        
        return {
            'quality_level': quality_level,
            'recommendation': recommendation,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'confidence_score': min(100, max(0, 100 - mape)),  # Score 0-100
            'usability': {
                'automation': quality_level in ['excellent', 'good'],
                'alerts': quality_level in ['excellent', 'good', 'acceptable'],
                'monitoring': True  # Toujours utile pour monitoring
            }
        }

    def evaluate_all_products(self, max_products: int = None) -> Dict:
        """
        Évalue tous les produits et génère un rapport complet.
        
        Args:
            max_products (int, optional): Limite le nombre de produits à évaluer
            
        Returns:
            dict: Rapport complet d'évaluation
        """
        logger.info("🚀 Évaluation de tous les produits")
        
        products = self.predictor.get_product_list()
        if max_products:
            products = products[:max_products]
        
        results = {
            'evaluation_date': datetime.now().isoformat(),
            'total_products': len(products),
            'individual_results': [],
            'summary_statistics': {},
            'recommendations': {}
        }
        
        successful_evaluations = []
        
        for i, product in enumerate(products, 1):
            logger.info(f"\n📊 [{i}/{len(products)}] Évaluation {product['name']} (ID: {product['id']})")
            
            evaluation = self.evaluate_single_product(product['id'])
            evaluation['product_name'] = product['name']
            evaluation['sales_count'] = product['sales_count']
            
            results['individual_results'].append(evaluation)
            
            if evaluation['success']:
                successful_evaluations.append(evaluation)
        
        # Statistiques globales
        if successful_evaluations:
            results['summary_statistics'] = self._calculate_summary_statistics(successful_evaluations)
            results['recommendations'] = self._generate_global_recommendations(successful_evaluations)
        
        results['successful_evaluations'] = len(successful_evaluations)
        results['failed_evaluations'] = len(products) - len(successful_evaluations)
        
        logger.info(f"\n🎉 Évaluation terminée : {len(successful_evaluations)}/{len(products)} succès")
        
        return results

    def _calculate_summary_statistics(self, evaluations: List[Dict]) -> Dict:
        """Calcule les statistiques globales."""
        mapes = [e['metrics']['mape'] for e in evaluations]
        rmses = [e['metrics']['rmse'] for e in evaluations]
        data_points = [e['data_summary']['total_days'] for e in evaluations]
        
        return {
            'mape': {
                'mean': round(np.mean(mapes), 2),
                'median': round(np.median(mapes), 2),
                'min': round(min(mapes), 2),
                'max': round(max(mapes), 2),
                'std': round(np.std(mapes), 2)
            },
            'rmse': {
                'mean': round(np.mean(rmses), 2),
                'median': round(np.median(rmses), 2),
                'min': round(min(rmses), 2),
                'max': round(max(rmses), 2)
            },
            'data_quality': {
                'avg_data_points': round(np.mean(data_points), 1),
                'min_data_points': min(data_points),
                'max_data_points': max(data_points)
            }
        }

    def _generate_global_recommendations(self, evaluations: List[Dict]) -> Dict:
        """Génère des recommandations globales."""
        excellent = sum(1 for e in evaluations if e['quality_analysis']['quality_level'] == 'excellent')
        good = sum(1 for e in evaluations if e['quality_analysis']['quality_level'] == 'good')
        acceptable = sum(1 for e in evaluations if e['quality_analysis']['quality_level'] == 'acceptable')
        poor = sum(1 for e in evaluations if e['quality_analysis']['quality_level'] in ['poor', 'very_poor'])
        
        total = len(evaluations)
        
        return {
            'quality_distribution': {
                'excellent': f"{excellent}/{total} ({excellent/total*100:.1f}%)",
                'good': f"{good}/{total} ({good/total*100:.1f}%)",
                'acceptable': f"{acceptable}/{total} ({acceptable/total*100:.1f}%)",
                'poor': f"{poor}/{total} ({poor/total*100:.1f}%)"
            },
            'automation_ready': excellent + good,
            'alert_ready': excellent + good + acceptable,
            'monitoring_only': poor,
            'global_strategy': self._suggest_global_strategy(excellent, good, acceptable, poor, total)
        }

    def _suggest_global_strategy(self, excellent: int, good: int, acceptable: int, poor: int, total: int) -> str:
        """Suggère une stratégie globale basée sur la distribution de qualité."""
        automation_pct = (excellent + good) / total * 100
        
        if automation_pct >= 60:
            return "OptiFlow prêt pour déploiement avec automatisation sur produits principaux"
        elif automation_pct >= 30:
            return "OptiFlow viable avec focus sur alertes et aide à la décision"
        elif automation_pct >= 10:
            return "OptiFlow utile pour monitoring, amélioration données recommandée"
        else:
            return "Plus de données historiques nécessaires avant déploiement"

    def save_evaluation_report(self, results: Dict, filename: str = None) -> str:
        """
        Sauvegarde le rapport d'évaluation.
        
        Args:
            results (dict): Résultats d'évaluation
            filename (str, optional): Nom du fichier
            
        Returns:
            str: Chemin du fichier sauvegardé
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"optiflow_evaluation_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 Rapport sauvegardé : {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde : {e}")
            return None


def main():
    """
    Fonction principale pour tester l'évaluation.
    """
    print("📊 OptiFlow - Évaluation des performances")
    print("=" * 50)
    
    evaluator = OptiFlowEvaluator()
    
    # Test sur un produit
    print("\n🧪 TEST : Évaluation produit 6 (Armoire)")
    result = evaluator.evaluate_single_product(product_id=6)
    
    if result['success']:
        print(f"✅ MAPE: {result['metrics']['mape']}%")
        print(f"📊 Qualité: {result['quality_analysis']['quality_level']}")
        print(f"💡 Recommandation: {result['quality_analysis']['recommendation']}")
    else:
        print(f"❌ Erreur: {result['error']}")


if __name__ == "__main__":
    main()