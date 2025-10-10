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

class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    # Méthode pour vérifier facilement si un user est client
    @classmethod
    def is_client(cls, user):
        return hasattr(user, 'client')

# Le modèle Shop (Boutique)
class Shop(models.Model):
    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='shop_images/', blank=True, null=True)

    def __str__(self):
        return f"Boutique de {self.merchant}"

# Catégories pour la navigation hiérarchique
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True) # Utile pour les URLs
    
    class Meta:
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name

# Sous-catégories
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
    
    # Lier le produit à une catégorie et une sous-catégorie
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')

    # Produits similaires (relation Many-to-Many)
    similar_products = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='recomended_by')

    def __str__(self):
        return self.name

# Variations de produits
class ProductVariation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations')
    type = models.CharField(max_length=50) # Ex: 'Couleur', 'Taille'
    value = models.CharField(max_length=50) # Ex: 'Bleu', 'XL'
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')) # Pour ajuster le prix
    stock_variation = models.IntegerField(default=0) # Stock pour cette variation
    sku = models.CharField(max_length=100, blank=True, null=True) # Référence unique
    image = models.ImageField(upload_to='variation_images/', blank=True, null=True) # Image spécifique
    is_active = models.BooleanField(default=True) # Est-ce que cette variation est disponible ?
    
    class Meta:
        unique_together = ('product', 'type', 'value') # Évite les doublons
    
    def __str__(self):
        return f"{self.product.name} - {self.type}: {self.value}"
    
    # Prix calculé avec le modificateur
    @property
    def calculated_price(self):
        return self.product.price + self.price_modifier
    
    # Stock total (produit + variation)
    @property
    def total_stock(self):
        return self.product.stock + self.stock_variation

# Groupe de variations
class VariationGroup(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variation_groups')
    name = models.CharField(max_length=100) # Ex: "Couleur et Taille"
    is_required = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"

# Option de variation dans un groupe
class VariationOption(models.Model):
    variation_group = models.ForeignKey(VariationGroup, on_delete=models.CASCADE, related_name='options')
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE)
    order = models.IntegerField(default=0) # Pour l'ordre d'affichage
    
    class Meta:
        ordering = ['order']
        unique_together = ('variation_group', 'variation')
    
    def __str__(self):
        return f"{self.variation_group.name} - {self.variation.value}"

# Modèle intermédiaire pour CartItem et ProductVariation
class CartItemVariation(models.Model):
    cart_item = models.ForeignKey('CartItem', on_delete=models.CASCADE)
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('cart_item', 'variation')

# Modèle intermédiaire pour OrderItem et ProductVariation
class OrderItemVariation(models.Model):
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE)
    variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('order_item', 'variation')

# Avis et évaluations
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
    
    # Référence aux variations sélectionnées via le modèle intermédiaire
    selected_variations = models.ManyToManyField(ProductVariation, through=CartItemVariation, blank=True)

    def __str__(self):
        variations_str = ", ".join([f"{v.type}: {v.value}" for v in self.selected_variations.all()])
        return f"{self.quantity} x {self.product.name}" + (f" ({variations_str})" if variations_str else "")
    
    @property
    def get_total(self):
        base_price = self.product.price
        # Ajouter le prix des variations sélectionnées
        variation_price = sum([v.price_modifier for v in self.selected_variations.all()])
        return (base_price + variation_price) * self.quantity
    
    # Méthode pour obtenir la clé unique du panier
    @property
    def cart_key(self):
        variations = sorted([f"{v.type}_{v.value}" for v in self.selected_variations.all()])
        return f"{self.product.id}_{'_'.join(variations)}"

# Le modèle Order (Commande)
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_ordered = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=100, null=True)
    # Informations de livraison
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
    
    # Stocker les variations sélectionnées via le modèle intermédiaire
    selected_variations = models.ManyToManyField(ProductVariation, through=OrderItemVariation, blank=True)
    variations_data = models.JSONField(default=dict, blank=True) # Backup des données de variation

    @property
    def get_total(self):
        base_price = self.product.price if self.product else 0
        variation_price = 0
        for variation in self.selected_variations.all():
            variation_price += variation.price_modifier
        return (base_price + variation_price) * self.quantity
    
    # Sauvegarder les données de variation
    def save(self, *args, **kwargs):
        if self.pk:  # Si l'instance existe déjà
            # Sauvegarder les données de variation dans le JSON
            self.variations_data = {
                'variations': [
                    {
                        'type': v.type,
                        'value': v.value,
                        'price_modifier': str(v.price_modifier)
                    } 
                    for v in self.selected_variations.all()
                ]
            }
        super().save(*args, **kwargs)

    def __str__(self):
        variations_str = ", ".join([f"{v.type}: {v.value}" for v in self.selected_variations.all()])
        return f"{self.quantity} x {self.product.name if self.product else 'Produit supprimé'}" + (f" ({variations_str})" if variations_str else "")

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
    
    # Champ pour identifier les messages générés par l'IA
    is_ai_response = models.BooleanField(default=False) 

    def __str__(self):
        return f"Message de {self.sender.username} dans la conversation {self.conversation.id}"

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

class ShopSettings(models.Model):
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE)
    is_public = models.BooleanField(default=True, help_text="Rendre la boutique visible au public")
    shareable_link_slug = models.SlugField(max_length=50, unique=True, blank=True, null=True,
                                         help_text="Nom personnalisé pour le lien de la boutique (ex: 'boutique-de-jane'). Laissez vide pour utiliser le nom d'utilisateur.")
    
    def __str__(self):
        return f"Paramètres de {self.shop.merchant.user.username}"

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
    

## Dans models.py, ajoutez cette classe
# models.py - Ajoutez cette classe
class MerchantActivity(models.Model):
    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name='activity')
    last_seen = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)
    is_active_in_chat = models.BooleanField(default=False)  # Spécifique aux conversations
    current_session_key = models.CharField(max_length=40, blank=True, null=True)
    
    class Meta:
        verbose_name = "Activité du commerçant"
        verbose_name_plural = "Activités des commerçants"
    
    def __str__(self):
        status = "En ligne" if self.is_online else "Hors ligne"
        return f"{self.merchant} - {status}"
    
    @property
    def minutes_since_last_seen(self):
        from django.utils import timezone
        if self.last_seen:
            return (timezone.now() - self.last_seen).total_seconds() / 60
        return 999  # Très grand nombre si jamais vu
    
    @classmethod
    def update_activity(cls, merchant, session_key=None):
        """Met à jour l'activité d'un commerçant"""
        activity, created = cls.objects.get_or_create(merchant=merchant)
        activity.last_seen = timezone.now()
        activity.is_online = True
        
        if session_key:
            activity.current_session_key = session_key
            
        # Si c'est une nouvelle session, on met à jour last_login
        if created or not activity.is_online:
            activity.last_login = timezone.now()
            
        activity.save()
        return activity