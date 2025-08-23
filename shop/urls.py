# shop/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('creer-boutique/', views.create_shop, name='create_shop'),
    path('acceder-boutique/', views.login_view, name='login_view'),
    path('deconnexion/', views.logout_view, name='logout_view'),
    path('tableau-de-bord/', views.dashboard, name='dashboard'),
    path('ajouter-produit/', views.add_product, name='add_product'),
    path('modifier-produit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('supprimer-produit/<int:product_id>/', views.delete_product, name='delete_product'),
    path('visiter-boutiques/', views.visit_shops, name='visit_shops'),
    path('produit/<int:product_id>/', views.product_detail, name='product_detail'),
    path('ajouter-au-panier/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('panier/', views.cart_detail, name='cart_detail'),
    path('panier/supprimer/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('panier/mettre-a-jour/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('paiement/', views.checkout_view, name='checkout_view'),
    path('paiement/traiter/', views.process_order, name='process_order'), # Nouvelle URL
    path('commande-confirmee/<int:order_id>/', views.order_confirmation, name='order_confirmation'), # Nouvelle URL
]
