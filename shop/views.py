# Fichier : shop/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product, Conversation, Message, Merchant, HeroSlide, Client
from django.http import JsonResponse, HttpResponseForbidden
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Sum, F, Avg, Q
from .models import Merchant, Shop, Product, ProductImage, ProductVideo, Cart, CartItem, Order, OrderItem, Category, SubCategory, Review, NegotiationSettings, ShopSettings, Client, ProductVariation, VariationOption,VariationGroup
from django.core.files.storage import FileSystemStorage
from decimal import Decimal, InvalidOperation
import json
from datetime import date, timedelta
from django.views.decorators.http import require_POST
from django.db.models.functions import TruncDay
from django.core.paginator import Paginator
import logging
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
import re

# Configuration du logger
logger = logging.getLogger(__name__)

# Fonctions utilitaires pour vérifier le type d'utilisateur
def is_merchant(user):
    return user.is_authenticated and hasattr(user, 'merchant')

def is_client(user):
    return user.is_authenticated and hasattr(user, 'client')

def get_user_type(user):
    if is_merchant(user):
        return 'merchant'
    elif is_client(user):
        return 'client'
    return 'anonymous'

# Décorateurs personnalisés
def client_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not is_client(request.user):
            return HttpResponseForbidden("Accès réservé aux clients")
        return view_func(request, *args, **kwargs)
    return wrapper

def merchant_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not is_merchant(request.user):
            return HttpResponseForbidden("Accès réservé aux commerçants")
        return view_func(request, *args, **kwargs)
    return wrapper

# VUES EXISTANTES
def index(request):
    return render(request, 'index.html')

