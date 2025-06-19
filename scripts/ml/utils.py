"""
OptiFlow - Fonctions utilitaires pour le machine learning
=======================================================

Ce module contient toutes les fonctions communes pour :
- Connexion à Supabase
- Chargement des données (ventes, stocks)
- Préparation des données pour Prophet
- Calculs métier (rupture, réapprovisionnement)

Auteur : Votre équipe OptiFlow
Date : Décembre 2024
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Configuration des logs pour debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()


def get_supabase_connection() -> Client:
    """
    Établit une connexion à Supabase.
    
    🎯 POURQUOI CETTE FONCTION ?
    - Centralise la connexion DB (pas de duplication de code)
    - Gère les erreurs de connexion proprement
    - Utilise les variables d'environnement sécurisées
    
    Returns:
        Client: Instance Supabase connectée
        
    Raises:
        Exception: Si la connexion échoue
        
    💡 EXEMPLE D'USAGE :
        supabase = get_supabase_connection()
        data = supabase.table('products').select('*').execute()
    """
    try:
        # Récupération des credentials depuis .env
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')  
        
        # Vérification que les variables existent
        if not url or not key:
            raise ValueError("Variables SUPABASE_URL ou SUPABASE_KEY manquantes dans .env")
        
        # Création de la connexion
        supabase: Client = create_client(url, key)
        logger.info("✅ Connexion Supabase établie avec succès")
        
        return supabase
        
    except Exception as e:
        logger.error(f"❌ Erreur connexion Supabase : {e}")
        raise


def load_sales_data(product_id: int = None) -> pd.DataFrame:
    """
    Charge l'historique des ventes depuis Supabase.
    
    🎯 POURQUOI CETTE FONCTION ?
    - Les données de vente sont la BASE des prédictions Prophet
    - Besoin de formatter les dates correctement
    - Possibilité de filtrer par produit ou charger tout
    
    Args:
        product_id (int, optional): ID du produit. Si None, charge tous les produits.
        
    Returns:
        pd.DataFrame: Données avec colonnes ['date', 'product_id', 'quantity_sold', 'order_date']
        
    💡 EXEMPLE D'USAGE :
        # Toutes les ventes
        all_sales = load_sales_data()
        
        # Ventes d'un produit spécifique
        canape_sales = load_sales_data(product_id=5)
    """
    try:
        supabase = get_supabase_connection()
        
        # Construction de la requête
        query = supabase.table('sales_history').select('*')
        
        # Filtrage par produit si spécifié
        if product_id is not None:
            query = query.eq('product_id', product_id)
            logger.info(f"📊 Chargement ventes pour produit {product_id}")
        else:
            logger.info("📊 Chargement de toutes les ventes")
        
        # Exécution de la requête
        response = query.execute()
        
        # Vérification qu'on a des données
        if not response.data:
            logger.warning("⚠️ Aucune donnée de vente trouvée")
            return pd.DataFrame()
        
        # Conversion en DataFrame
        df = pd.DataFrame(response.data)
        
        # ÉTAPE CRUCIALE : Conversion des dates
        # Prophet a besoin de dates au format datetime
        # CORRECTION : La colonne s'appelle 'order_date' dans votre table !
        df['date'] = pd.to_datetime(df['order_date'])
        
        # Renommer quantity en quantity_sold pour plus de clarté
        if 'quantity' in df.columns:
            df['quantity_sold'] = df['quantity']
        
        # Tri par date (important pour les séries temporelles)
        df = df.sort_values('date').reset_index(drop=True)
        
        logger.info(f"✅ {len(df)} lignes de vente chargées")
        logger.info(f"📅 Période : {df['date'].min()} à {df['date'].max()}")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Erreur chargement ventes : {e}")
        raise


def load_stock_levels(product_id: int, latest_only: bool = True) -> pd.DataFrame:
    """
    Charge les niveaux de stock depuis Supabase.
    
    🎯 POURQUOI CETTE FONCTION ?
    - Pour calculer combien de jours on peut tenir (stock runway)
    - Option latest_only=True pour juste le stock actuel
    - Option latest_only=False pour l'historique complet (analyses)
    
    Args:
        product_id (int): ID du produit obligatoire
        latest_only (bool): Si True, ne retourne que le stock le plus récent
        
    Returns:
        pd.DataFrame: Données avec colonnes ['date', 'product_id', 'quantity_available', 'recorded_at']
        
    💡 EXEMPLE D'USAGE :
        # Stock actuel seulement
        current_stock = load_stock_levels(product_id=5, latest_only=True)
        stock_qty = current_stock['quantity_available'].iloc[0]
        
        # Historique complet des stocks
        stock_history = load_stock_levels(product_id=5, latest_only=False)
    """
    try:
        supabase = get_supabase_connection()
        
        # Requête de base
        query = supabase.table('stock_levels').select('*').eq('product_id', product_id)
        
        if latest_only:
            # On veut juste le stock le plus récent
            # CORRECTION : Tri sur 'recorded_at' et non 'date'
            query = query.order('recorded_at', desc=True).limit(1)
            logger.info(f"📦 Chargement stock actuel pour produit {product_id}")
        else:
            # On veut tout l'historique
            query = query.order('recorded_at', desc=False)  # Tri chronologique
            logger.info(f"📦 Chargement historique stock pour produit {product_id}")
        
        response = query.execute()
        
        if not response.data:
            logger.warning(f"⚠️ Aucun stock trouvé pour produit {product_id}")
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        # CORRECTION : La colonne s'appelle 'recorded_at' dans votre table !
        df['date'] = pd.to_datetime(df['recorded_at'])
        
        # Renommer pour clarté
        if 'quantity_on_hand' in df.columns:
            df['quantity_available'] = df['quantity_on_hand']
        
        if latest_only:
            logger.info(f"✅ Stock actuel : {df['quantity_available'].iloc[0]} unités")
        else:
            logger.info(f"✅ {len(df)} entrées d'historique stock chargées")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Erreur chargement stock : {e}")
        raise


def prepare_prophet_data(df: pd.DataFrame, date_col: str = 'date', value_col: str = 'quantity_sold') -> pd.DataFrame:
    """
    Prépare les données au format Prophet (colonnes 'ds' et 'y').
    
    🎯 POURQUOI CETTE FONCTION ?
    Prophet est TRÈS exigeant sur le format :
    - Colonne 'ds' : dates (datetime)
    - Colonne 'y' : valeurs à prédire (numeric)
    - Pas de valeurs manquantes
    - Données agrégées par jour (sinon Prophet peut bugguer)
    
    Args:
        df (pd.DataFrame): DataFrame avec colonnes date et valeur
        date_col (str): Nom de la colonne date
        value_col (str): Nom de la colonne valeur (ex: quantity_sold)
        
    Returns:
        pd.DataFrame: Format Prophet avec colonnes ['ds', 'y']
        
    💡 EXEMPLE D'USAGE :
        sales_data = load_sales_data(product_id=5)
        prophet_data = prepare_prophet_data(sales_data)
        # Résultat : colonnes 'ds' (dates) et 'y' (quantités)
    """
    try:
        if df.empty:
            logger.warning("⚠️ DataFrame vide pour préparation Prophet")
            return pd.DataFrame(columns=['ds', 'y'])
        
        # Vérifier que les colonnes existent
        if date_col not in df.columns:
            raise ValueError(f"Colonne '{date_col}' introuvable dans le DataFrame")
        if value_col not in df.columns:
            raise ValueError(f"Colonne '{value_col}' introuvable dans le DataFrame")
        
        # Copie pour éviter de modifier l'original
        df_clean = df.copy()
        
        # ÉTAPE 1 : Conversion de la date si nécessaire
        df_clean[date_col] = pd.to_datetime(df_clean[date_col])
        
        # ÉTAPE 2 : Agrégation par jour (important si plusieurs ventes/jour)
        # Prophet préfère une ligne par jour
        df_agg = df_clean.groupby(df_clean[date_col].dt.date)[value_col].sum().reset_index()
        df_agg[date_col] = pd.to_datetime(df_agg[date_col])
        
        # ÉTAPE 3 : Format Prophet obligatoire
        prophet_df = pd.DataFrame({
            'ds': df_agg[date_col],  # 'ds' = date stamp
            'y': df_agg[value_col]   # 'y' = valeur à prédire
        })
        
        # ÉTAPE 4 : Nettoyer les valeurs aberrantes
        # Remplacer les valeurs négatives par 0 (pas de vente négative)
        prophet_df['y'] = prophet_df['y'].clip(lower=0)
        
        # Supprimer les NaN
        prophet_df = prophet_df.dropna()
        
        # Tri par date
        prophet_df = prophet_df.sort_values('ds').reset_index(drop=True)
        
        logger.info(f"✅ Données Prophet préparées : {len(prophet_df)} jours")
        logger.info(f"📅 Période : {prophet_df['ds'].min().date()} à {prophet_df['ds'].max().date()}")
        logger.info(f"📊 Ventes totales : {prophet_df['y'].sum()}")
        
        return prophet_df
        
    except Exception as e:
        logger.error(f"❌ Erreur préparation Prophet : {e}")
        raise


def calculate_days_until_stockout(current_stock: float, daily_forecast: pd.DataFrame) -> dict:
    """
    Calcule le nombre de jours avant rupture de stock.
    
    🎯 POURQUOI CETTE FONCTION ?
    C'est LE calcul clé d'OptiFlow ! Répondre à : "Quand vais-je être en rupture ?"
    
    Logique :
    1. Stock actuel - demande jour 1 = stock restant
    2. Stock restant - demande jour 2 = nouveau stock restant
    3. Répéter jusqu'à stock restant < 0
    4. Date de rupture = ce jour-là
    
    Args:
        current_stock (float): Stock actuel en unités
        daily_forecast (pd.DataFrame): Prédictions avec colonnes ['ds', 'yhat']
        
    Returns:
        dict: {
            'days_until_stockout': int,
            'stockout_date': datetime,
            'confidence': str
        }
        
    💡 EXEMPLE D'USAGE :
        current_stock = 50
        forecast = model.predict(future_dates)
        result = calculate_days_until_stockout(current_stock, forecast)
        # {'days_until_stockout': 23, 'stockout_date': '2024-12-31', 'confidence': 'high'}
    """
    try:
        if daily_forecast.empty:
            logger.warning("⚠️ Pas de prévision pour calcul rupture")
            return {
                'days_until_stockout': 0,
                'stockout_date': None,
                'confidence': 'none'
            }
        
        # Initialisation
        remaining_stock = float(current_stock)
        stockout_date = None
        days_count = 0
        
        # SIMULATION JOUR PAR JOUR
        for _, row in daily_forecast.iterrows():
            predicted_demand = max(0, row['yhat'])  # Pas de demande négative
            
            # Stock après la demande de ce jour
            remaining_stock -= predicted_demand
            days_count += 1
            
            # Rupture détectée ?
            if remaining_stock <= 0:
                stockout_date = row['ds']
                break
        
        # Calcul du niveau de confiance
        # (basé sur la variance des prédictions si disponible)
        if 'yhat_lower' in daily_forecast.columns and 'yhat_upper' in daily_forecast.columns:
            # Variance moyenne des prédictions
            avg_uncertainty = (daily_forecast['yhat_upper'] - daily_forecast['yhat_lower']).mean()
            avg_demand = daily_forecast['yhat'].mean()
            
            if avg_uncertainty / max(avg_demand, 1) < 0.2:
                confidence = 'high'
            elif avg_uncertainty / max(avg_demand, 1) < 0.5:
                confidence = 'medium'
            else:
                confidence = 'low'
        else:
            confidence = 'medium'  # Par défaut
        
        result = {
            'days_until_stockout': days_count if stockout_date else len(daily_forecast),
            'stockout_date': stockout_date,
            'confidence': confidence
        }
        
        if stockout_date:
            logger.info(f"⚠️ Rupture prévue dans {days_count} jours ({stockout_date.date()})")
        else:
            logger.info(f"✅ Stock suffisant pour {len(daily_forecast)} jours")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur calcul rupture : {e}")
        raise


def calculate_reorder_quantity(
    forecast_df: pd.DataFrame, 
    lead_time_days: int = 7, 
    safety_stock_days: int = 3, 
    minimum_order_qty: int = 1
) -> dict:
    """
    Calcule la quantité optimale à commander.
    
    🎯 POURQUOI CETTE FONCTION ?
    Répondre à : "Combien commander pour éviter la rupture ?"
    
    Formule OptiFlow :
    Quantité = (Demande pendant délai + Stock sécurité) - Stock actuel
    Avec respect du MOQ (Minimum Order Quantity)
    
    Args:
        forecast_df (pd.DataFrame): Prédictions futures avec 'yhat'
        lead_time_days (int): Délai livraison fournisseur
        safety_stock_days (int): Stock de sécurité en jours
        minimum_order_qty (int): Quantité minimum commande
        
    Returns:
        dict: {
            'recommended_quantity': int,
            'rationale': str,
            'covers_days': int
        }
        
    💡 EXEMPLE D'USAGE :
        forecast = model.predict(future_30_days)
        order = calculate_reorder_quantity(
            forecast, 
            lead_time_days=5, 
            safety_stock_days=7,
            minimum_order_qty=10
        )
    """
    try:
        if forecast_df.empty:
            logger.warning("⚠️ Pas de prévision pour calcul commande")
            return {
                'recommended_quantity': minimum_order_qty,
                'rationale': 'Aucune prévision disponible, commande minimum',
                'covers_days': 0
            }
        
        # CALCUL DE LA DEMANDE PRÉVISIONNELLE
        total_period = lead_time_days + safety_stock_days
        
        # Prendre les N premiers jours de prévision
        period_forecast = forecast_df.head(total_period)
        
        # Demande totale sur la période
        total_demand = period_forecast['yhat'].sum()
        
        # Assurer une demande minimum positive
        total_demand = max(0, total_demand)
        
        # AJUSTEMENTS BUSINESS
        # Arrondir à l'entier supérieur (on ne commande pas 12.3 unités)
        recommended_qty = int(np.ceil(total_demand))
        
        # Respecter la quantité minimum de commande
        if recommended_qty < minimum_order_qty:
            recommended_qty = minimum_order_qty
            rationale = f"Quantité ajustée au MOQ de {minimum_order_qty} unités"
        else:
            rationale = f"Couvre {lead_time_days}j délai + {safety_stock_days}j sécurité"
        
        # CALCUL COUVERTURE
        # Avec cette quantité, combien de jours sommes-nous couverts ?
        daily_avg_demand = forecast_df['yhat'].mean()
        covers_days = int(recommended_qty / max(daily_avg_demand, 0.1))  # Éviter division par 0
        
        result = {
            'recommended_quantity': recommended_qty,
            'rationale': rationale,
            'covers_days': covers_days,
            'total_demand_forecast': total_demand,
            'avg_daily_demand': daily_avg_demand
        }
        
        logger.info(f"📦 Recommandation : {recommended_qty} unités")
        logger.info(f"📅 Couverture : {covers_days} jours")
        logger.info(f"🎯 {rationale}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur calcul commande : {e}")
        raise