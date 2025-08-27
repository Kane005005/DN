# shop/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Sum, F
from .models import Merchant, Shop, Product, ProductImage, ProductVideo, Cart, CartItem, Order, OrderItem
from django.core.files.storage import FileSystemStorage
from decimal import Decimal, InvalidOperation
import json
from datetime import date, timedelta
from django.views.decorators.http import require_POST
from django.db.models.functions import TruncDay


def index(request):
    return render(request, 'index.html')

def create_shop(request):
    # ... (le code de cette fonction ne change pas)
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        country = request.POST.get('country')
        category = request.POST.get('category')
        description = request.POST.get('description')
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            merchant = Merchant.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                country=country
            )
            shop = Shop.objects.create(
                merchant=merchant,
                category=category,
                description=description
            )
            login(request, user)
            return redirect('dashboard') # Redirige vers le tableau de bord après l'inscription
        except IntegrityError:
            error_message = "Ce nom d'utilisateur, email ou numéro de téléphone est déjà utilisé."
            return render(request, 'create_shop.html', {'error_message': error_message})
        except Exception as e:
            error_message = f"Une erreur est survenue : {e}"
            return render(request, 'create_shop.html', {'error_message': error_message})

    return render(request, 'create_shop.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard') # Redirige vers le tableau de bord après la connexion
        else:
            error_message = "Nom d'utilisateur ou mot de passe incorrect."
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')



@login_required(login_url='login_view')
def dashboard(request):
    """
    Vue principale du tableau de bord d'un commerçant.
    """
    merchant = get_object_or_404(Merchant, user=request.user)
    shop = Shop.objects.filter(merchant=merchant).first()

    if not shop:
        context = {'shop': None}
        return render(request, 'dashboard_home.html', context)

    # Récupère le nombre total de produits
    total_products = Product.objects.filter(shop=shop).count()
    
    # Récupère le nombre total de commandes pour la boutique
    total_orders = Order.objects.filter(orderitem__product__shop=shop).distinct().count()
    
    # Calcule le chiffre d'affaires total
    total_revenue_result = OrderItem.objects.filter(
        product__shop=shop,
        order__complete=True
    ).aggregate(total_revenue=Sum(F('quantity') * F('product__price')))
    total_revenue = total_revenue_result['total_revenue'] or 0
    
    # Récupère les données de revenus pour les 30 derniers jours
    today = date.today()
    last_30_days = today - timedelta(days=30)
    
    revenue_by_day = OrderItem.objects.filter(
        order__date_ordered__date__gte=last_30_days,
        product__shop=shop
    ).annotate(
        day=TruncDay('order__date_ordered')
    ).values('day').annotate(
        revenue=Sum(F('quantity') * F('product__price'))
    ).order_by('day')
    
    # Convertit les dates en chaînes pour la sérialisation JSON
    revenue_data = [{'day': item['day'].strftime('%Y-%m-%d'), 'revenue': float(item['revenue'])} for item in revenue_by_day]
    
    # Récupère les 5 produits les plus vendus
    top_products = OrderItem.objects.filter(
        product__shop=shop
    ).values('product__name').annotate(
        quantity=Sum('quantity')
    ).order_by('-quantity')[:5]

    top_products_data = [{'name': item['product__name'], 'quantity': item['quantity']} for item in top_products]

    context = {
        'shop': shop,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'revenue_data_json': json.dumps(revenue_data),
        'top_products_data_json': json.dumps(top_products_data),
    }

    return render(request, 'dashboard_home.html', context)

@login_required(login_url='login_view')
def manage_shop(request):
    """
    Vue pour gérer et mettre à jour les informations de la boutique.
    """
    merchant = get_object_or_404(Merchant, user=request.user)
    shop = get_object_or_404(Shop, merchant=merchant)

    if request.method == 'POST':
        # Mettre à jour les champs de la boutique
        shop.category = request.POST.get('category')
        shop.description = request.POST.get('description')
        shop.save()
        return redirect('manage_shop')  # Rediriger vers la même page après la sauvegarde
    
    context = {
        'shop': shop
    }
    return render(request, 'manage_shop.html', context)


@login_required(login_url='login_view')
def manage_products(request):
    """
    Vue pour gérer les produits de la boutique du commerçant.
    """
    try:
        merchant = Merchant.objects.get(user=request.user)
    except Merchant.DoesNotExist:
        return redirect('create_shop')

    try:
        shop = Shop.objects.get(merchant=merchant)
    except Shop.DoesNotExist:
        return redirect('dashboard') # Redirige vers le tableau de bord si la boutique n'existe pas

    products = Product.objects.filter(shop=shop)

    context = {
        'merchant': merchant,
        'shop': shop,
        'products': products
    }
    
    return render(request, 'manage_products.html', context)