def create_shop(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        country = request.POST.get('country')
        description = request.POST.get('description')
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            user = User.objects.create_user(username=username, password=password)
            merchant = Merchant.objects.create(
                user=user, 
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                country=country
            )
            shop = Shop.objects.create(merchant=merchant, description=description)
            
            # Gestion de l'image de la boutique
            shop_image = request.FILES.get('image')
            if shop_image:
                fs = FileSystemStorage()
                filename = fs.save(f'shop_images/{shop_image.name}', shop_image)
                shop.image = filename
                shop.save()
            
            # Redirige vers la page de connexion
            return redirect('login_view')
        except IntegrityError:
            # Gère les cas où l'utilisateur ou le commerçant existe déjà
            return render(request, 'create_shop.html', {'error': 'Nom d\'utilisateur ou email déjà utilisé.'})
            
    return render(request, 'create_shop.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Rediriger vers le tableau de bord approprié
            if hasattr(user, 'merchant'):
                return redirect('dashboard')
            elif hasattr(user, 'client'):
                return redirect('client_dashboard')
            else:
                return redirect('index')
        else:
            # Si l'authentification échoue
            return render(request, 'login.html', {'error': 'Nom d\'utilisateur ou mot de passe incorrect.'})
    return render(request, 'login.html')

@login_required(login_url='login_view')
def logout_view(request):
    logout(request)
    return redirect('index')

@login_required(login_url='login_view')
def dashboard(request):
    try:
        # Vérifie si l'utilisateur est un commerçant
        merchant = request.user.merchant
        shop = merchant.shop
        
        # Récupère les statistiques
        total_products = Product.objects.filter(shop=shop).count()
        total_orders = Order.objects.filter(orderitem__product__shop=shop).distinct().count()
        
        # Calcul du revenu total
        order_items = OrderItem.objects.filter(product__shop=shop, order__complete=True)
        total_revenue = order_items.aggregate(
            total=Sum(F('product__price') * F('quantity'))
        )['total'] or 0
        
        # Données pour les graphiques (exemple des 7 derniers jours)
        from django.db.models.functions import TruncDay
        from django.utils import timezone
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)
        
        revenue_data = (
            OrderItem.objects.filter(
                product__shop=shop,
                order__complete=True,
                date_added__gte=start_date
            )
            .annotate(day=TruncDay('date_added'))
            .values('day')
            .annotate(revenue=Sum(F('product__price') * F('quantity')))
            .order_by('day')
        )
        
        # Convert datetime objects to strings for JSON serialization
        revenue_data_list = []
        for item in revenue_data:
            revenue_data_list.append({
                'day': item['day'].strftime('%Y-%m-%d'),  # Convert to string
                'revenue': float(item['revenue']) if item['revenue'] else 0.0
            })
        
        # Produits les plus vendus
        top_products = (
            OrderItem.objects.filter(product__shop=shop, order__complete=True)
            .values('product__name')
            .annotate(quantity=Sum('quantity'))
            .order_by('-quantity')[:5]
        )
        
        # Conversion en JSON pour le template
        revenue_data_json = json.dumps(revenue_data_list)
        top_products_data_json = json.dumps(list(top_products))
        
        context = {
            'is_merchant': True,
            'is_client': is_client(request.user),
            'user_type': get_user_type(request.user),
            'shop': shop,
            'total_products': total_products,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'revenue_data_json': revenue_data_json,
            'top_products_data_json': top_products_data_json
        }
        return render(request, 'dashboard.html', context)
        
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        # Si ce n'est pas un commerçant ou n'a pas de boutique
        context = {
            'is_merchant': False,
            'is_client': is_client(request.user),
            'user_type': get_user_type(request.user),
            'shop': None
        }
        return render(request, 'dashboard.html', context)
        
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        # Si ce n'est pas un commerçant ou n'a pas de boutique
        context = {
            'is_merchant': False,
            'is_client': is_client(request.user),
            'user_type': get_user_type(request.user),
            'shop': None
        }
        return render(request, 'dashboard.html', context)
    
# Fichier : shop/views.py - MODIFICATION de manage_products

@login_required(login_url='login_view')
@merchant_required
def manage_products(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
        products = Product.objects.filter(shop=shop).prefetch_related('variations')
        context = {
            'products': products,
            'is_merchant': True,
            'is_client': is_client(request.user),
            'user_type': get_user_type(request.user)
        }
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        return redirect('dashboard')
    
    return render(request, 'manage_products.html', context)

@login_required(login_url='login_view')
# Fichier : shop/views.py - MODIFICATION de add_product

@login_required(login_url='login_view')
@merchant_required
def add_product(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        return redirect('dashboard')

    categories = Category.objects.all()

    if request.method == 'POST':
        product_name = request.POST.get('name')
        product_price = request.POST.get('price')
        product_description = request.POST.get('description')
        product_stock = request.POST.get('stock')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        
        # Création du produit
        product = Product.objects.create(
            shop=shop,
            name=product_name,
            price=product_price,
            description=product_description,
            stock=product_stock,
            category_id=category_id,
            subcategory_id=subcategory_id
        )

        # Gestion des images
        images = request.FILES.getlist('images')
        for image_file in images:
            ProductImage.objects.create(product=product, image=image_file)

        # Gestion des vidéos
        videos = request.FILES.getlist('videos')
        for video_file in videos:
            ProductVideo.objects.create(product=product, video=video_file)

        # NOUVEAU : Gestion des variations
        variation_types = request.POST.getlist('variation_type[]')
        variation_values = request.POST.getlist('variation_value[]')
        variation_prices = request.POST.getlist('variation_price[]')
        variation_stocks = request.POST.getlist('variation_stock[]')
        variation_skus = request.POST.getlist('variation_sku[]')
        variation_images = request.FILES.getlist('variation_image[]')

        # Créer les variations
        for i in range(len(variation_types)):
            if variation_types[i] and variation_values[i]:  # S'assurer que les champs requis sont remplis
                variation = ProductVariation.objects.create(
                    product=product,
                    type=variation_types[i],
                    value=variation_values[i],
                    price_modifier=variation_prices[i] if i < len(variation_prices) else 0,
                    stock_variation=variation_stocks[i] if i < len(variation_stocks) else 0,
                    sku=variation_skus[i] if i < len(variation_skus) else ''
                )
                
                # Gérer l'image de variation si fournie
                if i < len(variation_images) and variation_images[i]:
                    variation.image = variation_images[i]
                    variation.save()

        messages.success(request, 'Produit ajouté avec succès avec ses variations!')
        return redirect('manage_products')

    context = {
        'categories': categories,
        'is_merchant': True,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'add_product.html', context)

@login_required(login_url='login_view')
@merchant_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # S'assurer que l'utilisateur est le propriétaire de la boutique
    if request.user.merchant.shop != product.shop:
        return redirect('manage_products')
    
    categories = Category.objects.all()
    
    # NOUVEAU : Récupérer les variations existantes
    existing_variations = product.variations.all()

    if request.method == 'POST':
        try:
            # Mettre à jour les informations de base du produit
            product.name = request.POST.get('name')
            product.price = Decimal(request.POST.get('price'))
            product.description = request.POST.get('description')
            product.stock = int(request.POST.get('stock'))
            
            # Mise à jour des catégories
            category_id = request.POST.get('category')
            subcategory_id = request.POST.get('subcategory')
            product.category = get_object_or_404(Category, id=category_id) if category_id else None
            product.subcategory = get_object_or_404(SubCategory, id=subcategory_id) if subcategory_id else None
            
            product.save()

            # Gestion des images existantes
            keep_images = request.POST.getlist('keep_images')
            # Supprimer les images non conservées
            for image in product.images.all():
                if str(image.id) not in keep_images:
                    image.delete()
            
            # Ajouter de nouvelles images
            new_images = request.FILES.getlist('new_images')
            for image_file in new_images:
                ProductImage.objects.create(product=product, image=image_file)

            # Gestion des vidéos existantes
            keep_videos = request.POST.getlist('keep_videos')
            for video in product.videos.all():
                if str(video.id) not in keep_videos:
                    video.delete()
            
            # Ajouter de nouvelles vidéos
            new_videos = request.FILES.getlist('new_videos')
            for video_file in new_videos:
                ProductVideo.objects.create(product=product, video=video_file)

            # NOUVEAU : Gestion des variations existantes
            existing_variation_ids = request.POST.getlist('existing_variation_id[]')
            existing_variation_types = request.POST.getlist('existing_variation_type[]')
            existing_variation_values = request.POST.getlist('existing_variation_value[]')
            existing_variation_prices = request.POST.getlist('existing_variation_price[]')
            existing_variation_stocks = request.POST.getlist('existing_variation_stock[]')
            existing_variation_skus = request.POST.getlist('existing_variation_sku[]')
            existing_variation_images = request.FILES.getlist('existing_variation_image[]')

            # Mettre à jour les variations existantes
            for i, variation_id in enumerate(existing_variation_ids):
                try:
                    variation = ProductVariation.objects.get(id=variation_id, product=product)
                    variation.type = existing_variation_types[i]
                    variation.value = existing_variation_values[i]
                    variation.price_modifier = existing_variation_prices[i] if i < len(existing_variation_prices) else 0
                    variation.stock_variation = existing_variation_stocks[i] if i < len(existing_variation_stocks) else 0
                    variation.sku = existing_variation_skus[i] if i < len(existing_variation_skus) else ''
                    
                    # Gérer l'image de variation
                    if i < len(existing_variation_images) and existing_variation_images[i]:
                        variation.image = existing_variation_images[i]
                    
                    variation.save()
                except ProductVariation.DoesNotExist:
                    continue

            # NOUVEAU : Ajouter de nouvelles variations
            new_variation_types = request.POST.getlist('new_variation_type[]')
            new_variation_values = request.POST.getlist('new_variation_value[]')
            new_variation_prices = request.POST.getlist('new_variation_price[]')
            new_variation_stocks = request.POST.getlist('new_variation_stock[]')
            new_variation_skus = request.POST.getlist('new_variation_sku[]')
            new_variation_images = request.FILES.getlist('new_variation_image[]')

            for i in range(len(new_variation_types)):
                if new_variation_types[i] and new_variation_values[i]:
                    variation = ProductVariation.objects.create(
                        product=product,
                        type=new_variation_types[i],
                        value=new_variation_values[i],
                        price_modifier=new_variation_prices[i] if i < len(new_variation_prices) else 0,
                        stock_variation=new_variation_stocks[i] if i < len(new_variation_stocks) else 0,
                        sku=new_variation_skus[i] if i < len(new_variation_skus) else ''
                    )
                    
                    if i < len(new_variation_images) and new_variation_images[i]:
                        variation.image = new_variation_images[i]
                        variation.save()

            # NOUVEAU : Supprimer les variations non présentes dans le formulaire
            submitted_variation_ids = [int(vid) for vid in existing_variation_ids if vid]
            for variation in existing_variations:
                if variation.id not in submitted_variation_ids:
                    variation.delete()

            messages.success(request, 'Produit mis à jour avec succès!')
            return redirect('manage_products')

        except (Merchant.DoesNotExist, InvalidOperation) as e:
            messages.error(request, f'Erreur lors de la mise à jour: {str(e)}')
            return redirect('edit_product', product_id=product_id)
    
    context = {
        'product': product,
        'categories': categories,
        'existing_variations': existing_variations,  # NOUVEAU
        'is_merchant': True,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'edit_product.html', context)
    
    # Récupère les catégories et sous-catégories pour le formulaire
    categories = Category.objects.all()
    context = {
        'product': product,
        'categories': categories,
        'is_merchant': True,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'edit_product.html', context)

@login_required(login_url='login_view')
@merchant_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.merchant.shop != product.shop:
            return redirect('manage_products')
        product.delete()
    except Merchant.DoesNotExist:
        pass
    return redirect('manage_products')

@login_required(login_url='login_view')
@merchant_required
def manage_orders(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
        orders = Order.objects.filter(orderitem__product__shop=shop).distinct().order_by('-date_ordered')
        context = {
            'orders': orders,
            'is_merchant': True,
            'is_client': is_client(request.user),
            'user_type': get_user_type(request.user)
        }
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        return redirect('dashboard')
    return render(request, 'manage_orders.html', context)

@login_required(login_url='login_view')
@merchant_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    # Vérifie si le commerçant a un produit dans la commande
    is_merchant_for_order = order.orderitem_set.filter(product__shop__merchant=request.user.merchant).exists()
    
    if not is_merchant_for_order:
        return redirect('dashboard')
        
    context = {
        'order': order,
        'is_merchant': True,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'order_detail.html', context)

@login_required(login_url='login_view')
@merchant_required
def manage_shop(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
        # Récupère ou crée les paramètres de la boutique
        shop_settings, created = ShopSettings.objects.get_or_create(shop=shop)

        # Gère la logique de la méthode POST pour la mise à jour des paramètres
        if request.method == 'POST':
            description = request.POST.get('description')
            image = request.FILES.get('image')
            is_public = request.POST.get('is_public') == 'on'
            shareable_link_slug = request.POST.get('shareable_link_slug')
            
            # Mise à jour des champs du modèle Shop
            shop.description = description
            if image:
                shop.image = image
            shop.save()
            
            # Mise à jour des champs du modèle ShopSettings
            shop_settings.is_public = is_public
            shop_settings.shareable_link_slug = shareable_link_slug
            shop_settings.save()
            
            messages.success(request, 'Les paramètres de votre boutique ont été mis à jour avec succès!')
            return redirect('manage_shop')

        # Génère le lien de partage
        if shop_settings.shareable_link_slug:
            shop_slug = shop_settings.shareable_link_slug
        else:
            shop_slug = request.user.username
        
        # CORRECTION ICI: Utilisez 'shop_detail_by_slug' au lieu de 'shop_detail'
        shop_link = request.build_absolute_uri(reverse('shop_detail_by_slug', args=[shop_slug]))
        
        context = {
            'shop': shop,
            'shop_settings': shop_settings,
            'shop_link': shop_link,
            'is_merchant': True,
            'is_client': is_client(request.user),
            'user_type': get_user_type(request.user)
        }
    except Merchant.DoesNotExist:
        return redirect('dashboard')
        
    return render(request, 'manage_shop.html', context)

@login_required(login_url='login_view')
@merchant_required
def configure_negotiation(request):
    try:
        merchant = request.user.merchant
        settings, created = NegotiationSettings.objects.get_or_create(shop=merchant.shop)
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        return redirect('dashboard')

    if request.method == 'POST':
        settings.is_active = request.POST.get('is_active') == 'on'
        settings.min_price_threshold = request.POST.get('min_price_threshold')
        settings.max_discount_percentage = request.POST.get('max_discount_percentage')
        settings.save()
        return redirect('configure_negotiation')

    context = {
        'settings': settings,
        'is_merchant': True,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'configure_negotiation.html', context)

def product_search_list(request):
    query = request.GET.get('q')
    products = Product.objects.all()
    
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'product_search_list.html', context)

# NOUVELLES FONCTIONNALITÉS : Vues pour la navigation et la recherche de produits
def visit_shops(request):
    """
    Vue qui liste toutes les boutiques publiques.
    """
    shops = Shop.objects.filter(shopsettings__is_public=True)
    context = {
        'shops': shops,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'visit_shops.html', context)

# MODIFICATION de product_detail pour inclure les variations organisées
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Récupération des avis et de la note moyenne
    reviews = Review.objects.filter(product=product).order_by('-date_created')
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    
    # Récupération des produits similaires
    similar_products = product.similar_products.all()
    
    # NOUVEAU : Récupération organisée des variations actives
    variations_by_type = {}
    for variation in product.variations.filter(is_active=True):
        if variation.type not in variations_by_type:
            variations_by_type[variation.type] = []
        variations_by_type[variation.type].append(variation)
    
    # Vérifier si la catégorie et le slug existent
    has_valid_category = product.category and product.category.slug
    has_valid_subcategory = product.subcategory and product.subcategory.slug
    
    context = {
        'product': product,
        'reviews': reviews,
        'average_rating': average_rating,
        'similar_products': similar_products,
        'variations_by_type': variations_by_type,  # NOUVEAU
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user),
        'has_valid_category': has_valid_category,
        'has_valid_subcategory': has_valid_subcategory
    }
    return render(request, 'product_detail.html', context)

@login_required(login_url='login_view')
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # S'assure que l'utilisateur n'est pas le commerçant de la boutique
    if is_merchant(request.user) and request.user.merchant.shop == product.shop:
        return redirect('product_detail', product_id=product_id)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        # Création de l'avis
        if rating and request.user.is_authenticated:
            Review.objects.create(
                product=product,
                user=request.user,
                rating=rating,
                comment=comment
            )
            return redirect('product_detail', product_id=product_id)
    
    return redirect('product_detail', product_id=product_id)

def product_list(request):
    # Récupération de tous les produits, puis application des filtres
    products = Product.objects.all().order_by('name')
    categories = Category.objects.all()
    
    # Récupérer les slides hero actifs
    hero_slides = HeroSlide.objects.filter(is_active=True).order_by('order')[:5]
    
    # 1. Filtre par recherche (champ 'q')
    query = request.GET.get('q')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    # 2. Filtre par prix
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except (InvalidOperation, ValueError):
            pass
    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except (InvalidOperation, ValueError):
            pass

    # 3. Filtre par note moyenne (rating)
    min_rating = request.GET.get('min_rating')
    if min_rating:
        products = products.annotate(avg_rating=Avg('reviews__rating')).filter(avg_rating__gte=int(min_rating))

    # 4. Filtre par catégorie (la vue est réutilisée)
    category_slug = request.GET.get('category_slug')
    if category_slug:
        products = products.filter(category__slug=category_slug)
        
    # 5. Trie
    sort_by = request.GET.get('sort_by')
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'rating_desc':
        products = products.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
        
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'hero_slides': hero_slides,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user),
    }
    return render(request, 'product_list.html', context)

# Vue pour les produits par catégorie
def products_by_category(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug)
    # Réutilisation de la vue product_list avec le filtre de catégorie
    return product_list(request, category_slug=category_slug)

# Vue pour les produits par sous-catégorie
def products_by_subcategory(request, category_slug, subcategory_slug):
    subcategory = get_object_or_404(SubCategory, slug=subcategory_slug)
    products = Product.objects.filter(subcategory=subcategory).order_by('name')
    categories = Category.objects.all()
    
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user),
        'current_category': subcategory.category,
        'current_subcategory': subcategory,
    }
    return render(request, 'product_list.html', context)

