from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import (
    Merchant, Shop, Product, ProductImage, ProductVideo, 
    Cart, CartItem, Order, OrderItem, 
    Conversation, Message, NegotiationSettings
)

# Register your models here.

@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'email', 'phone', 'country')
    list_filter = ('country',)
    search_fields = ('first_name', 'last_name', 'email', 'phone')

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('merchant', 'category')
    list_filter = ('category',)
    search_fields = ('merchant__first_name', 'merchant__last_name', 'category')

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'price', 'stock')
    list_filter = ('shop', 'stock')
    search_fields = ('name', 'description')
    inlines = [ProductImageInline, ProductVideoInline]

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_created')
    list_filter = ('date_created',)

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity')
    list_filter = ('cart',)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'date_ordered', 'complete', 'full_name', 'city')
    list_filter = ('complete', 'date_ordered', 'city')
    search_fields = ('user__username', 'full_name', 'transaction_id')
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'date_added')
    list_filter = ('date_added',)

class MessageInline(admin.TabularInline):
    model = Message
    extra = 1

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('product', 'client', 'merchant', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'client__username', 'merchant__user__username')
    inlines = [MessageInline]

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'timestamp', 'is_ai_response')
    list_filter = ('timestamp', 'is_ai_response')
    search_fields = ('conversation__product__name', 'sender__username', 'text')

@admin.register(NegotiationSettings)
class NegotiationSettingsAdmin(admin.ModelAdmin):
    list_display = ('shop', 'is_active', 'min_price_threshold', 'max_discount_percentage')
    list_filter = ('is_active',)
    search_fields = ('shop__merchant__user__username',)