@login_required(login_url='login_view')
def manage_orders(request):
    """
    Vue pour gérer les commandes du commerçant.
    Affiche une liste de toutes les commandes pour les produits de la boutique du commerçant connecté.
    """
    try:
        merchant = Merchant.objects.get(user=request.user)
        shop = merchant.shop
    except (Merchant.DoesNotExist, Shop.DoesNotExist):
        # Rediriger si la boutique n'existe pas
        return redirect('create_shop')
    
    # On récupère les commandes qui contiennent au moins un article de notre boutique.
    # On utilise .distinct() pour éviter les doublons si une commande contient plusieurs produits de la même boutique.
    orders = Order.objects.filter(orderitem__product__shop=shop).distinct().order_by('-date_ordered')

    # On pré-calcule le total de chaque commande pour le template
    for order in orders:
        # On s'assure que get_cart_total est une méthode sur le modèle Order
        # qui calcule le total en fonction des OrderItems.
        order.get_cart_total = sum(item.total_price for item in order.orderitem_set.all())

    context = {
        'shop': shop,
        'orders': orders,
    }

    return render(request, 'manage_orders.html', context)

def logout_view(request):
    """
    Cette vue gère la déconnexion de l'utilisateur.
    """
    logout(request)
    return redirect('index') # Redirige vers la page d'accueil après la déconnexion

@login_required(login_url='login_view')
def add_product(request):
    if request.method == 'POST':
        # On récupère les données du formulaire
        name = request.POST.get('name')
        description = request.POST.get('description')
        price_str = request.POST.get('price') # On récupère la valeur en tant que chaîne de caractères
        stock_str = request.POST.get('stock') # On récupère la valeur en tant que chaîne de caractères

        try:
            # 1. Validation et conversion des données
            if not name or not price_str or not stock_str:
                raise ValueError("Veuillez remplir tous les champs obligatoires.")
            
            # 2. On convertit les chaînes en types numériques
            price = Decimal(price_str)
            stock = int(stock_str)

            # 3. On trouve la boutique du commerçant connecté
            merchant = request.user.merchant
            shop = merchant.shop
            
            # 4. On crée le modèle Product
            product = Product.objects.create(
                shop=shop,
                name=name,
                description=description,
                price=price,
                stock=stock
            )
            
            # 5. On gère l'envoi des images
            if 'images' in request.FILES:
                images = request.FILES.getlist('images')
                for image in images:
                    ProductImage.objects.create(product=product, image=image)

            # 6. On gère l'envoi des vidéos
            if 'videos' in request.FILES:
                videos = request.FILES.getlist('videos')
                for video in videos:
                    ProductVideo.objects.create(product=product, video=video)
            
            # Redirection vers le tableau de bord ou une page de succès
            return redirect('dashboard')
        
        except (InvalidOperation, ValueError) as e:
            # Cette partie va attraper les erreurs de conversion ou de champs manquants
            error_message = f"Erreur de données. Veuillez vérifier les valeurs du prix et du stock. ({e})"
            return render(request, 'add_product.html', {'error_message': error_message})
        
        except Exception as e:
            # Pour toutes les autres erreurs
            error_message = f"Une erreur est survenue lors de l'ajout du produit : {e}"
            return render(request, 'add_product.html', {'error_message': error_message})
    
    return render(request, 'add_product.html')
# shop/views.py


from django.shortcuts import get_object_or_404 # Importe ceci


@login_required(login_url='login_view')
def edit_product(request, product_id):
    """
    Cette vue permet de modifier un produit existant.
    Elle vérifie que le commerçant a bien le droit de modifier ce produit.
    """
    # Récupère le produit ou renvoie une erreur 404 si le produit n'existe pas
    product = get_object_or_404(Product, pk=product_id)

    # S'assure que le produit appartient bien au commerçant connecté
    if product.shop.merchant.user != request.user:
        return redirect('dashboard') # Redirection si l'utilisateur n'est pas le propriétaire

    if request.method == 'POST':
        # Mise à jour des données du produit
        try:
            name = request.POST.get('name')
            description = request.POST.get('description')
            price_str = request.POST.get('price')
            stock_str = request.POST.get('stock')

            if not name or not price_str or not stock_str:
                raise ValueError("Veuillez remplir tous les champs obligatoires.")

            price = Decimal(price_str)
            stock = int(stock_str)

            product.name = name
            product.description = description
            product.price = price
            product.stock = stock
            product.save() # Sauvegarde les modifications

            # Ajout de nouvelles images
            if 'images' in request.FILES:
                images = request.FILES.getlist('images')
                for image in images:
                    ProductImage.objects.create(product=product, image=image)

            # Ajout de nouvelles vidéos
            if 'videos' in request.FILES:
                videos = request.FILES.getlist('videos')
                for video in videos:
                    ProductVideo.objects.create(product=product, video=video)

            return redirect('dashboard')

        except (InvalidOperation, ValueError) as e:
            error_message = f"Erreur de données. Veuillez vérifier les valeurs du prix et du stock. ({e})"
            return render(request, 'edit_product.html', {'product': product, 'error_message': error_message})
        except Exception as e:
            error_message = f"Une erreur est survenue lors de la modification du produit : {e}"
            return render(request, 'edit_product.html', {'product': product, 'error_message': error_message})

    # Affiche le formulaire avec les données du produit
    return render(request, 'edit_product.html', {'product': product})