# Vue pour la recherche de produits
def product_search(request):
    return product_list(request)

@login_required(login_url='login_view')
def cart_detail(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
        
    context = {
        'cart': cart, 
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'cart_detail.html', context)


@login_required(login_url='login_view')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # NOUVEAU : Récupérer les variations sélectionnées
    selected_variation_ids = request.POST.getlist('variations')
    selected_variations = ProductVariation.objects.filter(id__in=selected_variation_ids)
    
    # NOUVEAU : Vérifier la disponibilité des variations
    for variation in selected_variations:
        if variation.total_stock <= 0:
            messages.error(request, f"La variation {variation.type}: {variation.value} n'est plus en stock.")
            return redirect('product_detail', product_id=product_id)
    
    # NOUVEAU : Créer une clé unique pour cet article avec ses variations
    variation_keys = sorted([f"{v.id}" for v in selected_variations])
    cart_key = f"{product_id}_{'_'.join(variation_keys)}"
    
    # NOUVEAU : Vérifier si l'article avec ces variations existe déjà
    existing_item = None
    for item in cart.items.all():
        item_variation_keys = sorted([f"{v.id}" for v in item.selected_variations.all()])
        item_key = f"{item.product.id}_{'_'.join(item_variation_keys)}"
        if item_key == cart_key:
            existing_item = item
            break
    
    if existing_item:
        # Incrémenter la quantité si l'article existe déjà
        existing_item.quantity += 1
        existing_item.save()
    else:
        # Créer un nouvel article
        cart_item = CartItem.objects.create(cart=cart, product=product, quantity=1)
        cart_item.selected_variations.set(selected_variations)
        cart_item.save()
    
    messages.success(request, "Produit ajouté au panier avec succès!")
    return redirect('cart_detail')

# NOUVELLE VUE : API pour les variations
def get_product_variations(request, product_id):
    """API pour récupérer les variations d'un produit"""
    product = get_object_or_404(Product, id=product_id)
    
    # Organiser les variations par type
    variations_by_type = {}
    for variation in product.variations.filter(is_active=True):
        if variation.type not in variations_by_type:
            variations_by_type[variation.type] = []
        
        variations_by_type[variation.type].append({
            'id': variation.id,
            'value': variation.value,
            'price_modifier': str(variation.price_modifier),
            'image_url': variation.image.url if variation.image else None,
            'stock': variation.total_stock
        })
    
    return JsonResponse({
        'variations': variations_by_type,
        'base_price': str(product.price)
    })
    
@login_required(login_url='login_view')
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    return redirect('cart_detail')

@login_required(login_url='login_view')
def update_cart_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    if request.method == 'POST':
        new_quantity = int(request.POST.get('quantity', 1))
        if new_quantity > 0:
            item.quantity = new_quantity
            item.save()
        else:
            item.delete()
    return redirect('cart_detail')

@login_required(login_url='login_view')
def checkout_view(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        return redirect('cart_detail')
    
    # Calcule le total
    total = sum([item.get_total for item in cart.items.all()])
    
    # Vérifie si l'utilisateur a un panier avec des articles
    if not cart.items.exists():
        return redirect('cart_detail')
        
    context = {
        'cart': cart, 
        'total': total,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'checkout.html', context)

@login_required(login_url='login_view')
def process_order(request):
    if request.method == 'POST':
        cart = get_object_or_404(Cart, user=request.user)
        if not cart.items.exists():
            return redirect('cart_detail')
        
        # Récupère les informations du formulaire
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        city = request.POST.get('city')
        address = request.POST.get('address')
        zipcode = request.POST.get('zipcode')
        
        # Crée une nouvelle commande
        order = Order.objects.create(
            user=request.user, 
            complete=True,
            transaction_id=f"trans-{request.user.id}-{date.today().isoformat()}",
            full_name=full_name,
            email=email,
            city=city,
            address=address,
            zipcode=zipcode
        )
        
        # Déplace les articles du panier à la commande
        for item in cart.items.all():
            order_item = OrderItem.objects.create(
                product=item.product,
                order=order,
                quantity=item.quantity
            )
            # NOUVEAU : Copier les variations sélectionnées
            order_item.selected_variations.set(item.selected_variations.all())
            order_item.save()
            
            # Met à jour le stock du produit et des variations
            product = item.product
            product.stock -= item.quantity
            product.save()
            
            # NOUVEAU : Mettre à jour le stock des variations
            for variation in item.selected_variations.all():
                variation.stock_variation -= item.quantity
                variation.save()
            
        # Vide le panier
        cart.items.all().delete()
        
        return redirect('order_confirmation', order_id=order.id)
        
    return redirect('checkout_view')

@login_required(login_url='login_view')
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    context = {
        'order': order,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'order_confirmation.html', context)
    
@login_required(login_url='login_view')
def start_negotiation_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Si le client est aussi un commerçant et que le produit lui appartient, on redirige
    if is_merchant(request.user) and request.user.merchant.shop == product.shop:
        return redirect('product_detail', product_id=product_id)
        
    try:
        conversation = Conversation.objects.get(product=product, client=request.user)
        return redirect('conversation_detail', conversation_id=conversation.id)
    except Conversation.DoesNotExist:
        # Crée une nouvelle conversation si elle n'existe pas
        conversation = Conversation.objects.create(
            product=product,
            client=request.user,
            merchant=product.shop.merchant
        )
        return redirect('conversation_detail', conversation_id=conversation.id)

# views.py - CORRECTION de la partie IA dans conversation_detail_view

@login_required(login_url='login_view')
def conversation_detail_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Vérification des permissions
    is_user_merchant = is_merchant(request.user)
    if (is_user_merchant and conversation.merchant.user != request.user) or \
       (not is_user_merchant and conversation.client != request.user):
        return redirect('list_conversations')
    
    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        if not message_text:
            messages.error(request, 'Le message ne peut pas être vide.')
            return redirect('conversation_detail', conversation_id=conversation.id)

        # Création du message de l'utilisateur
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=message_text
        )

        # LOGIQUE IA AMÉLIORÉE
        if not is_user_merchant:  # Si c'est le client qui envoie un message
            try:
                from .services import get_ai_negotiation_response, should_use_ai
                
                # Vérifier si l'IA doit répondre
                if should_use_ai(conversation):
                    # Appel du service amélioré
                    ai_response_text = get_ai_negotiation_response(
                        conversation.product, 
                        message_text,
                        conversation
                    )
                    
                    # Si l'IA a généré une réponse, on la sauvegarde
                    if ai_response_text:
                        Message.objects.create(
                            conversation=conversation,
                            sender=conversation.merchant.user,
                            text=ai_response_text,
                            is_ai_response=True
                        )
                        logger.info(f"✅ Réponse IA envoyée pour la conversation {conversation.id}")
                    else:
                        logger.info(f"❌ Aucune réponse IA générée pour la conversation {conversation.id}")
                else:
                    logger.info(f"⏸️ IA non autorisée à répondre pour la conversation {conversation.id}")
                
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'appel à l'IA : {e}")
                # En cas d'erreur, on continue sans bloquer la conversation

        return redirect('conversation_detail', conversation_id=conversation.id)
    
    messages_list = conversation.messages.all().order_by('timestamp')
    
    # Ajout du statut IA dans le contexte pour l'affichage
    from .services import get_conversation_ai_status
    ai_status = get_conversation_ai_status(conversation)
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
        'product': conversation.product,
        'is_merchant': is_user_merchant,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user),
        'ai_status': ai_status,
    }
    return render(request, 'conversation_detail.html', context)
