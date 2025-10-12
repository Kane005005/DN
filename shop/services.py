# Fichier : shop/services.py
import os
import re
import logging
from decimal import Decimal, InvalidOperation
from openai import OpenAI
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Avg
from .models import (
    Product, NegotiationSettings, Conversation, Message, 
    MerchantActivity, ProductImage, ProductVideo, ProductVariation,
    Review, Category, SubCategory
)

# Configuration du logger
logger = logging.getLogger(__name__)

# services.py - CORRECTION de la fonction should_use_ai

def should_use_ai(conversation):
    """
    Détermine si l'IA doit répondre en fonction de l'activité réelle du commerçant
    """
    try:
        # Vérifie si la négociation IA est activée
        try:
            negotiation_settings = NegotiationSettings.objects.get(shop=conversation.product.shop)
            if not negotiation_settings.is_active:
                logger.debug(f"Négociation IA désactivée pour {conversation.merchant}")
                return False
        except NegotiationSettings.DoesNotExist:
            logger.debug(f"Paramètres de négociation non trouvés pour {conversation.merchant.shop}")
            return False

        # Vérifie l'activité du commerçant
        try:
            activity = MerchantActivity.objects.get(merchant=conversation.merchant)
            
            # L'IA n'intervient PAS si :
            # 1. Le commerçant est en ligne ET actif récemment (moins de 2 minutes)
            if activity.is_online and activity.minutes_since_last_seen < 2:
                logger.debug(f"Commerçant {conversation.merchant} en ligne et actif - IA n'intervient pas")
                return False
            
            # 2. Le commerçant a été actif dans le chat récemment (moins de 10 minutes)
            recent_messages = Message.objects.filter(
                conversation__merchant=conversation.merchant,
                sender=conversation.merchant.user,
                timestamp__gte=timezone.now() - timedelta(minutes=10)
            )
            if recent_messages.exists():
                logger.debug(f"Commerçant {conversation.merchant} actif dans le chat - IA n'intervient pas")
                return False
                
        except MerchantActivity.DoesNotExist:
            # Si pas d'info d'activité, l'IA peut intervenir
            logger.debug(f"Aucune activité trouvée pour {conversation.merchant} - IA peut intervenir")
            pass
            
        # L'IA intervient seulement si toutes les conditions sont remplies
        logger.info(f"IA autorisée à répondre pour la conversation {conversation.id}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur dans should_use_ai: {e}")
        return False