@login_required(login_url='login_view')
def delete_product(request, product_id):
    """
    Cette vue permet de supprimer un produit.
    Elle vérifie que le commerçant a bien le droit de supprimer ce produit.
    """
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=product_id)
        
        # S'assure que le produit appartient bien au commerçant connecté
        if product.shop.merchant.user != request.user:
            return redirect('dashboard') # Redirection si l'utilisateur n'est pas le propriétaire

        # Supprime le produit
        product.delete()
        
    return redirect('dashboard')


def visit_shops(request):
    """
    Cette vue affiche la liste de tous les produits disponibles sur la plateforme.
    """
    # On récupère tous les produits de la base de données
    all_products = Product.objects.all()
    
    # On envoie la liste des produits au template
    return render(request, 'visit_shops.html', {'products': all_products})

def product_detail(request, product_id):
    """
    Cette vue affiche les détails d'un produit spécifique.
    """
    # Récupère le produit ou renvoie une erreur 404 si le produit n'existe pas
    product = get_object_or_404(Product, pk=product_id)
    
    return render(request, 'product_detail.html', {'product': product})


@login_required(login_url='login_view')
def add_to_cart(request, product_id):
    """
    Cette vue permet d'ajouter un produit au panier de l'utilisateur.
    """
    # Récupère le produit ou renvoie une erreur 404
    product = get_object_or_404(Product, pk=product_id)
    
    # Récupère le panier de l'utilisateur ou le crée s'il n'existe pas
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Vérifie si l'article est déjà dans le panier
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart, 
        product=product,
        defaults={'quantity': 1}
    )
    
    # Si l'article existait déjà, on incrémente la quantité
    if not item_created:
        cart_item.quantity += 1
        cart_item.save()
        
    # Redirige l'utilisateur vers la page de détail du produit ou le panier
    return redirect('product_detail', product_id=product.id)


@login_required(login_url='login_view')
def cart_detail(request):
    """
    Cette vue affiche le contenu du panier de l'utilisateur.
    """
    cart = None
    total_cost = 0
    
    try:
        cart = Cart.objects.get(user=request.user)
        # Calcule le coût total
        for item in cart.items.all():
            total_cost += item.get_total
    except Cart.DoesNotExist:
        pass # Le panier n'existe pas encore, ce qui est normal
        
    return render(request, 'cart_detail.html', {
        'cart': cart,
        'total_cost': total_cost
    })


@login_required(login_url='login_view')
def remove_from_cart(request, item_id):
    """
    Cette vue permet de supprimer un article du panier.
    """
    if request.method == 'POST':
        item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
        item.delete()
    return redirect('cart_detail')

@login_required(login_url='login_view')
def update_cart_item(request, item_id):
    """
    Cette vue permet de mettre à jour la quantité d'un article dans le panier.
    """
    if request.method == 'POST':
        item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
        try:
            new_quantity = int(request.POST.get('quantity'))
            if new_quantity > 0:
                item.quantity = new_quantity
                item.save()
            else:
                item.delete() # Supprime l'article si la quantité est 0 ou moins
        except (ValueError, InvalidOperation):
            pass # Ignore l'erreur si la quantité n'est pas un nombre valide
            
    return redirect('cart_detail')


@login_required(login_url='login_view')
def checkout_view(request):
    """
    Cette vue affiche la page de paiement.
    """
    # Récupère le panier de l'utilisateur
    cart = get_object_or_404(Cart, user=request.user)
    
    # Calcule le total du panier
    total_cost = sum(item.total_cost for item in cart.items.all())
    
    context = {
        'cart': cart,
        'total_cost': total_cost
    }
    
    return render(request, 'checkout.html', context)