@login_required(login_url='login_view')
def chat_api(request, conversation_id):
    if request.method == 'POST':
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        is_user_merchant = is_merchant(request.user)
        # Vérifie que l'utilisateur est bien un participant de la conversation
        if (is_user_merchant and conversation.merchant.user != request.user) or (not is_user_merchant and conversation.client != request.user):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        try:
            data = json.loads(request.body)
            message_text = data.get('message', '').strip()
            
            if not message_text:
                return JsonResponse({'error': 'Message cannot be empty'}, status=400)
            
            # Sauvegarde le message
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                text=message_text
            )
            
            # Tente de générer une réponse de l'IA (si la négociation est active)
            response_text = ""
            if is_user_merchant:
                # C'est un commerçant qui envoie un message, l'IA ne répond pas
                pass
            else:
                # C'est un client qui envoie un message
                shop = conversation.merchant.shop
                settings_exist = NegotiationSettings.objects.filter(shop=shop, is_active=True).exists()

                if settings_exist and "proposition" in message_text.lower():
                    # Appelle le service d'IA pour obtenir une réponse
                    from .services import get_ai_negotiation_response
                    try:
                        # Extraire le prix proposé
                        price_match = re.search(r'(\d+(\.\d+)?)', message_text)
                        user_price_offer = Decimal(price_match.group(1)) if price_match else None
                        
                        if user_price_offer is not None:
                            ai_response_text = get_ai_negotiation_response(conversation.product, user_price_offer, conversation)
                            Message.objects.create(
                                conversation=conversation,
                                sender=conversation.merchant.user,
                                text=ai_response_text,
                                is_ai_response=True
                            )
                            response_text = ai_response_text

                    except Exception as e:
                        print(f"Erreur lors de l'appel à l'IA : {e}")
            
            return JsonResponse({'success': True, 'ai_response': response_text})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required(login_url='login_view')
