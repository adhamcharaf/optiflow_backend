#!/usr/bin/env python3
"""
Test de connexion à Odoo CE avec OdooRPC
"""

import odoorpc
import json
from datetime import datetime
from typing import Dict, List, Any


class OdooConnector:
    def __init__(self, host: str = 'localhost', port: int = 8069, 
                 db: str = 'odoo', username: str = 'admin', password: str = 'admin'):
        """
        Initialise la connexion à Odoo via OdooRPC
        """
        self.host = host
        self.port = port
        self.db = db
        self.username = username
        self.password = password
        self.odoo = None
        
    def connect(self):
        """Connexion à Odoo"""
        try:
            # Connexion au serveur Odoo
            self.odoo = odoorpc.ODOO(self.host, port=self.port)
            
            # Login
            self.odoo.login(self.db, self.username, self.password)
            
            print(f"✅ Connecté à Odoo!")
            print(f"📌 Version: {self.odoo.version}")
            print(f"👤 Utilisateur: {self.odoo.env.user.name} (ID: {self.odoo.env.uid})")
            print(f"🏢 Société: {self.odoo.env.user.company_id.name}")
            
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            raise
    
    def test_models_access(self):
        """Teste l'accès aux modèles nécessaires pour OptiFlow"""
        print("\n🔍 Test d'accès aux modèles Odoo...")
        
        models_to_test = {
            'product.product': 'Produits',
            'product.template': 'Modèles de produits',
            'stock.quant': 'Stock (Quantités)',
            'stock.move': 'Mouvements de stock',
            'stock.location': 'Emplacements',
            'sale.order': 'Commandes de vente',
            'sale.order.line': 'Lignes de commande',
            'res.partner': 'Clients/Fournisseurs',
        }
        
        for model_name, description in models_to_test.items():
            try:
                Model = self.odoo.env[model_name]
                count = Model.search_count([])
                print(f"✅ {description} ({model_name}): {count} enregistrements")
            except Exception as e:
                print(f"❌ {description} ({model_name}): {str(e)}")
    
    def get_products_sample(self):
        """Récupère un échantillon de produits avec leurs stocks"""
        print("\n📦 Analyse des produits...")
        
        Product = self.odoo.env['product.product']
        
        # Chercher les produits de type 'product' (stockables)
        product_ids = Product.search([('type', '=', 'product')], limit=10)
        
        if not product_ids:
            print("⚠️ Aucun produit stockable trouvé")
            return []
        
        # Récupérer les données détaillées
        products = Product.browse(product_ids)
        
        print(f"\n📊 {len(products)} produits stockables trouvés:")
        print("-" * 80)
        
        products_data = []
        for product in products:
            data = {
                'id': product.id,
                'name': product.name,
                'reference': product.default_code or 'N/A',
                'qty_available': product.qty_available,
                'virtual_available': product.virtual_available,
                'incoming_qty': product.incoming_qty,
                'outgoing_qty': product.outgoing_qty,
                'list_price': product.list_price,
                'standard_price': product.standard_price,
                'categ_id': product.categ_id.name if product.categ_id else 'Sans catégorie'
            }
            products_data.append(data)
            
            # Affichage formaté
            print(f"\n🏷️ {data['name']} [{data['reference']}]")
            print(f"   📦 Stock physique: {data['qty_available']} unités")
            print(f"   📈 Stock prévisionnel: {data['virtual_available']} unités")
            print(f"   💰 Prix de vente: {data['list_price']}€ | Coût: {data['standard_price']}€")
            print(f"   📂 Catégorie: {data['categ_id']}")
        
        return products_data
    
    def get_stock_locations(self):
        """Liste les emplacements de stock"""
        print("\n📍 Emplacements de stock:")
        
        Location = self.odoo.env['stock.location']
        locations = Location.search_read(
            [('usage', '=', 'internal')],
            ['name', 'complete_name', 'usage'],
            limit=10
        )
        
        for loc in locations:
            print(f"  - {loc['complete_name']}")
        
        return locations
    
    def get_recent_sales(self):
        """Récupère les ventes récentes"""
        print("\n💰 Commandes de vente récentes:")
        
        SaleOrder = self.odoo.env['sale.order']
        
        # Chercher les commandes confirmées
        order_ids = SaleOrder.search(
            [('state', 'in', ['sale', 'done'])],
            limit=5,
            order='date_order desc'
        )
        
        if not order_ids:
            print("⚠️ Aucune commande trouvée")
            # Cherchons les devis alors
            order_ids = SaleOrder.search([], limit=5, order='date_order desc')
        
        orders = SaleOrder.browse(order_ids)
        
        for order in orders:
            print(f"\n  📄 {order.name}")
            print(f"     Client: {order.partner_id.name}")
            print(f"     Date: {order.date_order}")
            print(f"     Total: {order.amount_total}€")
            print(f"     État: {order.state}")
    
    def create_test_product(self):
        """Crée un produit de test pour vérifier les permissions"""
        print("\n🧪 Test de création d'un produit...")
        
        try:
            Product = self.odoo.env['product.product']
            
            # Créer un produit test
            product_data = {
                'name': f'Produit Test OptiFlow {datetime.now().strftime("%H%M%S")}',
                'type': 'product',
                'list_price': 100.0,
                'standard_price': 60.0,
                'default_code': f'TEST-{datetime.now().strftime("%H%M%S")}',
            }
            
            product_id = Product.create(product_data)
            print(f"✅ Produit créé avec succès! ID: {product_id}")
            
            # Le supprimer immédiatement
            Product.browse(product_id).unlink()
            print("✅ Produit test supprimé")
            
        except Exception as e:
            print(f"❌ Erreur lors de la création: {e}")


def main():
    """Fonction principale"""
    print("🚀 Test de connexion Odoo pour OptiFlow\n")
    print("=" * 80)
    
    # Configuration
    config = {
        'host': 'localhost',
        'port': 8069,
        'db': 'odoo',
        'username': 'admin@test.com',
        'password': 'admin'
    }
    
    try:
        # Connexion
        connector = OdooConnector(**config)
        connector.connect()
        
        # Tests
        connector.test_models_access()
        connector.get_stock_locations()
        connector.get_products_sample()
        connector.get_recent_sales()
        connector.create_test_product()
        
        print("\n" + "=" * 80)
        print("✅ Tous les tests sont passés! Odoo est prêt pour OptiFlow.")
        print("\n💡 Prochaine étape: Configurer Supabase pour stocker ces données")
        
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        print("\n💡 Vérifiez que:")
        print("   - Docker est lancé")
        print("   - Odoo est accessible sur http://localhost:8069")
        print("   - Les identifiants sont corrects")


if __name__ == "__main__":
    main()