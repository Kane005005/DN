# Fichier : shop/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product, Conversation, Message, Merchant,HeroSlide
from django.http import JsonResponse
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Sum, F, Avg, Q # AJOUT : Import d'Avg et Q pour la moyenne et la recherche
from .models import Merchant, Shop, Product, ProductImage, ProductVideo, Cart, CartItem, Order, OrderItem, Category, SubCategory, Review, NegotiationSettings
from django.core.files.storage import FileSystemStorage
from decimal import Decimal, InvalidOperation
import json
from datetime import date, timedelta
from django.views.decorators.http import require_POST
from django.db.models.functions import TruncDay
from django.core.paginator import Paginator # AJOUT : Pour la pagination

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
            return redirect('dashboard')
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
        
        # Produits les plus vendus
        top_products = (
            OrderItem.objects.filter(product__shop=shop, order__complete=True)
            .values('product__name')
            .annotate(quantity=Sum('quantity'))
            .order_by('-quantity')[:5]
        )
        
        # Conversion en JSON pour le template
        import json
        revenue_data_json = json.dumps(list(revenue_data))
        top_products_data_json = json.dumps(list(top_products))
        
        context = {
            'is_merchant': True,
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
            'shop': None
        }
        return render(request, 'dashboard.html', context)
    
@login_required(login_url='login_view')
def manage_products(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
        products = Product.objects.filter(shop=shop)
        context = {
            'products': products,
            'is_merchant': True
        }
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        return redirect('dashboard')
    
    return render(request, 'manage_products.html', context)

@login_required(login_url='login_view')
def add_product(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        return redirect('dashboard')

    categories = Category.objects.all()

    if request.method == 'POST':
        # SUPPRIMER: with transaction.atomic():  (si vous n'en avez pas besoin)
        # OU AJOUTER: from django.db import transaction  en haut du fichier
        
        product_name = request.POST.get('name')
        product_price = request.POST.get('price')
        product_description = request.POST.get('description')
        product_stock = request.POST.get('stock')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        
        product = Product.objects.create(
            shop=shop,
            name=product_name,
            price=product_price,
            description=product_description,
            stock=product_stock,
            category_id=category_id,
            subcategory_id=subcategory_id
        )

        images = request.FILES.getlist('images')
        videos = request.FILES.getlist('videos')

        for image_file in images:
            ProductImage.objects.create(product=product, image=image_file)

        for video_file in videos:
            ProductVideo.objects.create(product=product, video=video_file)  # CORRECTION: video au lieu de video_file

        return redirect('manage_products')

    context = {
        'categories': categories,
    }
    return render(request, 'add_product.html', context)

def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        # ... (le code de cette fonction ne change pas)
        try:
            # S'assure que l'utilisateur est le propriétaire de la boutique
            if request.user.merchant.shop != product.shop:
                return redirect('manage_products')
            
            product.name = request.POST.get('name')
            product.price = Decimal(request.POST.get('price'))
            product.description = request.POST.get('description')
            product.stock = request.POST.get('stock')
            
            # AJOUT : Mise à jour des catégories
            category_id = request.POST.get('category')
            subcategory_id = request.POST.get('subcategory')
            product.category = get_object_or_404(Category, id=category_id) if category_id else None
            product.subcategory = get_object_or_404(SubCategory, id=subcategory_id) if subcategory_id else None
            
            product.save()

            # Gère les images et vidéos existantes et nouvelles
            # ... (la logique de gestion des images/vidéos reste la même)

            return redirect('manage_products')
        except (Merchant.DoesNotExist, InvalidOperation):
            return redirect('dashboard')
    
    # AJOUT : Récupère les catégories et sous-catégories pour le formulaire
    categories = Category.objects.all()
    context = {
        'product': product,
        'categories': categories,
        'is_merchant': True
    }
    return render(request, 'edit_product.html', context)


def delete_product(request, product_id):
    # ... (le code de cette fonction ne change pas)
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.merchant.shop != product.shop:
            return redirect('manage_products')
        product.delete()
    except Merchant.DoesNotExist:
        pass
    return redirect('manage_products')

@login_required(login_url='login_view')
def manage_orders(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
        orders = Order.objects.filter(orderitem__product__shop=shop).distinct().order_by('-date_ordered')
        context = {
            'orders': orders,
            'is_merchant': True
        }
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        return redirect('dashboard')
    return render(request, 'manage_orders.html', context)

@login_required(login_url='login_view')
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    # Vérifie si le commerçant a un produit dans la commande
    is_merchant_for_order = order.orderitem_set.filter(product__shop__merchant=request.user.merchant).exists()
    
    if not is_merchant_for_order:
        return redirect('dashboard')
        
    context = {
        'order': order,
        'is_merchant': True
    }
    return render(request, 'order_detail.html', context)


@login_required(login_url='login_view')
def manage_shop(request):
    try:
        merchant = request.user.merchant
        shop = merchant.shop
        context = {
            'shop': shop,
            'is_merchant': True
        }
    except Merchant.DoesNotExist:
        return redirect('dashboard')
        
    return render(request, 'manage_shop.html', context)

@login_required(login_url='login_view')
def configure_negotiation(request):
    # ... (le code de cette fonction ne change pas)
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
        'settings': settings
    }
    return render(request, 'configure_negotiation.html', context)


# NOUVELLES FONCTIONNALITÉS : Vues pour la navigation et la recherche de produits
def visit_shops(request):
    # Cette vue est maintenant plus simple car la logique de filtrage est dans product_list
    shops = Shop.objects.all()
    context = {'shops': shops}
    return render(request, 'visit_shops.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # AJOUT : Récupération des avis et de la note moyenne
    reviews = Review.objects.filter(product=product).order_by('-date_created')
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    
    # AJOUT : Récupération des produits similaires
    similar_products = product.similar_products.all()
    
    # AJOUT : Récupération des variations de produits
    variations = product.variations.all()
    
    # Vérifier si la catégorie et le slug existent
    has_valid_category = product.category and product.category.slug
    has_valid_subcategory = product.subcategory and product.subcategory.slug
    
    context = {
        'product': product,
        'reviews': reviews,
        'average_rating': average_rating,
        'similar_products': similar_products,
        'variations': variations,
        'is_merchant': request.user.is_authenticated and hasattr(request.user, 'merchant'),
        'has_valid_category': has_valid_category,
        'has_valid_subcategory': has_valid_subcategory
    }
    return render(request, 'product_detail.html', context)

@login_required(login_url='login_view')
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # S'assure que l'utilisateur n'est pas le commerçant de la boutique
    if request.user.is_authenticated and hasattr(request.user, 'merchant'):
        if request.user.merchant.shop == product.shop:
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


# Modifiez la vue product_list pour inclure les slides hero

def product_list(request):
    # Récupération de tous les produits, puis application des filtres
    products = Product.objects.all().order_by('name')
    categories = Category.objects.all()
    
    # Récupérer les slides hero actifs
    hero_slides = HeroSlide.objects.filter(is_active=True).order_by('order')[:5]  # Limiter à 5 slides
    
    # 1. Filtre par recherche (champ 'q')
    query = request.GET.get('q')
    if query:
        # Utilisation de Q pour combiner la recherche sur plusieurs champs
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
    paginator = Paginator(products, 12)  # Affiche 12 produits par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'hero_slides': hero_slides,  # Ajout des slides hero
        'is_merchant': request.user.is_authenticated and hasattr(request.user, 'merchant'),
    }
    return render(request, 'product_list.html', context)
# AJOUT : Vue pour les produits par catégorie
def products_by_category(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug)
    # Réutilisation de la vue product_list avec le filtre de catégorie
    return product_list(request, category_slug=category_slug)

# AJOUT : Vue pour les produits par sous-catégorie
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
        'is_merchant': request.user.is_authenticated and hasattr(request.user, 'merchant'),
        'current_category': subcategory.category,
        'current_subcategory': subcategory,
    }
    return render(request, 'product_list.html', context)


# AJOUT : Vue pour la recherche de produits
def product_search(request):
    return product_list(request)
    
# ... autres vues (le reste du code)
@login_required(login_url='login_view')
def cart_detail(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
        
    context = {'cart': cart, 'is_merchant': request.user.is_authenticated and hasattr(request.user, 'merchant')}
    return render(request, 'cart_detail.html', context)

@login_required(login_url='login_view')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Vérifier si l'article est déjà dans le panier
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    
    if not created:
        cart_item.quantity += 1
    else:
        cart_item.quantity = 1
        
    cart_item.save()
    
    return redirect('cart_detail')
    
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
        'is_merchant': request.user.is_authenticated and hasattr(request.user, 'merchant')
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
            OrderItem.objects.create(
                product=item.product,
                order=order,
                quantity=item.quantity
            )
            # Met à jour le stock du produit
            product = item.product
            product.stock -= item.quantity
            product.save()
            
        # Vide le panier
        cart.items.all().delete()
        
        return redirect('order_confirmation', order_id=order.id)
        
    return redirect('checkout_view')

@login_required(login_url='login_view')
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    context = {
        'order': order,
        'is_merchant': request.user.is_authenticated and hasattr(request.user, 'merchant')
    }
    return render(request, 'order_confirmation.html', context)
    
@login_required(login_url='login_view')
def start_negotiation_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Si le client est aussi un commerçant et que le produit lui appartient, on redirige
    if hasattr(request.user, 'merchant') and request.user.merchant.shop == product.shop:
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

@login_required(login_url='login_view')
def conversation_detail_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Assure que seul le client ou le commerçant peut voir la conversation
    is_merchant = hasattr(request.user, 'merchant')
    if is_merchant and conversation.merchant.user != request.user:
        return redirect('list_conversations')
    elif not is_merchant and conversation.client != request.user:
        return redirect('list_conversations')
        
    context = {
        'conversation': conversation,
        'is_merchant': is_merchant,
        'is_client': not is_merchant,
    }
    return render(request, 'conversation_detail.html', context)

@login_required(login_url='login_view')
def chat_api(request, conversation_id):
    if request.method == 'POST':
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        is_merchant = hasattr(request.user, 'merchant')
        # Vérifie que l'utilisateur est bien un participant de la conversation
        if (is_merchant and conversation.merchant.user != request.user) or (not is_merchant and conversation.client != request.user):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # ... (le code de cette fonction ne change pas)
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
            if is_merchant:
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
    is_merchant = hasattr(request.user, 'merchant')
    
    if is_merchant:
        # Si c'est un commerçant, on récupère les conversations de sa boutique
        conversations = Conversation.objects.filter(merchant=request.user.merchant)
    else:
        # Si c'est un client, on récupère ses conversations
        conversations = Conversation.objects.filter(client=request.user)
    
    context = {
        'conversations': conversations,
        'is_merchant': is_merchant
    }
    return render(request, 'list_conversations.html', context)


@login_required(login_url='login_view')
def negotiation_chat(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Vérification des permissions
    is_merchant = hasattr(request.user, 'merchant')
    if (is_merchant and conversation.merchant.user != request.user) or (not is_merchant and conversation.client != request.user):
        return redirect('list_conversations')
    
    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        if message_text:
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                text=message_text
            )
            return redirect('negotiation_chat', conversation_id=conversation.id)
    
    messages = conversation.messages.all().order_by('timestamp')
    
    context = {
        'conversation': conversation,
        'messages': messages,
        'product': conversation.product,
        'is_merchant': is_merchant,
    }
    return render(request, 'negotiation_chat.html', context)