def list_conversations_view(request):
    is_user_merchant = is_merchant(request.user)
    
    if is_user_merchant:
        # Si c'est un commerçant, on récupère les conversations de sa boutique
        conversations = Conversation.objects.filter(merchant=request.user.merchant)
    else:
        # Si c'est un client, on récupère ses conversations
        conversations = Conversation.objects.filter(client=request.user)
    
    context = {
        'conversations': conversations,
        'is_merchant': is_user_merchant,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'list_conversations.html', context)

@login_required(login_url='login_view')
def negotiation_chat(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Vérification des permissions
    is_user_merchant = is_merchant(request.user)
    if (is_user_merchant and conversation.merchant.user != request.user) or \
       (not is_user_merchant and conversation.client != request.user):
        return redirect('list_conversations')
    
    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        if not message_text:
            return JsonResponse({'error': 'Message vide.'}, status=400)

        # Création du message de l'utilisateur
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=message_text
        )

        # Logique pour déclencher l'IA si c'est le client qui a envoyé le message
        # et que le commerçant a activé la négociation IA.
        if not is_user_merchant:
            try:
                # Vérifie si le commerçant a activé la négociation IA
                negotiation_settings = NegotiationSettings.objects.get(shop=conversation.product.shop)
                if negotiation_settings.is_active:
                    
                    # Convertit le prix en Decimal
                    try:
                        user_price_offer = Decimal(message_text.replace(' CFA', ''))
                    except (InvalidOperation, ValueError):
                        user_price_offer = None
                    
                    # Si l'offre de prix est valide, appelle l'IA
                    if user_price_offer is not None:
                        ai_response_text = get_ai_negotiation_response(conversation.product, user_price_offer, conversation)
                        
                        # Crée un message pour la réponse de l'IA
                        Message.objects.create(
                            conversation=conversation,
                            sender=conversation.merchant.user,
                            text=ai_response_text,
                            is_ai_response=True
                        )
            except NegotiationSettings.DoesNotExist:
                logger.info("Les paramètres de négociation de l'IA n'existent pas pour cette boutique.")
            except Exception as e:
                logger.error(f"Erreur lors de l'appel à l'IA : {e}")

        # La réponse se fera via le rechargement de la page pour le moment
        return redirect('negotiation_chat', conversation_id=conversation.id)
    
    messages_list = conversation.messages.all().order_by('timestamp')
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
        'product': conversation.product,
        'is_merchant': is_user_merchant,
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user),
    }
    return render(request, 'conversation_detail.html', context)

