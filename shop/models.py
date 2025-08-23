# shop/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


# Le modèle Merchant (Commerçant)
class Merchant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True) 
    phone = models.CharField(max_length=20, unique=True)
    country = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# Le modèle Shop (Boutique)
class Shop(models.Model):
    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE)
    
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    image = models.ImageField(upload_to='shop_images/', blank=True, null=True)

    def __str__(self):
        return f"Boutique de {self.merchant}"

# Le modèle Product (Produit)
class Product(models.Model):
    # Chaque produit appartient à une boutique. 
    # Si la boutique est supprimée, ses produits le sont aussi.
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Prix avec 2 décimales
    stock = models.IntegerField(default=0) # Quantité en stock
    created_at = models.DateTimeField(auto_now_add=True) # Date de création automatique
    updated_at = models.DateTimeField(auto_now=True) # Date de mise à jour automatique

    def __str__(self):
        return self.name

# Le nouveau modèle ProductImage (Image de produit)
class ProductImage(models.Model):
    # Clé étrangère vers le modèle Product. 
    # Un produit peut avoir plusieurs images.
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='product_images/')

# Le nouveau modèle ProductVideo (Vidéo de produit)
class ProductVideo(models.Model):
    # Clé étrangère vers le modèle Product. 
    # Un produit peut avoir plusieurs vidéos.
    product = models.ForeignKey(Product, related_name='videos', on_delete=models.CASCADE)
    video = models.FileField(upload_to='product_videos/')

# Modèle pour le panier
class Cart(models.Model):
    # Un panier est lié à un utilisateur. Un utilisateur non authentifié aura un panier temporaire.
    # Pour l'instant, on lie le panier à un utilisateur, nous gérerons les utilisateurs non authentifiés plus tard.
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Panier de {self.user.username}"

# Modèle pour les articles dans le panier
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    # Propriété pour calculer le coût total de l'article
    @property
    def total_cost(self):
        return self.quantity * self.product.price


class Order(models.Model):
    """
    Modèle de commande.
    Représente une commande passée par un client.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    date_ordered = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=100, null=True)
    
    # Informations de livraison
    full_name = models.CharField(max_length=200, null=True)
    address = models.CharField(max_length=200, null=True)
    city = models.CharField(max_length=200, null=True)
    phone = models.CharField(max_length=50, null=True)

    @property
    def get_cart_total(self):
        orderitems = self.orderitem_set.all()
        total = sum([item.get_total for item in orderitems])
        return total

    @property
    def get_cart_items(self):
        orderitems = self.orderitem_set.all()
        total = sum([item.quantity for item in orderitems])
        return total

    def __str__(self):
        return str(self.id)

class OrderItem(models.Model):
    """
    Modèle d'article de commande.
    Représente un article individuel dans une commande.
    """
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0, null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    @property
    def get_total(self):
        if self.product:
            return self.product.price * self.quantity
        return Decimal(0)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"