"""
OptiFlow - Moteur d'agrégation pour l'interface Web
==================================================

Ce module expose une couche métier *unifiée* pour OptiFlow. Il encapsule les
fonctionnalités de prédiction, d'évaluation et de récupération de données afin
que l'interface web puisse interagir avec une **seule** classe : `OptiFlowEngine`.

Fonctionnalités clefs :
1. get_dashboard_data()      – Vue d'ensemble pour le tableau de bord
2. get_product_detail(id)    – Analyse complète d'un produit
3. get_active_alerts()       – Centre d'alertes
4. get_performance_summary() – Suivi global des performances

Contraintes :
- Aucune modification des tables Supabase
- Utilise les classes existantes (Predictor, Forecast, Evaluator)
- Gestion d'erreur robuste + logs détaillés
- Valeurs retournées sous forme de dictionnaires 100 % JSON-serialisables

Auteur : Équipe OptiFlow
Date : Juillet 2025
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Any

# Modules internes OptiFlow
from utils import get_supabase_connection, load_stock_levels
from train_models import OptiFlowPredictor
from predict import OptiFlowForecast
from evaluate import OptiFlowEvaluator

# ---------------------------------------------------------------------------
# Configuration logging (hérite du root si déjà défini)
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class OptiFlowEngine:
    """Couche d'orchestration unique pour l'interface web OptiFlow."""

    # Ordre de sévérité pour le tri des alertes
    _SEVERITY_ORDER = {
        "CRITICAL": 1,
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4,
        "UNKNOWN": 5,
    }

    # Cache en mémoire pour éviter des recalculs coûteux
    _cache: Dict[str, Any] = {}
    _CACHE_TTL_SECONDS = 60 * 10  # 10 minutes

    # ---------------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------------
    def __init__(self) -> None:
        self.supabase = get_supabase_connection()
        self.predictor = OptiFlowPredictor()
        self.forecaster = OptiFlowForecast(self.predictor)
        self.evaluator = OptiFlowEvaluator(self.predictor)
        logger.info("🧩 OptiFlowEngine initialisé – prêt à servir l'interface web")

    # ---------------------------------------------------------------------
    # API publique
    # ---------------------------------------------------------------------
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Retourne les informations nécessaires au tableau de bord principal."""
        try:
            # Comptage produits actifs
            products_resp = self.supabase.table("products").select("id, is_active").execute()
            total_products = len([p for p in (products_resp.data or []) if p.get("is_active")])

            # Comptage modèles entraînés (présents sur disque ou mémoire)
            trained_products = self.predictor.get_product_list()
            models_trained = len(trained_products)

            # Nombre total de prédictions en base (row count dans forecasts)
            forecasts_resp = self.supabase.table("forecasts").select("id").execute()
            total_predictions = len(forecasts_resp.data or [])

            # Récupération des alertes actives
            alerts_resp = self.supabase.table("alerts").select("*") \
                .eq("is_resolved", False).execute()
            active_alerts: List[Dict[str, Any]] = alerts_resp.data or []

            # Agrégation du nombre d'alertes par sévérité
            alert_severity_counts: Dict[str, int] = {}
            for a in active_alerts:
                severity = a.get("severity", "UNKNOWN")
                alert_severity_counts[severity] = alert_severity_counts.get(severity, 0) + 1

            # Top 5 risques = alertes triées par sévérité + date de rupture si dispo
            sorted_alerts = sorted(
                active_alerts,
                key=lambda x: (
                    self._SEVERITY_ORDER.get(x.get("severity", "UNKNOWN"), 5),
                    x.get("created_at", ""),
                ),
            )
            top_risks = [
                {
                    "product_id": a.get("product_id"),
                    "severity": a.get("severity"),
                    "message": a.get("message"),
                }
                for a in sorted_alerts[:5]
            ]

            # Statistiques de performance globales – utilisent le cache
            perf_summary = self.get_performance_summary(use_cache=True)

            dashboard = {
                "summary": {
                    "total_products": total_products,
                    "models_trained": models_trained,
                    "total_predictions": total_predictions,
                    "active_alerts": len(active_alerts),
                },
                "alerts_breakdown": alert_severity_counts,
                "top_risks": top_risks,
                "performance": perf_summary,
            }
            logger.info("📊 Dashboard data généré")
            return dashboard
        except Exception as exc:
            logger.error(f"❌ Erreur get_dashboard_data : {exc}")
            return {"error": str(exc), "success": False}

    def get_product_detail(self, product_id: int) -> Dict[str, Any]:
        """Retourne l'analyse complète d'un produit pour la vue détail."""
        try:
            # Infos produit de base
            product_resp = (
                self.supabase.table("products").select("*").eq("id", product_id).limit(1).execute()
            )
            if not product_resp.data:
                raise ValueError(f"Produit {product_id} introuvable")
            product_info = product_resp.data[0]

            # Stock actuel
            stock_df = load_stock_levels(product_id, latest_only=True)
            current_stock = (
                float(stock_df["quantity_available"].iloc[0]) if not stock_df.empty else 0.0
            )

            # Prédiction + analyses (pas de save en DB pour cette vue)
            forecast_result = self.forecaster.generate_product_forecast(
                product_id=product_id, save_to_db=False
            )
            if not forecast_result.get("success"):
                raise RuntimeError(forecast_result.get("error", "Erreur prédiction"))

            # Évaluation du modèle
            evaluation_result = self.evaluator.evaluate_single_product(product_id)

            detail = {
                "product": {
                    "id": product_id,
                    "name": product_info.get("name"),
                    "sku": product_info.get("sku"),
                    "category": product_info.get("category"),
                    "current_stock": current_stock,
                },
                "forecast": {
                    "generated_at": forecast_result["generated_at"],
                    "period": forecast_result["forecast_period"],
                    "predictions": forecast_result["predictions"],
                    "stockout_analysis": forecast_result["stockout_analysis"],
                    "reorder_recommendation": forecast_result["reorder_recommendation"],
                    "alert_level": forecast_result["alert_level"],
                },
                "performance": {
                    "metrics": evaluation_result.get("metrics", {}),
                    "quality": evaluation_result.get("quality_analysis", {}),
                },
            }
            logger.info(f"📄 Détail produit {product_id} généré")
            return detail
        except Exception as exc:
            logger.error(f"❌ Erreur get_product_detail({product_id}) : {exc}")
            return {"success": False, "error": str(exc), "product_id": product_id}

    def get_active_alerts(self) -> Dict[str, Any]:
        """Retourne la liste des alertes non résolues, triées par priorité."""
        try:
            resp = (
                self.supabase.table("alerts").select("*").eq("is_resolved", False).execute()
            )
            alerts: List[Dict[str, Any]] = resp.data or []

            alerts_sorted = sorted(
                alerts,
                key=lambda a: (
                    self._SEVERITY_ORDER.get(a.get("severity", "UNKNOWN"), 5),
                    a.get("created_at", ""),
                ),
            )
            logger.info(f"🚨 {len(alerts_sorted)} alertes actives récupérées")
            return {"total_active_alerts": len(alerts_sorted), "alerts": alerts_sorted}
        except Exception as exc:
            logger.error(f"❌ Erreur get_active_alerts : {exc}")
            return {"success": False, "error": str(exc)}

    def get_performance_summary(self, use_cache: bool = False) -> Dict[str, Any]:
        """Retourne un résumé agrégé des performances des modèles."""
        cache_key = "performance_summary"
        if use_cache and cache_key in self._cache:
            cached_entry = self._cache[cache_key]
            if (datetime.now() - cached_entry["timestamp"]).total_seconds() < self._CACHE_TTL_SECONDS:
                logger.debug("⏱️ Utilisation du cache pour performance_summary")
                return cached_entry["data"]

        try:
            eval_report = self.evaluator.evaluate_all_products()
            perf_data = {
                "evaluation_date": eval_report.get("evaluation_date"),
                "avg_mape": eval_report.get("summary_statistics", {}).get("mape", {}).get("mean"),
                "mape_distribution": eval_report.get("summary_statistics", {}).get("mape", {}),
                "rmse_distribution": eval_report.get("summary_statistics", {}).get("rmse", {}),
                "quality_distribution": eval_report.get("recommendations", {}).get(
                    "quality_distribution", {}
                ),
                "global_strategy": eval_report.get("recommendations", {}).get("global_strategy"),
            }

            # Mise en cache
            self._cache[cache_key] = {"timestamp": datetime.now(), "data": perf_data}
            logger.info("📈 Performance summary recalculé et mis en cache")
            return perf_data
        except Exception as exc:
            logger.error(f"❌ Erreur get_performance_summary : {exc}")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Utils internes
    # ------------------------------------------------------------------

    def _severity_rank(self, severity: str) -> int:
        """Retourne le rang numérique associé à la sévérité (pour tri)."""
        return self._SEVERITY_ORDER.get(severity, 5)