# Vue pour la page de détail de la boutique
def shop_detail(request, shop_id):
    """
    Vue pour afficher les détails d'une boutique et ses produits.
    """
    # 1. Récupère la boutique ou renvoie une erreur 404 si elle n'existe pas
    shop = get_object_or_404(Shop, id=shop_id)
    
    # 2. Récupère tous les produits associés à cette boutique
    products = Product.objects.filter(shop=shop)
    
    # 3. Crée le dictionnaire de contexte à passer au template
    context = {
        'shop': shop,
        'products': products,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    
    # 4. Rend le template 'shop_detail.html' avec les données
    return render(request, 'shop_detail.html', context)

# Vue détaillée de la boutique
def shop_detail_by_slug(request, shop_slug):
    """Affiche la page d'accueil d'une boutique avec les produits en vedette."""
    shop = get_object_or_404(Shop, merchant__user__username=shop_slug)
    featured_products = Product.objects.filter(shop=shop, stock__gt=0)[:8]
    categories = Category.objects.filter(products__shop=shop).distinct()
    
    context = {
        'shop': shop,
        'featured_products': featured_products,
        'categories': categories,
        'is_shop_page': True,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'shop/shop_detail.html', context)

# Tous les produits de la boutique
def shop_products(request, shop_slug):
    """Affiche tous les produits d'une boutique, avec pagination et filtres."""
    shop = get_object_or_404(Shop, merchant__user__username=shop_slug)
    products = Product.objects.filter(shop=shop, stock__gt=0)
    
    # Filtres et pagination similaires à product_list
    query = request.GET.get('q')
    category_slug = request.GET.get('cat')
    subcategory_slug = request.GET.get('subcat')
    
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category_slug:
        products = products.filter(category__slug=category_slug)
    if subcategory_slug:
        products = products.filter(subcategory__slug=subcategory_slug)

    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.filter(products__shop=shop).distinct()
    
    context = {
        'shop': shop,
        'page_obj': page_obj,
        'categories': categories,
        'query': query,
        'is_shop_page': True,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'shop/shop_products.html', context)

# Produits par catégorie dans la boutique
def shop_category(request, shop_slug, category_slug):
    """Affiche les produits d'une boutique, filtrés par une catégorie spécifique."""
    shop = get_object_or_404(Shop, merchant__user__username=shop_slug)
    category = get_object_or_404(Category, slug=category_slug)
    products = Product.objects.filter(shop=shop, category=category, stock__gt=0)
    
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'shop': shop,
        'category': category,
        'page_obj': page_obj,
        'is_shop_page': True,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'shop/shop_category.html', context)

