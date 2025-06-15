#!/usr/bin/env python3
"""
Générateur de données de test pour OptiFlow
Crée un historique complet de ventes et mouvements de stock pour 2024
"""

import odoorpc
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging
from dotenv import load_dotenv
import os

# Configuration
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class TestDataGenerator:
    def __init__(self):
        """Initialise la connexion Odoo"""
        self.odoo = None
        self.connect_odoo()
        self.products = []
        self.customers = []
        self.year = 2024
        
    def connect_odoo(self):
        """Connexion à Odoo"""
        try:
            self.odoo = odoorpc.ODOO(
                os.getenv('ODOO_HOST'), 
                port=int(os.getenv('ODOO_PORT'))
            )
            self.odoo.login(
                os.getenv('ODOO_DB'),
                os.getenv('ODOO_USERNAME'),
                os.getenv('ODOO_PASSWORD')
            )
            logger.info("✅ Connecté à Odoo")
        except Exception as e:
            logger.error(f"❌ Erreur connexion: {e}")
            raise
    
    def get_products_and_customers(self):
        """Récupère les produits stockables et les clients"""
        # Produits
        Product = self.odoo.env['product.product']
        product_ids = Product.search([('type', '=', 'product')])
        self.products = Product.browse(product_ids)
        logger.info(f"📦 {len(self.products)} produits trouvés")
        
        # Clients (on prend les clients existants)
        Partner = self.odoo.env['res.partner']
        customer_ids = Partner.search([('is_company', '=', True)], limit=20)
        self.customers = Partner.browse(customer_ids)
        
        # Si pas assez de clients, on en crée
        if len(self.customers) < 10:
            self.create_test_customers()
    
    def create_test_customers(self):
        """Crée des clients de test"""
        logger.info("🏢 Création de clients de test...")
        
        Partner = self.odoo.env['res.partner']
        customer_names = [
            "Tech Solutions SARL", "Bureau Plus", "Mobilier Pro",
            "Entreprise Martin", "Société Durand", "Office Design",
            "Workspace Innovation", "Corporate Furniture", "Business Equipment",
            "Professional Supplies", "Executive Office", "Modern Workspace"
        ]
        
        for name in customer_names:
            try:
                partner_id = Partner.create({
                    'name': name,
                    'is_company': True,
                    'customer_rank': 1,
                    'email': f"{name.lower().replace(' ', '.')}@example.com"
                })
                self.customers.append(Partner.browse(partner_id))
            except:
                pass
    
    def get_seasonality_factor(self, date: datetime) -> float:
        """Retourne un facteur de saisonnalité basé sur le mois"""
        month = date.month
        
        # Patterns de vente typiques pour du mobilier de bureau
        seasonality = {
            1: 1.1,   # Janvier : budgets nouvelle année
            2: 0.9,   # Février : calme
            3: 1.0,   # Mars : normal
            4: 1.0,   # Avril : normal
            5: 0.8,   # Mai : ralentissement
            6: 0.7,   # Juin : creux avant été
            7: 0.6,   # Juillet : vacances
            8: 0.5,   # Août : creux été
            9: 1.3,   # Septembre : rentrée
            10: 1.2,  # Octobre : projets Q4
            11: 1.4,  # Novembre : black friday
            12: 1.5   # Décembre : fin d'année fiscale
        }
        
        # Ajouter un peu de randomness
        base_factor = seasonality.get(month, 1.0)
        return base_factor * (0.8 + random.random() * 0.4)
    
    def generate_sales_pattern(self, product) -> Dict:
        """Génère un pattern de vente pour un produit"""
        # Caractéristiques selon le prix
        if product.list_price > 500:  # Produits chers
            avg_daily_sales = random.uniform(0.1, 0.5)
            avg_qty_per_order = random.randint(1, 3)
        elif product.list_price > 100:  # Prix moyen
            avg_daily_sales = random.uniform(0.5, 2)
            avg_qty_per_order = random.randint(2, 8)
        else:  # Produits bon marché
            avg_daily_sales = random.uniform(1, 5)
            avg_qty_per_order = random.randint(5, 20)
        
        return {
            'avg_daily_sales': avg_daily_sales,
            'avg_qty_per_order': avg_qty_per_order,
            'stock_min': avg_qty_per_order * 10,  # Stock min = 10 jours de vente
            'stock_max': avg_qty_per_order * 30   # Stock max = 30 jours
        }
    
    def create_sale_order(self, date: datetime, customer, lines: List[Tuple]) -> int:
        """Crée une commande de vente"""
        SaleOrder = self.odoo.env['sale.order']
        
        # Créer la commande
        order_vals = {
            'partner_id': customer.id,
            'date_order': date.strftime('%Y-%m-%d %H:%M:%S'),
            'validity_date': (date + timedelta(days=30)).strftime('%Y-%m-%d'),
            'order_line': []
        }
        
        # Ajouter les lignes
        for product, qty, price in lines:
            order_vals['order_line'].append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price
            }))
        
        try:
            order_id = SaleOrder.create(order_vals)
            
            # Confirmer la commande
            order = SaleOrder.browse(order_id)
            order.action_confirm()
            
            # Livrer immédiatement (pour générer les mouvements de stock)
            for picking in order.picking_ids:
                picking.action_assign()
                for move in picking.move_ids:
                    move.quantity_done = move.product_uom_qty
                picking.button_validate()
            
            return order_id
            
        except Exception as e:
            logger.error(f"Erreur création commande: {e}")
            return None
    
    def adjust_stock_level(self, product, target_qty: float, date: datetime):
        """Ajuste le niveau de stock d'un produit"""
        try:
            # Obtenir le stock actuel
            current_qty = product.qty_available
            
            if abs(current_qty - target_qty) < 0.01:
                return  # Pas besoin d'ajuster
            
            # Créer un ajustement d'inventaire
            Inventory = self.odoo.env['stock.quant']
            Location = self.odoo.env['stock.location']
            
            # Trouver l'emplacement de stock principal
            location_id = Location.search([
                ('usage', '=', 'internal'),
                ('name', 'like', 'Stock')
            ], limit=1)[0]
            
            # Chercher ou créer le quant
            quant_id = Inventory.search([
                ('product_id', '=', product.id),
                ('location_id', '=', location_id)
            ], limit=1)
            
            if quant_id:
                quant = Inventory.browse(quant_id[0])
                quant.inventory_quantity = target_qty
                quant.action_apply_inventory()
            else:
                # Créer un nouveau quant
                Inventory.create({
                    'product_id': product.id,
                    'location_id': location_id,
                    'inventory_quantity': target_qty
                }).action_apply_inventory()
                
        except Exception as e:
            logger.error(f"Erreur ajustement stock {product.name}: {e}")
    
    def generate_year_data(self):
        """Génère les données pour toute l'année 2024"""
        logger.info(f"🚀 Génération des données pour {self.year}...")
        
        # Récupérer produits et clients
        self.get_products_and_customers()
        
        if not self.products or not self.customers:
            logger.error("❌ Pas assez de produits ou clients")
            return
        
        # Patterns de vente par produit
        product_patterns = {}
        for product in self.products:
            product_patterns[product.id] = self.generate_sales_pattern(product)
            # Stock initial au 1er janvier
            initial_stock = product_patterns[product.id]['stock_max']
            self.adjust_stock_level(product, initial_stock, datetime(self.year, 1, 1))
        
        # Compteurs
        total_orders = 0
        total_lines = 0
        
        # Générer jour par jour
        current_date = datetime(self.year, 1, 1)
        end_date = datetime(self.year, 12, 31)
        
        while current_date <= end_date:
            # Skip weekends (optionnel)
            if current_date.weekday() >= 5:  # Samedi/Dimanche
                if random.random() > 0.8:  # 20% de chance de vente weekend
                    current_date += timedelta(days=1)
                    continue
            
            # Facteur de saisonnalité
            season_factor = self.get_seasonality_factor(current_date)
            
            # Pour chaque produit, décider s'il y a des ventes
            daily_orders = []
            
            for product in self.products:
                pattern = product_patterns[product.id]
                
                # Probabilité de vente aujourd'hui
                sales_prob = pattern['avg_daily_sales'] * season_factor
                
                if random.random() < sales_prob:
                    # Quantité à vendre
                    qty = max(1, int(pattern['avg_qty_per_order'] * random.uniform(0.5, 1.5)))
                    
                    # Prix (peut varier légèrement)
                    price = product.list_price * random.uniform(0.95, 1.05)
                    
                    # Choisir un client
                    customer = random.choice(self.customers)
                    
                    daily_orders.append((product, qty, price, customer))
            
            # Grouper les commandes par client
            orders_by_customer = {}
            for product, qty, price, customer in daily_orders:
                if customer.id not in orders_by_customer:
                    orders_by_customer[customer.id] = []
                orders_by_customer[customer.id].append((product, qty, price))
            
            # Créer les commandes
            for customer_id, lines in orders_by_customer.items():
                customer = next(c for c in self.customers if c.id == customer_id)
                order_id = self.create_sale_order(current_date, customer, lines)
                if order_id:
                    total_orders += 1
                    total_lines += len(lines)
            
            # Réapprovisionner si nécessaire (tous les lundis)
            if current_date.weekday() == 0:  # Lundi
                for product in self.products:
                    current_stock = product.qty_available
                    pattern = product_patterns[product.id]
                    
                    # Réapprovisionner si en dessous du stock min
                    if current_stock < pattern['stock_min']:
                        target_stock = pattern['stock_max']
                        self.adjust_stock_level(product, target_stock, current_date)
                        logger.info(f"📦 Réappro {product.name}: {current_stock:.0f} → {target_stock:.0f}")
            
            # Afficher progression
            if current_date.day == 1:
                logger.info(f"📅 {current_date.strftime('%B %Y')} - {total_orders} commandes créées")
            
            current_date += timedelta(days=1)
        
        logger.info("=" * 60)
        logger.info(f"✅ Génération terminée!")
        logger.info(f"📊 Résumé:")
        logger.info(f"   - Commandes créées: {total_orders}")
        logger.info(f"   - Lignes de vente: {total_lines}")
        logger.info(f"   - Période: {self.year}")


def main():
    """Fonction principale"""
    generator = TestDataGenerator()
    
    # Confirmation
    print("\n⚠️  ATTENTION: Ce script va créer beaucoup de données dans Odoo!")
    print("Cela peut prendre 10-20 minutes selon la performance.")
    response = input("\nContinuer? (oui/non): ")
    
    if response.lower() in ['oui', 'o', 'yes', 'y']:
        generator.generate_year_data()
    else:
        print("❌ Annulé")


if __name__ == "__main__":
    main()