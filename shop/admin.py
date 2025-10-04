# Fichier : shop/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import (
    Merchant, Shop, Category, SubCategory, Product, ProductVariation,
    Review, ProductImage, ProductVideo, Cart, CartItem, Order, OrderItem,
    Conversation, Message, NegotiationSettings, HeroSlide, Client,
    VariationGroup, VariationOption, CartItemVariation, OrderItemVariation
)

# Admin pour Merchant
@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'email', 'phone', 'country')
    list_filter = ('country',)
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('user',)

# Admin pour Client
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'email', 'phone', 'date_created')
    list_filter = ('date_created', 'country')
    search_fields = ('first_name', 'last_name', 'email', 'phone')

# Admin pour Shop
@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('merchant', 'description_preview', 'image_preview')
    list_filter = ('merchant__country',)
    search_fields = ('merchant__first_name', 'merchant__last_name', 'description')
    
    def description_preview(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else obj.description
    description_preview.short_description = 'Description'
    
    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" style="width: 50px; height: 50px; object-fit: cover;" />'
        return "Aucune image"
    image_preview.allow_tags = True
    image_preview.short_description = 'Image'

# Admin pour Category
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'product_count')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Nombre de produits'

# Admin pour SubCategory
@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'slug', 'product_count')
    list_filter = ('category',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'category__name')
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Nombre de produits'

# Inline pour ProductImage
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'image_preview')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" style="width: 100px; height: 100px; object-fit: cover;" />'
        return "Aucune image"
    image_preview.allow_tags = True
    image_preview.short_description = 'Aperçu'

# Inline pour ProductVideo
class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 1
    fields = ('video',)

# Inline pour ProductVariation
class ProductVariationInline(admin.TabularInline):
    model = ProductVariation
    extra = 1
    fields = ('type', 'value', 'price_modifier', 'stock_variation', 'image', 'is_active', 'sku')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" style="width: 50px; height: 50px; object-fit: cover;" />'
        return "Aucune image"
    image_preview.allow_tags = True
    image_preview.short_description = 'Aperçu'

# Inline pour Review
class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ('user', 'rating', 'comment', 'date_created')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

# Admin pour ProductVariation
@admin.register(ProductVariation)
class ProductVariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'type', 'value', 'price_modifier', 'stock_variation', 'is_active')
    list_filter = ('type', 'is_active', 'product__shop')
    search_fields = ('product__name', 'type', 'value')
    list_editable = ('price_modifier', 'stock_variation', 'is_active')

# Admin pour Product
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'price', 'category', 'subcategory', 'stock', 'date_added', 'has_variations')
    list_filter = ('category', 'subcategory', 'shop', 'date_added')
    search_fields = ('name', 'description', 'shop__merchant__first_name')
    list_editable = ('price', 'stock')
    inlines = [ProductImageInline, ProductVideoInline, ProductVariationInline, ReviewInline]
    filter_horizontal = ('similar_products',)
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'shop', 'price', 'description', 'stock')
        }),
        ('Catégorisation', {
            'fields': ('category', 'subcategory')
        }),
        ('Produits similaires', {
            'fields': ('similar_products',),
            'classes': ('collapse',)
        }),
    )
    
    def has_variations(self, obj):
        return obj.variations.exists()
    has_variations.boolean = True
    has_variations.short_description = 'A des variations'

# Admin pour Review
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'date_created', 'comment_preview')
    list_filter = ('rating', 'date_created')
    search_fields = ('product__name', 'user__username', 'comment')
    readonly_fields = ('date_created',)
    
    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if obj.comment and len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Commentaire'

# Inline pour CartItemVariation
class CartItemVariationInline(admin.TabularInline):
    model = CartItemVariation
    extra = 1

# Inline pour CartItem
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'get_total', 'selected_variations_display')
    inlines = [CartItemVariationInline]
    
    def get_total(self, obj):
        return obj.get_total
    get_total.short_description = 'Total'
    
    def selected_variations_display(self, obj):
        return ", ".join([f"{v.type}: {v.value}" for v in obj.selected_variations.all()])
    selected_variations_display.short_description = 'Variations'

# Admin pour Cart
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_created', 'item_count')
    list_filter = ('date_created',)
    search_fields = ('user__username',)
    inlines = [CartItemInline]
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Nombre d\'articles'

# Inline pour OrderItemVariation
class OrderItemVariationInline(admin.TabularInline):
    model = OrderItemVariation
    extra = 1