# Page contact de la boutique
def shop_contact(request, shop_slug):
    """Gère le formulaire de contact pour une boutique spécifique."""
    shop = get_object_or_404(Shop, merchant__user__username=shop_slug)
    
    if request.method == 'POST':
        # Gérer l'envoi du formulaire de contact
        # (L'envoi d'email au commerçant est à implémenter ici)
        
        messages.success(request, 'Votre message a été envoyé avec succès!')
        return redirect('shop_contact', shop_slug=shop_slug)
    
    context = {
        'shop': shop,
        'is_shop_page': True,
        'is_merchant': is_merchant(request.user),
        'is_client': is_client(request.user),
        'user_type': get_user_type(request.user)
    }
    return render(request, 'shop/shop_contact.html', context)

def shop_detail_by_slug(request, shop_slug):
    """Affiche la page d'accueil d'une boutique avec les produits en vedette."""
    try:
        # Essayer de trouver la boutique par le slug du lien partageable d'abord
        shop_settings = ShopSettings.objects.filter(shareable_link_slug=shop_slug).first()
        if shop_settings:
            shop = shop_settings.shop
        else:
            # Sinon, chercher par le nom d'utilisateur du marchand
            shop = get_object_or_404(Shop, merchant__user__username=shop_slug)
        
        # Vérifier que la boutique est publique
        if not shop.shopsettings.is_public:
            return render(request, 'shop/shop_private.html', {'shop': shop})
            
        featured_products = Product.objects.filter(shop=shop, stock__gt=0)[:8]
        categories = Category.objects.filter(products__shop=shop).distinct()
        
        context = {
            'shop': shop,
            'featured_products': featured_products,
            'categories': categories,
            'is_shop_page': True,
            'is_merchant': is_merchant(request.user),
            'is_client': is_client(request.user),
            'user_type': get_user_type(request.user)
        }
        return render(request, 'shop/shop_detail.html', context)
        
    except Shop.DoesNotExist:
        # Si la boutique n'existe pas, afficher une page 404 personnalisée
        return render(request, 'shop/shop_not_found.html', {'shop_slug': shop_slug})