def extract_price_from_message(message):
    """
    Extrait un prix d'un message texte avec plusieurs motifs
    """
    # Nettoyage du message
    cleaned_message = message.replace(',', '.').replace(' ', '')
    
    # Recherche de motifs de prix courants
    price_patterns = [
        r'(\d+(?:\.\d+)?)\s*CFA',
        r'(\d+(?:\.\d+)?)\s*€',
        r'(\d+(?:\.\d+)?)\s*euros',
        r'prix\s*:\s*(\d+(?:\.\d+)?)',
        r'propos[ée]\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*$',
        r'(\d+(?:\.\d+)?)\s*francs',
        r'à\s*(\d+(?:\.\d+)?)',
        r'pour\s*(\d+(?:\.\d+)?)',
        r'(\d+)\s*milliers',
        r'(\d+)\s*mille'
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            try:
                price_str = match.group(1).replace(',', '.')
                price = Decimal(price_str)
                
                # Validation du prix raisonnable
                if price > 0 and price < 10000000:  # Entre 0 et 10 millions
                    logger.debug(f"Prix extrait: {price} CFA")
                    return price
            except (InvalidOperation, ValueError) as e:
                logger.debug(f"Erreur conversion prix: {e}")
                continue
    
    logger.debug("Aucun prix valide trouvé dans le message")
    return None

def is_negotiation_message(message):
    """
    Détermine si le message concerne une négociation de prix
    """
    negotiation_keywords = [
        'prix', 'cher', 'coût', 'tarif', 'proposition', 'offre', 
        'négocier', 'marchander', 'discuter', 'réduction', 'rabais',
        'solde', 'promotion', 'discount', 'baisser', 'réduire',
        'marchandage', 'arranger', 'concéder', 'discount', 'bon prix',
        'dernier prix', 'meilleur prix', 'prix final'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in negotiation_keywords)

def is_technical_question(message):
    """
    Détermine si le message est une question technique sur le produit
    """
    question_patterns = [
        r'comment.*fonctionne',
        r'quelle.*taille',
        r'quelles.*caractéristiques',
        r'c\'est quoi',
        r'qu\'est.*ce que',
        r'peux.*tu expliquer',
        r'décris.*moi',
        r'parle.*moi',
        r'dis.*moi',
        r'caractéristique',
        r'spécification',
        r'technique',
        r'matériau',
        r'composition',
        r'dimension',
        r'capacité',
        r'utilisation',
        r'fonctionnalité',
        r'avantage',
        r'inconvénient',
        r'mode d\'emploi',
        r'notice',
        r'garantie',
        r'entretien',
        r'nettoyage'
    ]
    
    message_lower = message.lower()
    return any(re.search(pattern, message_lower) for pattern in question_patterns)

def is_general_question(message):
    """
    Détermine si le message est une question générale
    """
    general_patterns = [
        r'bonjour',
        r'bonsoir',
        r'salut',
        r'coucou',
        r'hello',
        r'hi ',
        r'ça va',
        r'cv ',
        r'disponible',
        r'stock',
        r'livraison',
        r'délai',
        r'envoi',
        r'expédition',
        r'retour',
        r'remboursement',
        r'échange',
        r'couleur',
        r'modèle',
        r'version'
    ]
    
    message_lower = message.lower()
    return any(re.search(pattern, message_lower) for pattern in general_patterns)

def build_product_context(product):
    """
    Construit un contexte détaillé sur le produit pour l'IA
    """
    context = f"""
INFORMATIONS DÉTAILLÉES DU PRODUIT :

📋 DESCRIPTION GÉNÉRALE :
Nom : {product.name}
Prix initial : {product.price} CFA
Description : {product.description or "Aucune description disponible"}
Stock disponible : {product.stock} unités
Catégorie : {product.category.name if product.category else "Non catégorisé"}
Sous-catégorie : {product.subcategory.name if product.subcategory else "Non catégorisé"}
Date d'ajout : {product.date_added.strftime('%d/%m/%Y')}

🏪 INFORMATIONS BOUTIQUE :
Commerçant : {product.shop.merchant.first_name} {product.shop.merchant.last_name}
Description boutique : {product.shop.description or "Aucune description"}
"""
    
    # Ajoute les variations de produit si elles existent
    variations = product.variations.all()
    if variations.exists():
        context += "\n🎨 VARIATIONS DISPONIBLES :\n"
        for variation in variations:
            variation_price = product.price + variation.price_modifier
            context += f"- {variation.type} : {variation.value} "
            if variation.price_modifier != 0:
                context += f"(prix: {variation_price} CFA) "
            if variation.stock_variation > 0:
                context += f"(stock: {variation.stock_variation})"
            context += "\n"
    
    # Ajoute les médias disponibles
    images = product.images.all()
    if images.exists():
        context += f"\n🖼️ MÉDIAS : {images.count()} image(s) disponible(s)"
    
    videos = product.videos.all()
    if videos.exists():
        context += f"\n🎥 VIDÉOS : {videos.count()} vidéo(s) de démonstration"
    
    # Ajoute les avis si disponibles
    reviews = product.reviews.all()
    if reviews.exists():
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        context += f"\n⭐ AVIS CLIENTS : Note moyenne {avg_rating:.1f}/5 sur {reviews.count()} avis"
    
    # Ajoute les produits similaires
    similar_products = product.similar_products.all()[:3]
    if similar_products.exists():
        context += "\n🔗 PRODUITS SIMILAIRES :\n"
        for similar in similar_products:
            context += f"- {similar.name} ({similar.price} CFA)\n"
    
    return context

def get_conversation_history(conversation, max_messages=6):
    """
    Récupère l'historique récent de la conversation
    """
    messages = conversation.messages.all().order_by('-timestamp')[:max_messages]
    history = []
    
    for message in reversed(messages):
        role = "user" if message.sender == conversation.client else "assistant"
        history.append({
            "role": role,
            "content": message.text
        })
    
    return history

def get_openai_client():
    """
    Retourne le client OpenAI configuré pour OpenRouter
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    
    if not api_key:
        logger.error("❌ CLÉ API OPENROUTER NON CONFIGURÉE")
        logger.error("💡 Pour configurer :")
        logger.error("1. Allez sur https://openrouter.ai/")
        logger.error("2. Créez un compte et générez une clé API")
        logger.error("3. Définissez la variable d'environnement : export OPENROUTER_API_KEY='votre_clé'")
        return None

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        # Test simple de la clé
        try:
            client.chat.completions.create(
                model="mistralai/mistral-small-3.1-24b-instruct:free",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
        except Exception as test_error:
            if "401" in str(test_error):
                logger.error("❌ CLÉ API OPENROUTER INVALIDE")
                logger.error("💡 Vérifiez votre clé API sur https://openrouter.ai/keys")
                return None
            # Pour les autres erreurs, on continue car le test a au moins confirmé que la clé est valide
        
        logger.info("✅ Clé API OpenRouter validée")
        return client
        
    except Exception as e:
        logger.error(f"❌ Erreur création client OpenAI: {e}")
        return None

def get_ai_negotiation_response(product: Product, user_message: str, conversation: Conversation):
    """
    Appelle l'API Mistral via OpenRouter pour générer une réponse contextuelle et intelligente
    """
    # Vérifie si l'IA doit répondre
    if not should_use_ai(conversation):
        logger.debug("IA non autorisée à répondre")
        return None

    # Récupère le client OpenAI
    client = get_openai_client()
    if not client:
        logger.error("❌ Impossible d'initialiser le client API - utilisation du mode secours")
        return get_fallback_response(product, user_message, conversation)

    # Récupère les paramètres de négociation
    try:
        negotiation_settings = NegotiationSettings.objects.get(shop=conversation.merchant.shop)
        min_price = negotiation_settings.min_price_threshold or Decimal(product.price * Decimal('0.7'))
        max_discount_percentage = negotiation_settings.max_discount_percentage or Decimal('10.00')
        
        logger.debug(f"Paramètres négociation: min={min_price}, max_discount={max_discount_percentage}%")
        
    except NegotiationSettings.DoesNotExist:
        min_price = Decimal(product.price * Decimal('0.7'))
        max_discount_percentage = Decimal('10.00')
        logger.debug("Paramètres négociation par défaut utilisés")

    # Construit le contexte du produit
    product_context = build_product_context(product)
    
    # Analyse le message de l'utilisateur
    user_price_offer = extract_price_from_message(user_message)
    is_negotiation = is_negotiation_message(user_message)
    is_technical = is_technical_question(user_message)
    
    logger.debug(f"Analyse message: prix={user_price_offer}, négociation={is_negotiation}, technique={is_technical}")

    # Prépare le prompt système adapté au contexte
    if user_price_offer is not None:
        # Mode négociation de prix
        system_prompt = f"""Tu es {conversation.merchant.first_name}, assistant commercial.

Produit: {product.name}
Prix: {product.price} CFA
Offre client: {user_price_offer} CFA

Réponds en français en 1-2 phrases. Sois professionnel."""
        
    elif is_technical:
        # Mode réponse aux questions techniques
        system_prompt = f"""Tu es {conversation.merchant.first_name}, expert technique.

Produit: {product.name}

Réponds à la question technique en 2-3 phrases. Sois précis."""
        
    elif is_negotiation:
        # Mode initiation de négociation
        system_prompt = f"""Tu es {conversation.merchant.first_name}, commercial.

Produit: {product.name} - {product.price} CFA

Engage la discussion commerciale en 1-2 phrases. Sois professionnel."""
        
    else:
        # Mode conversation générale
        system_prompt = f"""Tu es {conversation.merchant.first_name}, assistant.

Produit: {product.name}

Accueille le client en 1-2 phrases. Sois courtois."""

    # Construit les messages pour l'API
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    try:
        logger.info(f"🔗 Appel API Mistral pour conversation {conversation.id}")
        
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://deanna-ecommerce.com",
                "X-Title": "DEANNA E-commerce",
            },
            model="mistralai/mistral-small-3.1-24b-instruct:free",
            messages=messages,
            max_tokens=100,
            temperature=0.7,
        )
        
        ai_message = completion.choices[0].message.content.strip()
        logger.info(f"✅ Réponse Mistral générée: {ai_message}")
        
        return ai_message
        
    except Exception as e:
        logger.error(f"❌ Erreur API OpenRouter: {e}")
        
        # Vérifie si c'est une erreur d'authentification
        if "401" in str(e) or "User not found" in str(e):
            logger.error("🚨 ERREUR D'AUTHENTIFICATION - Vérifiez votre clé API OpenRouter")
            logger.error("💡 Allez sur https://openrouter.ai/keys pour générer une nouvelle clé")
        
        return get_fallback_response(product, user_message, conversation)

def get_fallback_response(product, user_message, conversation):
    """
    Réponse de secours intelligente quand l'IA n'est pas disponible
    """
    user_price_offer = extract_price_from_message(user_message)
    
    if user_price_offer is not None:
        try:
            negotiation_settings = NegotiationSettings.objects.get(shop=conversation.merchant.shop)
            min_price = negotiation_settings.min_price_threshold or Decimal(product.price * Decimal('0.7'))
        except NegotiationSettings.DoesNotExist:
            min_price = Decimal(product.price * Decimal('0.7'))

        if user_price_offer >= product.price:
            return f"J'accepte votre offre de {user_price_offer} CFA ! Le produit est à vous."
        elif user_price_offer >= min_price:
            return f"Je peux vous proposer {user_price_offer} CFA. C'est un prix raisonnable !"
        else:
            return f"Je ne peux pas accepter moins de {min_price} CFA pour ce produit de qualité."
            
    elif is_technical_question(user_message):
        return "Je vous remercie pour votre question technique. Le commerçant vous répondra dès son retour avec les informations détaillées."
        
    elif "bonjour" in user_message.lower() or "salut" in user_message.lower():
        return f"Bonjour ! Je suis l'assistant de {conversation.merchant.first_name}. Comment puis-je vous aider avec {product.name} ?"
        
    elif "merci" in user_message.lower():
        return "Je vous en prie ! N'hésitez pas si vous avez d'autres questions."
        
    else:
        return "Merci pour votre message. Le commerçant vous répondra rapidement."

def update_merchant_activity(user):
    """
    Met à jour l'activité du commerçant (à appeler à chaque connexion/action)
    """
    if hasattr(user, 'merchant'):
        try:
            activity, created = MerchantActivity.objects.get_or_create(merchant=user.merchant)
            activity.last_seen = timezone.now()
            activity.is_online = True
            
            if created:
                activity.last_login = timezone.now()
                logger.info(f"Nouvelle activité créée pour {user.merchant}")
            else:
                logger.debug(f"Activité mise à jour pour {user.merchant}")
                
            activity.save()
            return activity
            
        except Exception as e:
            logger.error(f"Erreur mise à jour activité pour {user.merchant}: {e}")
    
    return None

def get_merchant_status(merchant):
    """
    Retourne le statut détaillé d'un commerçant
    """
    try:
        activity = MerchantActivity.objects.get(merchant=merchant)
        
        if not hasattr(activity, 'minutes_since_last_seen'):
            # Calcul manuel si la propriété n'existe pas
            from django.utils import timezone
            minutes_since_seen = (timezone.now() - activity.last_seen).total_seconds() / 60
        else:
            minutes_since_seen = activity.minutes_since_last_seen
        
        if activity.is_online:
            if minutes_since_seen < 1:
                return {
                    'status': 'en_ligne_actif',
                    'label': 'En ligne',
                    'description': 'Connecté et actif',
                    'can_use_ai': False
                }
            elif minutes_since_seen < 3:
                return {
                    'status': 'en_ligne_inactif',
                    'label': 'En ligne',
                    'description': 'Connecté mais inactif',
                    'can_use_ai': False
                }
            else:
                return {
                    'status': 'en_ligne_absent',
                    'label': 'Absent',
                    'description': 'Connecté mais absent',
                    'can_use_ai': True
                }
        else:
            if minutes_since_seen < 5:
                return {
                    'status': 'hors_ligne_recent',
                    'label': 'Hors ligne',
                    'description': 'Déconnecté récemment',
                    'can_use_ai': True
                }
            else:
                return {
                    'status': 'hors_ligne',
                    'label': 'Hors ligne',
                    'description': 'Déconnecté',
                    'can_use_ai': True
                }
                
    except MerchantActivity.DoesNotExist:
        return {
            'status': 'inconnu',
            'label': 'Statut inconnu',
            'description': 'Aucune information disponible',
            'can_use_ai': True
        }

def can_use_ai_for_conversation(conversation):
    """
    Vérifie si l'IA peut être utilisée pour une conversation spécifique
    """
    status = get_merchant_status(conversation.merchant)
    
    # Vérifie les paramètres de négociation
    try:
        negotiation_settings = NegotiationSettings.objects.get(shop=conversation.merchant.shop)
        if not negotiation_settings.is_active:
            return False
    except NegotiationSettings.DoesNotExist:
        return False
    
    return status['can_use_ai']

def get_conversation_ai_status(conversation):
    """
    Retourne le statut complet de l'IA pour une conversation
    """
    merchant_status = get_merchant_status(conversation.merchant)
    
    try:
        negotiation_settings = NegotiationSettings.objects.get(shop=conversation.merchant.shop)
        ai_enabled = negotiation_settings.is_active
    except NegotiationSettings.DoesNotExist:
        ai_enabled = False
    
    return {
        'merchant_status': merchant_status,
        'ai_enabled': ai_enabled,
        'can_use_ai': merchant_status['can_use_ai'] and ai_enabled,
        'merchant_name': f"{conversation.merchant.first_name} {conversation.merchant.last_name}",
        'shop_name': conversation.merchant.shop.description or "Boutique"
    }
