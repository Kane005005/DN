# Fichier : shop/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal, InvalidOperation

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
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    description = models.TextField(blank=True, null=True)
    stock = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    
class ProductVideo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='videos')
    video = models.FileField(upload_to='product_videos/')

# Le modèle Cart (Panier)
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Panier de {self.user.username}"
        
class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    quantity = models.IntegerField(default=1)
    
    def __str__(self):
        return f"{self.product.name} ({self.quantity})"
    
    @property
    def get_total(self):
        """
        Calcule le prix total pour cet article du panier.
        """
        return self.product.price * self.quantity
    
    # Ajoutez cette propriété pour correspondre à ce que le template attend
    @property
    def total_cost(self):
        """
        Alias pour get_total pour correspondre à l'attente du template.
        """
        return self.get_total

# Le modèle Order (Commande)
class Order(models.Model):
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
        """
        Calcule le prix total de la commande en sommant tous les articles.
        """
        orderitems = self.orderitem_set.all()
        total = sum([item.get_total for item in orderitems])
        return total

    @property
    def get_cart_items(self):
        """
        Calcule le nombre total d'articles dans la commande.
        """
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
        """
        Calcule le prix total pour cet article de commande.
        """
        # Assurez-vous que le produit existe avant d'accéder à son prix
        if self.product:
            return self.product.price * self.quantity
        return 0
    
    def __str__(self):
        return self.product.name

# Fichier : shop/models.py
# ... (le reste de ton code)

# Fichier : shop/models.py
from django.db import models
from django.contrib.auth.models import User

class Conversation(models.Model):
    """
    Représente une conversation de négociation entre un client et un commerçant.
    """
    # L'utilisateur client qui a initié la conversation.
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_conversations')
    # Le commerçant de la boutique du produit concerné.
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='merchant_conversations')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True) # Ajout pour marquer les conversations terminées

    def __str__(self):
        return f"Conversation sur '{self.product.name}' entre {self.client.username} et {self.merchant.user.username}"


# Le modèle Message
class Message(models.Model):
    """
    Représente un message individuel au sein d'une conversation.
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Ajout d'un champ pour identifier les messages générés par l'IA
    is_ai_response = models.BooleanField(default=False) 

    def __str__(self):
        return f"Message de {self.sender.username} dans la conversation {self.conversation.id}"



# Fichier : shop/models.py
# ... (tes autres modèles existants)
from decimal import Decimal

# Modèle pour les paramètres de négociation
class NegotiationSettings(models.Model):
    """
    Paramètres de l'IA de négociation pour une boutique.
    """
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='negotiation_settings')
    is_active = models.BooleanField(default=False)
    # Le prix minimum pour tous les produits de la boutique
    min_price_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    # La réduction maximale que l'IA peut offrir (en pourcentage)
    max_discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    
    def __str__(self):
        return f"Paramètres de négociation pour la boutique de {self.shop.merchant.user.username}"