# Création de compte client
def create_client(request):
    """Crée un nouvel utilisateur et un profil client."""
    if request.user.is_authenticated:
        return redirect('index')
        
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        username = request.POST.get('username')
        
        # Validation basique
        if not all([first_name, last_name, email, password, username]):
            return render(request, 'client/create_client.html', {
                'error': 'Tous les champs obligatoires doivent être remplis'
            })
        
        try:
            # Créer l'utilisateur
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            
            # Créer le client
            client = Client.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone
            )
            
            # Connecter automatiquement l'utilisateur
            login(request, user)
            messages.success(request, 'Votre compte client a été créé avec succès!')
            return redirect('client_dashboard')
            
        except IntegrityError:
            return render(request, 'client/create_client.html', {
                'error': 'Nom d\'utilisateur ou email déjà utilisé'
            })
        except Exception as e:
            # En cas d'autre erreur, supprimer l'utilisateur créé si nécessaire
            if 'user' in locals():
                user.delete()
            return render(request, 'client/create_client.html', {
                'error': f'Une erreur s\'est produite: {str(e)}'
            })
    
    return render(request, 'client/create_client.html')

@login_required
@client_required
def client_dashboard(request):
    """Tableau de bord pour les clients"""
    client = request.user.client
    orders = Order.objects.filter(user=request.user).order_by('-date_ordered')[:5]
    total_orders = Order.objects.filter(user=request.user).count()
    
    # Calculer le total des dépenses
    total_spent = Order.objects.filter(
        user=request.user, 
        complete=True
    ).aggregate(total=Sum(F('orderitem__product__price') * F('orderitem__quantity')))['total'] or 0
    
    context = {
        'client': client,
        'recent_orders': orders,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'is_client': True,
        'is_merchant': is_merchant(request.user),
        'user_type': 'client'
    }
    return render(request, 'client/dashboard.html', context)

@login_required
@client_required
def client_orders(request):
    """Historique des commandes du client"""
    orders = Order.objects.filter(user=request.user).order_by('-date_ordered')
    
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'is_client': True,
        'is_merchant': is_merchant(request.user),
        'user_type': 'client'
    }
    return render(request, 'client/orders.html', context)

@login_required
@client_required
def client_order_detail(request, order_id):
    """Détail d'une commande client"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    context = {
        'order': order,
        'is_client': True,
        'is_merchant': is_merchant(request.user),
        'user_type': 'client'
    }
    return render(request, 'client/order_detail.html', context)

@login_required
@client_required
def client_profile(request):
    """Profil du client avec possibilité de modification"""
    client = request.user.client
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        city = request.POST.get('city')
        country = request.POST.get('country')
        
        # Mettre à jour le user
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.email = email
        request.user.save()
        
        # Mettre à jour le client
        client.first_name = first_name
        client.last_name = last_name
        client.email = email
        client.phone = phone
        client.address = address
        client.city = city
        client.country = country
        client.save()
        
        messages.success(request, 'Votre profil a été mis à jour avec succès!')
        return redirect('client_profile')
    
    context = {
        'client': client,
        'is_client': True,
        'is_merchant': is_merchant(request.user),
        'user_type': 'client'
    }
    return render(request, 'client/profile.html', context)

# Fonction utilitaire pour l'IA de négociation (doit être implémentée)
def get_ai_negotiation_response(product, user_price_offer, conversation):
    """
    Fonction qui génère une réponse de négociation basée sur l'IA.
    À implémenter selon vos besoins spécifiques.
    """
    # Exemple simple de réponse
    if user_price_offer >= product.price * Decimal('0.8'):
        return f"J'accepte votre offre de {user_price_offer} CFA!"
    else:
        return f"Je ne peux pas accepter {user_price_offer} CFA. Mon prix minimum est {product.price * Decimal('0.8')} CFA."


@login_required
def merchant_status_api(request, merchant_id):
    """API pour obtenir le statut d'un commerçant"""
    merchant = get_object_or_404(Merchant, id=merchant_id)
    
    status = get_merchant_status(merchant)
    
    return JsonResponse({
        'merchant_id': merchant.id,
        'status': status,
        'is_online': status in ['en_ligne_actif', 'en_ligne_inactif'],
        'last_seen': merchant.activity.last_seen.isoformat() if hasattr(merchant, 'activity') else None
    })

@merchant_required
def my_status_api(request):
    """API pour que le commerçant voit son propre statut"""
    activity = get_object_or_404(MerchantActivity, merchant=request.user.merchant)
    
    return JsonResponse({
        'is_online': activity.is_online,
        'last_seen': activity.last_seen.isoformat(),
        'minutes_since_last_seen': activity.minutes_since_last_seen,
        'is_active_in_chat': activity.is_active_in_chat
    })


# views.py - AJOUTEZ cette vue pour tester l'IA

# Dans views.py
def test_ai_service(request):
    from .services import test_ai_connection, openrouter_client
    test_result = test_ai_connection()
    return JsonResponse(test_result)