# Inline pour OrderItem
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'get_total', 'date_added', 'selected_variations_display')
    inlines = [OrderItemVariationInline]
    
    def get_total(self, obj):
        return obj.get_total
    get_total.short_description = 'Total'
    
    def selected_variations_display(self, obj):
        if obj.selected_variations.exists():
            return ", ".join([f"{v.type}: {v.value}" for v in obj.selected_variations.all()])
        elif obj.variations_data:
            variations = obj.variations_data.get('variations', [])
            return ", ".join([f"{v['type']}: {v['value']}" for v in variations])
        return "Aucune"
    selected_variations_display.short_description = 'Variations'

# Admin pour Order
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'date_ordered', 'complete', 'get_cart_total', 'get_cart_items')
    list_filter = ('complete', 'date_ordered')
    search_fields = ('user__username', 'transaction_id')
    readonly_fields = ('date_ordered', 'transaction_id')
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Informations de commande', {
            'fields': ('user', 'complete', 'transaction_id')
        }),
        ('Informations de livraison', {
            'fields': ('full_name', 'email', 'city', 'address', 'zipcode'),
            'classes': ('collapse',)
        }),
    )

# Admin pour OrderItem
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'order', 'quantity', 'get_total', 'date_added', 'variations_display')
    list_filter = ('date_added',)
    search_fields = ('product__name', 'order__id')
    readonly_fields = ('date_added', 'get_total')
    inlines = [OrderItemVariationInline]
    
    def get_total(self, obj):
        return obj.get_total
    get_total.short_description = 'Total'
    
    def variations_display(self, obj):
        if obj.selected_variations.exists():
            return ", ".join([f"{v.type}: {v.value}" for v in obj.selected_variations.all()])
        elif obj.variations_data:
            variations = obj.variations_data.get('variations', [])
            return ", ".join([f"{v['type']}: {v['value']}" for v in variations])
        return "Aucune"
    variations_display.short_description = 'Variations'

# Inline pour Message
class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'text', 'timestamp', 'is_ai_response')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

# Admin pour Conversation
@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('product', 'client', 'merchant', 'created_at', 'message_count')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'client__username', 'merchant__user__username')
    readonly_fields = ('created_at',)
    inlines = [MessageInline]
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Nombre de messages'

# Admin pour Message
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'timestamp', 'is_ai_response', 'text_preview')
    list_filter = ('timestamp', 'is_ai_response')
    search_fields = ('conversation__product__name', 'sender__username', 'text')
    readonly_fields = ('timestamp',)
    
    def text_preview(self, obj):
        return obj.text[:50] + '...' if obj.text and len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Message'

# Admin pour NegotiationSettings
@admin.register(NegotiationSettings)
class NegotiationSettingsAdmin(admin.ModelAdmin):
    list_display = ('shop', 'is_active', 'min_price_threshold', 'max_discount_percentage')
    list_filter = ('is_active',)
    search_fields = ('shop__merchant__first_name', 'shop__merchant__last_name')
    list_editable = ('is_active', 'min_price_threshold', 'max_discount_percentage')

# Admin pour VariationGroup
@admin.register(VariationGroup)
class VariationGroupAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'is_required', 'options_count')
    list_filter = ('is_required', 'product__shop')
    search_fields = ('product__name', 'name')
    
    def options_count(self, obj):
        return obj.options.count()
    options_count.short_description = "Nombre d'options"

# Admin pour VariationOption
@admin.register(VariationOption)
class VariationOptionAdmin(admin.ModelAdmin):
    list_display = ('variation_group', 'variation', 'order')
    list_filter = ('variation_group',)
    search_fields = ('variation_group__name', 'variation__value')

# Admin pour HeroSlide
@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'is_active', 'order', 'created_at')
    list_filter = ('is_active', 'created_at')
    list_editable = ('is_active', 'order')
    search_fields = ('title', 'subtitle', 'product__name')
    
    fieldsets = (
        ('Contenu', {
            'fields': ('title', 'subtitle', 'image')
        }),
        ('Lien', {
            'fields': ('product', 'external_url'),
            'description': 'Choisissez soit un produit, soit une URL externe, ou laissez vide'
        }),
        ('Paramètres', {
            'fields': ('is_active', 'order')
        }),
    )

# Optionnel : Personnaliser l'admin de User pour inclure des infos Merchant
class MerchantInline(admin.StackedInline):
    model = Merchant
    can_delete = False
    verbose_name_plural = 'Informations du commerçant'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = (MerchantInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_merchant')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    
    def is_merchant(self, obj):
        return hasattr(obj, 'merchant')
    is_merchant.boolean = True
    is_merchant.short_description = 'Commerçant'

# Désenregistrer le User admin par défaut et réenregistrer avec le custom
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Personnalisation de l'interface d'administration
admin.site.site_header = "Administration DEANNA"
admin.site.site_title = "Plateforme DEANNA"
admin.site.index_title = "Gestion de la plateforme DEANNA"