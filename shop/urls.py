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


    # Anciennes URLs de gestion de produits
    path('ajouter-produit/', views.add_product, name='add_product'),
    path('modifier-produit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('supprimer-produit/<int:product_id>/', views.delete_product, name='delete_product'),
    
    # URLs pour les clients
    path('visiter-boutiques/', views.visit_shops, name='visit_shops'),
    path('produit/<int:product_id>/', views.product_detail, name='product_detail'),
    path('ajouter-au-panier/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('panier/', views.cart_detail, name='cart_detail'),
    path('panier/supprimer/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('panier/mettre-a-jour/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('paiement/', views.checkout_view, name='checkout_view'),
    path('paiement/traiter/', views.process_order, name='process_order'),
    path('commande-confirmee/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    # Nouvelles URLs pour le chat
    path('chat/<int:product_id>/', views.negotiation_chat_view, name='negotiation_chat'),
]
