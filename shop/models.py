# Fichier : shop/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
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
    
    # Nous allons remplacer la catégorie par un lien vers le nouveau modèle Category
    description = models.TextField(blank=True, null=True)
    
    image = models.ImageField(upload_to='shop_images/', blank=True, null=True)

    def __str__(self):
        return f"Boutique de {self.merchant}"

# NOUVEAU MODÈLE : Catégories pour la navigation hiérarchique
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True) # Utile pour les URLs
    
    class Meta:
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name

# NOUVEAU MODÈLE : Sous-catégories
class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    
    class Meta:
        verbose_name_plural = 'Subcategories'
        unique_together = ('category', 'name') # Assure que le nom est unique par catégorie
    
    def __str__(self):
        return f"{self.category.name} - {self.name}"

# Le modèle Product (Produit)
class Product(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    stock = models.IntegerField(default=0)
    
    # AJOUT : Lier le produit à une catégorie et une sous-catégorie
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')

    # AJOUT : Un champ pour les produits similaires (relation Many-to-Many)
    similar_products = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='recomended_by')

    def __str__(self):
        return self.name
        
# NOUVEAU MODÈLE : Variations de produits
class ProductVariation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations')
    type = models.CharField(max_length=50) # Ex: 'Couleur', 'Taille'
    value = models.CharField(max_length=50) # Ex: 'Bleu', 'XL'
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')) # Pour ajuster le prix
    stock_variation = models.IntegerField(default=0) # Stock pour cette variation
    
    def __str__(self):
        return f"{self.product.name} - {self.type}: {self.value}"

# NOUVEAU MODÈLE : Avis et évaluations
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)]) # Note de 1 à 5
    comment = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Avis de {self.user.username} sur {self.product.name}"

# Le modèle ProductImage
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')

    def __str__(self):
        return f"Image pour {self.product.name}"

# Le modèle ProductVideo
class ProductVideo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='videos')
    video = models.FileField(upload_to='product_videos/')

    def __str__(self):
        return f"Vidéo pour {self.product.name}"

# Le modèle Cart (Panier)
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Panier de {self.user.username}" if self.user else f"Panier #{self.id}"

# Le modèle CartItem (Article du Panier)
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} de {self.product.name}"
    
    @property
    def get_total(self):
        return self.product.price * self.quantity

# Le modèle Order (Commande)
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_ordered = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=100, null=True)
    # AJOUT : Informations de livraison
    full_name = models.CharField(max_length=200, null=True)
    email = models.EmailField(null=True)
    city = models.CharField(max_length=200, null=True)
    address = models.CharField(max_length=200, null=True)
    zipcode = models.CharField(max_length=200, null=True)

    def __str__(self):
        return str(self.id)
    
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

# Le modèle OrderItem (Article de la commande)
class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=0, null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    @property
    def get_total(self):
        return self.product.price * self.quantity

# Le modèle Conversation
class Conversation(models.Model):
    """
    Représente une conversation de négociation entre un client et un commerçant.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_conversations')
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='merchant_conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'client') # Un seul chat par client et par produit

    def __str__(self):
        return f"Conversation sur {self.product.name} entre {self.client.username} et {self.merchant.user.username}"

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
        return f"Paramètres de négociation pour {self.shop}"

# Ajoutez ceci à votre fichier models.py

class HeroSlide(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='hero_slides/')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, 
                               help_text="Produit à mettre en avant (optionnel)")
    external_url = models.URLField(blank=True, null=True, help_text="URL externe (optionnel)")
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Ordre d'affichage")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return self.title
    
    def get_target_url(self):
        if self.product:
            return reverse('product_detail', args=[self.product.id])
        elif self.external_url:
            return self.external_url
        return '#'