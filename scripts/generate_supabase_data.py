#!/usr/bin/env python3
"""
Générateur de données réalistes pour OptiFlow - Supabase
Génère 11 mois de données cohérentes (jan-nov 2024) pour entraîner l'IA
"""

import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging
from dotenv import load_dotenv
import os
from supabase import create_client, Client

# Configuration
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class SupabaseDataGenerator:
    def __init__(self):
        """Initialise la connexion Supabase"""
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL', 'https://odnvwmcbuoffevpgooqh.supabase.co'),
            os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9kbnZ3bWNidW9mZmV2cGdvb3FoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTA1NjQ3NSwiZXhwIjoyMDY0NjMyNDc1fQ.yulUrzHdi9FVBeYbVFdVjoN1Nmyx6DuHhVTYDt9lAhw')
        )
        self.products = []
        self.customers = []
        self.year = 2024
        self.batch_size = 1000
        
    def load_products(self):
        """Charge les produits existants"""
        try:
            response = self.supabase.table('products').select('*').execute()
            self.products = response.data
            logger.info(f"📦 {len(self.products)} produits chargés")
            
            # Afficher les produits
            for p in self.products:
                logger.info(f"  - {p['name']} (#{p['id']}) - {p['list_price']}€")
                
        except Exception as e:
            logger.error(f"❌ Erreur chargement produits: {e}")
            raise
    
    def generate_customers(self) -> List[str]:
        """Génère une liste de clients fictifs"""
        customer_names = [
            "Tech Solutions SARL", "Bureau Plus", "Mobilier Pro",
            "Entreprise Martin", "Société Durand", "Office Design",
            "Workspace Innovation", "Corporate Furniture", "Business Equipment",
            "Professional Supplies", "Executive Office", "Modern Workspace",
            "Digital Corp", "Innovation Hub", "StartUp Factory",
            "Business Center", "Coworking Space", "Enterprise Solutions",
            "Modern Office", "Professional Services", "Corporate Design",
            "Furniture Plus", "Office Solutions", "Workspace Design",
            "Business Furniture", "Executive Supplies", "Modern Equipment"
        ]
        return customer_names
    
    def get_seasonality_factor(self, date: datetime) -> float:
        """Facteur de saisonnalité pour mobilier de bureau"""
        month = date.month
        
        seasonality = {
            1: 1.2,   # Janvier : budgets nouvelle année
            2: 0.9,   # Février : calme
            3: 1.1,   # Mars : reprise
            4: 1.0,   # Avril : normal
            5: 0.8,   # Mai : ralentissement
            6: 0.7,   # Juin : pré-été
            7: 0.6,   # Juillet : vacances
            8: 0.5,   # Août : creux été
            9: 1.4,   # Septembre : rentrée forte
            10: 1.3,  # Octobre : projets Q4
            11: 1.5,  # Novembre : fin d'année
        }
        
        base_factor = seasonality.get(month, 1.0)
        # Ajouter variabilité ±20%
        return base_factor * random.uniform(0.8, 1.2)
    
    def get_weekday_factor(self, date: datetime) -> float:
        """Facteur selon jour de la semaine"""
        weekday = date.weekday()
        factors = {
            0: 1.2,  # Lundi : fort
            1: 1.3,  # Mardi : pic
            2: 1.2,  # Mercredi : fort
            3: 1.1,  # Jeudi : bon
            4: 0.9,  # Vendredi : faible
            5: 0.3,  # Samedi : très faible
            6: 0.1   # Dimanche : quasi nul
        }
        return factors.get(weekday, 1.0)
    
    def generate_product_profile(self, product: Dict) -> Dict:
        """Génère un profil de vente pour un produit"""
        price = product['list_price']
        
        # Profil selon le prix
        if price > 500:  # Produits chers (bureaux)
            profile = {
                'avg_daily_sales': random.uniform(0.05, 0.3),
                'avg_qty_per_order': random.uniform(1, 2),
                'price_variance': 0.15,  # ±15%
                'stock_turnover_days': random.randint(45, 90),
                'reorder_point_ratio': 0.3,
                'max_stock_ratio': 2.0
            }
        elif price > 100:  # Prix moyen (armoires, rangements)
            profile = {
                'avg_daily_sales': random.uniform(0.2, 0.8),
                'avg_qty_per_order': random.uniform(2, 5),
                'price_variance': 0.10,
                'stock_turnover_days': random.randint(30, 60),
                'reorder_point_ratio': 0.25,
                'max_stock_ratio': 3.0
            }
        else:  # Produits bon marché (accessoires)
            profile = {
                'avg_daily_sales': random.uniform(0.5, 2.0),
                'avg_qty_per_order': random.uniform(3, 15),
                'price_variance': 0.05,
                'stock_turnover_days': random.randint(15, 30),
                'reorder_point_ratio': 0.20,
                'max_stock_ratio': 4.0
            }
        
        # Calculer les niveaux de stock
        avg_daily_consumption = profile['avg_daily_sales'] * profile['avg_qty_per_order']
        profile['stock_min'] = math.ceil(avg_daily_consumption * profile['stock_turnover_days'] * profile['reorder_point_ratio'])
        profile['stock_max'] = math.ceil(avg_daily_consumption * profile['stock_turnover_days'] * profile['max_stock_ratio'])
        profile['stock_initial'] = random.randint(profile['stock_min'], profile['stock_max'])
        
        return profile
    
    def generate_sales_data(self) -> List[Dict]:
        """Génère les données de vente pour 11 mois"""
        logger.info("💰 Génération des ventes...")
        
        sales_data = []
        customers = self.generate_customers()
        
        # Profils par produit
        product_profiles = {}
        for product in self.products:
            product_profiles[product['id']] = self.generate_product_profile(product)
        
        # Génération jour par jour
        start_date = datetime(self.year, 1, 1)
        end_date = datetime(self.year, 11, 30)  # Jusqu'à novembre
        current_date = start_date
        
        order_counter = 1000  # Numéro de commande
        
        while current_date <= end_date:
            # Facteurs multiplicateurs
            season_factor = self.get_seasonality_factor(current_date)
            weekday_factor = self.get_weekday_factor(current_date)
            
            # Générer les ventes du jour
            daily_sales = []
            
            for product in self.products:
                profile = product_profiles[product['id']]
                
                # Probabilité de vente
                base_prob = profile['avg_daily_sales']
                final_prob = base_prob * season_factor * weekday_factor
                
                # Décider si vente aujourd'hui
                if random.random() < final_prob:
                    # Quantité
                    qty = max(1, int(profile['avg_qty_per_order'] * random.uniform(0.5, 2.0)))
                    
                    # Prix avec variance
                    base_price = product['list_price']
                    price_variance = profile['price_variance']
                    unit_price = base_price * random.uniform(1 - price_variance, 1 + price_variance)
                    
                    # Total et marge
                    total_amount = qty * unit_price
                    cost_price = base_price * 0.6  # Marge estimée 40%
                    margin = total_amount - (qty * cost_price)
                    
                    # Client
                    customer = random.choice(customers)
                    
                    # Ordre aléatoire dans la journée
                    order_time = current_date.replace(
                        hour=random.randint(8, 18),
                        minute=random.randint(0, 59)
                    )
                    
                    sale = {
                        'product_id': product['id'],
                        'odoo_order_id': f'SO{order_counter:05d}',
                        'customer_name': customer,
                        'quantity': qty,
                        'unit_price': round(unit_price, 2),
                        'total_amount': round(total_amount, 2),
                        'margin': round(margin, 2),
                        'order_date': order_time.isoformat()
                    }
                    
                    daily_sales.append(sale)
                    order_counter += 1
            
            # Ajouter les ventes du jour
            sales_data.extend(daily_sales)
            
            # Afficher progression
            if current_date.day == 1:
                logger.info(f"📅 {current_date.strftime('%B %Y')} - {len(sales_data)} ventes générées")
            
            current_date += timedelta(days=1)
        
        logger.info(f"✅ {len(sales_data)} ventes générées pour 11 mois")
        return sales_data
    
    def generate_stock_data(self, sales_data: List[Dict]) -> List[Dict]:
        """Génère les données de stock cohérentes avec les ventes"""
        logger.info("📊 Génération des stocks...")
        
        stock_data = []
        
        # Profils par produit
        product_profiles = {}
        for product in self.products:
            product_profiles[product['id']] = self.generate_product_profile(product)
        
        # Stocks initiaux (1er janvier)
        current_stocks = {}
        for product in self.products:
            profile = product_profiles[product['id']]
            current_stocks[product['id']] = profile['stock_initial']
            
            # Enregistrement stock initial
            stock_data.append({
                'product_id': product['id'],
                'odoo_product_id': product.get('odoo_id', product['id']),
                'quantity_on_hand': current_stocks[product['id']],
                'quantity_forecasted': current_stocks[product['id']],
                'quantity_incoming': 0,
                'quantity_outgoing': 0,
                'location': 'Stock Principal',
                'recorded_at': datetime(self.year, 1, 1).isoformat()
            })
        
        # Grouper les ventes par jour
        sales_by_date = {}
        for sale in sales_data:
            date_key = sale['order_date'][:10]  # YYYY-MM-DD
            if date_key not in sales_by_date:
                sales_by_date[date_key] = []
            sales_by_date[date_key].append(sale)
        
        # Simuler jour par jour
        start_date = datetime(self.year, 1, 2)  # Après le stock initial
        end_date = datetime(self.year, 11, 30)
        current_date = start_date
        
        while current_date <= end_date:
            date_key = current_date.strftime('%Y-%m-%d')
            
            # Appliquer les ventes du jour
            if date_key in sales_by_date:
                for sale in sales_by_date[date_key]:
                    product_id = sale['product_id']
                    qty_sold = sale['quantity']
                    current_stocks[product_id] -= qty_sold
            
            # Réapprovisionnement (tous les lundis)
            if current_date.weekday() == 0:  # Lundi
                for product in self.products:
                    product_id = product['id']
                    profile = product_profiles[product_id]
                    current_stock = current_stocks[product_id]
                    
                    # Réapprovisionner si sous le seuil
                    if current_stock < profile['stock_min']:
                        reorder_qty = profile['stock_max'] - current_stock
                        current_stocks[product_id] = profile['stock_max']
                        
                        # Enregistrer le réapprovisionnement
                        stock_data.append({
                            'product_id': product_id,
                            'odoo_product_id': product.get('odoo_id', product_id),
                            'quantity_on_hand': current_stocks[product_id],
                            'quantity_forecasted': current_stocks[product_id],
                            'quantity_incoming': reorder_qty,
                            'quantity_outgoing': 0,
                            'location': 'Stock Principal',
                            'recorded_at': current_date.isoformat()
                        })
            
            # Enregistrement quotidien du stock (lundi et vendredi)
            if current_date.weekday() in [0, 4]:  # Lundi et vendredi
                for product in self.products:
                    product_id = product['id']
                    
                    # Calculer prévisionnel (stock - ventes prévues 7 jours)
                    profile = product_profiles[product_id]
                    expected_sales_7d = profile['avg_daily_sales'] * profile['avg_qty_per_order'] * 7
                    forecasted = max(0, current_stocks[product_id] - expected_sales_7d)
                    
                    stock_data.append({
                        'product_id': product_id,
                        'odoo_product_id': product.get('odoo_id', product_id),
                        'quantity_on_hand': current_stocks[product_id],
                        'quantity_forecasted': forecasted,
                        'quantity_incoming': 0,
                        'quantity_outgoing': expected_sales_7d,
                        'location': 'Stock Principal',
                        'recorded_at': current_date.isoformat()
                    })
            
            current_date += timedelta(days=1)
        
        logger.info(f"✅ {len(stock_data)} enregistrements de stock générés")
        return stock_data
    
    def insert_data_batch(self, table_name: str, data: List[Dict]):
        """Insère les données par batch pour de meilleures performances"""
        logger.info(f"💾 Insertion en base - table {table_name}...")
        
        total_inserted = 0
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i+self.batch_size]
            
            try:
                response = self.supabase.table(table_name).insert(batch).execute()
                total_inserted += len(batch)
                logger.info(f"  📝 {total_inserted}/{len(data)} enregistrements insérés")
            except Exception as e:
                logger.error(f"❌ Erreur insertion batch {i}-{i+len(batch)}: {e}")
                # Essayer un par un pour identifier les problèmes
                for item in batch:
                    try:
                        self.supabase.table(table_name).insert([item]).execute()
                        total_inserted += 1
                    except Exception as item_error:
                        logger.error(f"❌ Erreur item: {item_error}")
                        logger.error(f"Item problématique: {item}")
        
        logger.info(f"✅ {total_inserted} enregistrements insérés dans {table_name}")
        return total_inserted
    
    def clean_existing_data(self):
        """Nettoie les données existantes (optionnel)"""
        logger.info("🧹 Nettoyage des données existantes...")
        
        try:
            # Vider les tables
            self.supabase.table('sales_history').delete().neq('id', 0).execute()
            self.supabase.table('stock_levels').delete().neq('id', 0).execute()
            logger.info("✅ Tables nettoyées")
        except Exception as e:
            logger.error(f"⚠️ Erreur nettoyage: {e}")
    
    def generate_all_data(self, clean_first: bool = False):
        """Génère toutes les données"""
        logger.info("🚀 Génération complète des données OptiFlow")
        logger.info("=" * 60)
        
        # Charger les produits
        self.load_products()
        
        if not self.products:
            logger.error("❌ Aucun produit trouvé")
            return
        
        # Nettoyer si demandé
        if clean_first:
            self.clean_existing_data()
        
        # 1. Générer les ventes
        sales_data = self.generate_sales_data()
        
        # 2. Générer les stocks (basé sur les ventes)
        stock_data = self.generate_stock_data(sales_data)
        
        # 3. Insérer en base
        sales_inserted = self.insert_data_batch('sales_history', sales_data)
        stock_inserted = self.insert_data_batch('stock_levels', stock_data)
        
        # 4. Résumé
        logger.info("=" * 60)
        logger.info("✅ Génération terminée!")
        logger.info(f"📊 Résumé:")
        logger.info(f"   - Produits: {len(self.products)}")
        logger.info(f"   - Ventes: {sales_inserted}")
        logger.info(f"   - Stocks: {stock_inserted}")
        logger.info(f"   - Période: Jan-Nov {self.year}")
        logger.info(f"   - Volume total: {sales_inserted + stock_inserted} enregistrements")


def main():
    """Fonction principale"""
    generator = SupabaseDataGenerator()
    
    print("\nGenerateur de donnees OptiFlow pour Supabase")
    print("=" * 50)
    print("Ce script va generer:")
    print("  - ~15 000 ventes realistes (11 mois)")
    print("  - ~3 000 enregistrements de stock")
    print("  - Patterns saisonniers et coherents")
    print("  - Donnees pretes pour l'IA")
    print("\nTemps estime: 2-3 minutes")
    
    # Lancer automatiquement sans confirmation
    print("\nLancement automatique de la generation...")
    generator.generate_all_data(clean_first=True)


if __name__ == "__main__":
    main()