@login_required(login_url='login_view')
def process_order(request):
    """
    Cette vue traite la commande du client, la crée et vide le panier.
    """
    if request.method == 'POST':
        # Récupère les informations de livraison du formulaire
        full_name = request.POST.get('full_name')
        address = request.POST.get('address')
        city = request.POST.get('city')
        phone = request.POST.get('phone')

        # Récupère le panier de l'utilisateur
        cart = get_object_or_404(Cart, user=request.user)
        
        # Crée une nouvelle commande
        order = Order.objects.create(
            user=request.user,
            full_name=full_name,
            address=address,
            city=city,
            phone=phone,
            complete=True # Pour l'instant, on considère la commande complète
        )
        
        # Crée des articles de commande à partir des articles du panier
        for item in cart.items.all():
            OrderItem.objects.create(
                product=item.product,
                order=order,
                quantity=item.quantity
            )
            
        # Vide le panier une fois la commande passée
        cart.items.all().delete()
        
        # Redirige vers une page de confirmation
        return redirect('order_confirmation', order_id=order.id)
        
    return redirect('checkout_view')
@login_required(login_url='login_view')
def order_confirmation(request, order_id):
    """
    Cette vue affiche la page de confirmation de la commande.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    
    context = {
        'order': order
    }
    
    return render(request, 'order_confirmation.html', context)


@login_required(login_url='login_view')
def manage_orders(request):
    """
    Vue pour afficher toutes les commandes d'un commerçant.
    """
    merchant = get_object_or_404(Merchant, user=request.user)
    
    # Récupère toutes les commandes liées aux produits de la boutique du commerçant
    # On utilise .distinct() pour s'assurer qu'une commande n'est pas affichée plusieurs fois
    orders = Order.objects.filter(
        orderitem__product__shop__merchant=merchant
    ).distinct().order_by('-date_ordered')

    context = {
        'orders': orders,
    }
    return render(request, 'manage_orders.html', context)


@login_required(login_url='login_view')
def order_detail(request, order_id):
    """
    Vue pour afficher les détails d'une commande spécifique.
    Le commerçant peut voir les informations du client et les articles commandés.
    """
    try:
        # Récupère l'objet commande ou renvoie une erreur 404 s'il n'existe pas.
        # On s'assure que la commande appartient à la boutique du commerçant connecté.
        order = get_object_or_404(
            Order,
            pk=order_id,
            orderitem__product__shop__merchant__user=request.user
        )
    except Exception as e:
        print(f"Erreur lors de la récupération de la commande : {e}")
        return redirect('manage_orders')
        
    # Récupère tous les articles liés à cette commande
    items = order.orderitem_set.all()

    context = {
        'order': order,
        'items': items,
    }

    return render(request, 'order_detail.html', context)

# NOUVELLES VUES POUR LE CHAT DE NÉGOCIATION
@login_required(login_url='login_view')
def negotiation_chat_view(request, product_id):
    """
    Cette vue gère l'affichage du chat de négociation.
    Elle est accessible à la fois par le client et le commerçant.
    """
    product = get_object_or_404(Product, pk=product_id)
    
    # On vérifie si l'utilisateur est le commerçant de la boutique
    is_merchant = False
    try:
        merchant = Merchant.objects.get(user=request.user)
        if product.shop.merchant == merchant:
            is_merchant = True
    except Merchant.DoesNotExist:
        pass

    # On trouve ou on crée la conversation
    if is_merchant:
        # Le commerçant ne démarre pas la conversation, il la rejoint
        # Il peut rejoindre n'importe quelle conversation liée à son produit
        conversation = get_object_or_404(Conversation, product=product)
    else:
        # Le client démarre ou rejoint sa propre conversation
        conversation, created = Conversation.objects.get_or_create(
            product=product,
            client=request.user,
            merchant=product.shop.merchant # Le commerçant est celui du produit
        )

    if request.method == 'POST':
        # Gérer l'envoi d'un nouveau message via une requête AJAX
        try:
            data = json.loads(request.body)
            message_text = data.get('message_text')
            if message_text:
                new_message = Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    text=message_text
                )
                # Retourne le nouveau message au format JSON pour la mise à jour côté client
                return JsonResponse({
                    'id': new_message.id,
                    'text': new_message.text,
                    'sender': new_message.sender.username,
                    'is_me': new_message.sender == request.user,
                    'timestamp': new_message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    # Gérer l'affichage initial de la page ou les requêtes GET pour rafraîchir le chat
    messages = conversation.messages.order_by('timestamp')

    # Prépare les messages pour le rendu du template
    # Ajoute un indicateur 'is_me' pour différencier les messages de l'utilisateur
    formatted_messages = []
    for message in messages:
        formatted_messages.append({
            'text': message.text,
            'sender': message.sender.username,
            'is_me': message.sender == request.user,
            'timestamp': message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        })

    context = {
        'conversation': conversation,
        'product': product,
        'messages': formatted_messages,
        'is_merchant': is_merchant,
    }
    
    return render(request, 'negotiation_chat.html', context)
