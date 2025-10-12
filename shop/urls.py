# shop/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('creer-boutique/', views.create_shop, name='create_shop'),
    path('acceder-boutique/', views.login_view, name='login_view'),
    path('deconnexion/', views.logout_view, name='logout_view'),
    
    # Nouvelles URLs pour le tableau de bord
    path('tableau-de-bord/', views.dashboard, name='dashboard'),
    path('tableau-de-bord/produits/', views.manage_products, name='manage_products'),
    path('tableau-de-bord/commandes/', views.manage_orders, name='manage_orders'),
    path('tableau-de-bord/commandes/<int:order_id>/', views.order_detail, name='order_detail'),
    path('tableau-de-bord/boutique/', views.manage_shop, name='manage_shop'),
    path('tableau-de-bord/negociation/', views.configure_negotiation, name='configure_negotiation'),


    # Anciennes URLs de gestion de produits
    path('ajouter-produit/', views.add_product, name='add_product'),
    path('modifier-produit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('supprimer-produit/<int:product_id>/', views.delete_product, name='delete_product'),
    
    # AJOUT : URLs pour la navigation et la recherche de produits avancée
    path('produits/', views.product_list, name='product_list'),
    path('produits/recherche/', views.product_search, name='product_search'),
    path('produits/categorie/<slug:category_slug>/', views.products_by_category, name='products_by_category'),
    path('produits/categorie/<slug:category_slug>/<slug:subcategory_slug>/', views.products_by_subcategory, name='products_by_subcategory'),
    
    # URLs pour les clients
    path('visiter-boutiques/', views.visit_shops, name='visit_shops'),
    path('produit/<int:product_id>/', views.product_detail, name='product_detail'),
    path('produit/<int:product_id>/avis/', views.add_review, name='add_review'), # AJOUT : URL pour ajouter un avis
    path('ajouter-au-panier/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('panier/', views.cart_detail, name='cart_detail'),
    path('panier/supprimer/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('panier/mettre-a-jour/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('paiement/', views.checkout_view, name='checkout_view'),
    path('paiement/traiter/', views.process_order, name='process_order'),
    path('commande-confirmee/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('produits/', views.product_search_list, name='product_search_list'),
    # Nouvelles URLs pour le chat
    path('chat/<int:product_id>/demarrer/', views.start_negotiation_view, name='start_negotiation'),
    path('chat/<int:conversation_id>/', views.conversation_detail_view, name='conversation_detail'),
    path('chat/', views.list_conversations_view, name='list_conversations'),
    path('api/chat/<int:conversation_id>/', views.chat_api, name='chat_api'),
    # Ajoutez cette ligne dans urlpatterns
    path('chat/<int:conversation_id>/negocier/', views.negotiation_chat, name='negotiation_chat'),
    # Ajoutez cette ligne dans urlpatterns
    # Ajoutez ces URLs à votre urlpatterns

    
    path('boutiques/', views.visit_shops, name='visit_shops'),
    path('boutiques/<slug:shop_slug>/', views.shop_detail_by_slug, name='shop_detail_by_slug'),
    path('boutiques/<slug:shop_slug>/produits/', views.shop_products, name='shop_products'),
    path('boutiques/<slug:shop_slug>/categorie/<slug:category_slug>/', views.shop_category, name='shop_category'),
    path('boutiques/<slug:shop_slug>/contact/', views.shop_contact, name='shop_contact'), # NOUVEAU
    
    
    # AJOUT : URL pour la création de compte client
    path('creer-client/', views.create_client, name='create_client'),
        # Tableau de bord client
    path('tableau-de-bord-client/', views.client_dashboard, name='client_dashboard'),
    
    # Historique des commandes client
    path('mes-commandes/', views.client_orders, name='client_orders'),
    
    # Détail d'une commande client
    path('ma-commande/<int:order_id>/', views.client_order_detail, name='client_order_detail'),
    path('api/product/<int:product_id>/variations/', views.get_product_variations, name='product_variations_api'),
    path('api/merchant/<int:merchant_id>/status/', views.merchant_status_api, name='merchant_status_api'),
    path('api/my-status/', views.my_status_api, name='my_status_api'),
    path('test-ai/', views.test_ai_service, name='test_ai_service'),

]
