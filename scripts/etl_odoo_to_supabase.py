#!/usr/bin/env python3
"""
ETL Script: Odoo → Supabase
Synchronise les données d'Odoo vers Supabase pour OptiFlow
"""

import os
import sys
import odoorpc
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
import time

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class OptiFlowETL:
    def __init__(self):
        """Initialise les connexions Odoo et Supabase"""
        # Connexion Odoo
        self.odoo = None
        self.connect_odoo()
        
        # Connexion Supabase
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        
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
            logger.error(f"❌ Erreur connexion Odoo: {e}")
            sys.exit(1)
    
    def sync_products(self):
        """Synchronise les produits Odoo → Supabase"""
        logger.info("🔄 Synchronisation des produits...")
        start_time = time.time()
        
        try:
            # Récupérer les produits stockables d'Odoo
            Product = self.odoo.env['product.product']
            product_ids = Product.search([('type', '=', 'product')])
            products = Product.browse(product_ids)
            
            synced_count = 0
            for product in products:
                product_data = {
                    'odoo_id': product.id,
                    'name': product.name,
                    'reference': product.default_code or f'REF-{product.id}',
                    'category': product.categ_id.name if product.categ_id else 'Sans catégorie',
                    'list_price': float(product.list_price),
                    'standard_price': float(product.standard_price),
                    'is_active': product.active
                }
                
                # Upsert dans Supabase
                response = self.supabase.table('products').upsert(
                    product_data, 
                    on_conflict='odoo_id'
                ).execute()
                
                synced_count += 1
            
            logger.info(f"✅ {synced_count} produits synchronisés")
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ Erreur sync produits: {e}")
            raise
    
    def sync_stock_levels(self):
        """Synchronise les niveaux de stock"""
        logger.info("📊 Synchronisation des stocks...")
        
        try:
            # Récupérer les produits de Supabase
            products = self.supabase.table('products').select('*').execute()
            
            synced_count = 0
            for sup_product in products.data:
                # Récupérer le produit Odoo
                Product = self.odoo.env['product.product']
                product = Product.browse(sup_product['odoo_id'])
                
                stock_data = {
                    'product_id': sup_product['id'],
                    'odoo_product_id': sup_product['odoo_id'],
                    'quantity_on_hand': float(product.qty_available),
                    'quantity_forecasted': float(product.virtual_available),
                    'quantity_incoming': float(product.incoming_qty),
                    'quantity_outgoing': float(product.outgoing_qty),
                    'recorded_at': datetime.now().isoformat()
                }
                
                # Insérer dans Supabase
                self.supabase.table('stock_levels').insert(stock_data).execute()
                synced_count += 1
            
            logger.info(f"✅ {synced_count} niveaux de stock enregistrés")
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ Erreur sync stocks: {e}")
            raise
    
    def sync_sales_history(self, days_back=30):
        """Synchronise l'historique des ventes"""
        logger.info(f"💰 Synchronisation des ventes ({days_back} derniers jours)...")
        
        try:
            # Date de début
            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            # Récupérer les commandes confirmées
            SaleOrder = self.odoo.env['sale.order']
            order_ids = SaleOrder.search([
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', start_date)
            ])
            
            if not order_ids:
                logger.warning("⚠️ Aucune commande trouvée")
                return 0
            
            orders = SaleOrder.browse(order_ids)
            
            synced_count = 0
            for order in orders:
                # Pour chaque ligne de commande
                for line in order.order_line:
                    # Vérifier si c'est un produit stockable
                    if line.product_id.type != 'product':
                        continue
                    
                    # Trouver l'ID Supabase du produit
                    sup_product = self.supabase.table('products').select('id').eq(
                        'odoo_id', line.product_id.id
                    ).execute()
                    
                    if not sup_product.data:
                        continue
                    
                    # Calculer la marge
                    margin = (line.price_unit - line.product_id.standard_price) * line.product_uom_qty
                    
                    sale_data = {
                        'product_id': sup_product.data[0]['id'],
                        'odoo_order_id': order.name,
                        'customer_name': order.partner_id.name,
                        'quantity': float(line.product_uom_qty),
                        'unit_price': float(line.price_unit),
                        'total_amount': float(line.price_subtotal),
                        'margin': float(margin),
                        'order_date': order.date_order.isoformat()
                    }
                    
                    self.supabase.table('sales_history').insert(sale_data).execute()
                    synced_count += 1
            
            logger.info(f"✅ {synced_count} lignes de vente synchronisées")
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ Erreur sync ventes: {e}")
            raise
    
    def log_sync_result(self, sync_type: str, status: str, records: int, error: str = None):
        """Enregistre le résultat de la synchronisation"""
        log_data = {
            'sync_type': sync_type,
            'status': status,
            'records_processed': records,
            'error_message': error,
            'started_at': self.sync_start.isoformat(),
            'completed_at': datetime.now().isoformat(),
            'duration_seconds': int(time.time() - time.mktime(self.sync_start.timetuple()))
        }
        
        self.supabase.table('etl_sync_log').insert(log_data).execute()
    
    def run_full_sync(self):
        """Lance une synchronisation complète"""
        logger.info("🚀 Démarrage de la synchronisation complète OptiFlow")
        logger.info("=" * 60)
        
        self.sync_start = datetime.now()
        
        # 1. Synchroniser les produits
        try:
            product_count = self.sync_products()
            self.log_sync_result('products', 'success', product_count)
        except Exception as e:
            self.log_sync_result('products', 'failed', 0, str(e))
            
        # 2. Synchroniser les stocks
        try:
            stock_count = self.sync_stock_levels()
            self.log_sync_result('stock', 'success', stock_count)
        except Exception as e:
            self.log_sync_result('stock', 'failed', 0, str(e))
            
        # 3. Synchroniser les ventes
        try:
            sales_count = self.sync_sales_history()
            self.log_sync_result('sales', 'success', sales_count)
        except Exception as e:
            self.log_sync_result('sales', 'failed', 0, str(e))
        
        logger.info("=" * 60)
        logger.info("✅ Synchronisation terminée!")
        
        # Afficher un résumé
        self.display_summary()
    
    def display_summary(self):
        """Affiche un résumé des données synchronisées"""
        try:
            # Compter les enregistrements
            products = self.supabase.table('products').select('id', count='exact').execute()
            stocks = self.supabase.table('stock_levels').select('id', count='exact').execute()
            sales = self.supabase.table('sales_history').select('id', count='exact').execute()
            
            logger.info("\n📊 Résumé Supabase:")
            logger.info(f"   - Produits: {products.count}")
            logger.info(f"   - Enregistrements de stock: {stocks.count}")
            logger.info(f"   - Lignes de vente: {sales.count}")
            
        except Exception as e:
            logger.error(f"Erreur affichage résumé: {e}")


def main():
    """Fonction principale"""
    etl = OptiFlowETL()
    etl.run_full_sync()


if __name__ == "__main__":
    main()