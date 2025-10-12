# Fichier : shop/services.py
import os
import re
import logging
import requests
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Avg
from .models import (
    Product, NegotiationSettings, Conversation, Message, 
    MerchantActivity, ProductImage, ProductVideo, ProductVariation,
    Review, Category, SubCategory, Shop
)

# Configuration du logger
logger = logging.getLogger(__name__)

class OpenRouterClient:
    """
    Client HTTP simple pour OpenRouter pour éviter les problèmes de compatibilité
    """
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://deanna-ecommerce.com",
            "X-Title": "DEANNA E-commerce",
        }
    
    def is_configured(self):
        """Vérifie si le client est correctement configuré"""
        return bool(self.api_key)
    
    def chat_completion(self, messages, model="mistralai/mistral-small-3.1-24b-instruct:free", max_tokens=150, temperature=0.7):
        """
        Envoie une requête de chat completion à l'API OpenRouter
        """
        if not self.is_configured():
            raise Exception("Clé API OpenRouter non configurée")
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30  # 30 secondes timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            elif response.status_code == 401:
                raise Exception("Clé API invalide - vérifiez votre clé OpenRouter")
            elif response.status_code == 429:
                raise Exception("Quota API épuisé - vérifiez votre compte OpenRouter")
            else:
                raise Exception(f"Erreur API {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            raise Exception("Timeout de l'API OpenRouter")
        except requests.exceptions.ConnectionError:
            raise Exception("Erreur de connexion à l'API OpenRouter")
        except Exception as e:
            raise Exception(f"Erreur inconnue: {str(e)}")

# Instance globale du client
openrouter_client = OpenRouterClient()

def should_use_ai(conversation):
    """
    Détermine si l'IA doit répondre en fonction de l'activité réelle du commerçant
    """
    try:
        # Vérifie si la négociation IA est activée pour cette boutique
        try:
            negotiation_settings = NegotiationSettings.objects.get(shop=conversation.product.shop)
            if not negotiation_settings.is_active:
                logger.debug(f"❌ Négociation IA désactivée pour {conversation.merchant}")
                return False
        except NegotiationSettings.DoesNotExist:
            logger.debug(f"❌ Paramètres de négociation non trouvés pour {conversation.merchant.shop}")
            return False

        # Vérifie l'activité du commerçant
        try:
            activity = MerchantActivity.objects.get(merchant=conversation.merchant)
            
            # L'IA n'intervient PAS si :
            # 1. Le commerçant est en ligne ET actif récemment (moins de 2 minutes)
            if activity.is_online and activity.minutes_since_last_seen < 2:
                logger.debug(f"⏸️ Commerçant {conversation.merchant} en ligne et actif - IA n'intervient pas")
                return False
            
            # 2. Le commerçant a été actif dans le chat récemment (moins de 10 minutes)
            recent_merchant_messages = Message.objects.filter(
                conversation=conversation,
                sender=conversation.merchant.user,
                timestamp__gte=timezone.now() - timedelta(minutes=10)
            )
            if recent_merchant_messages.exists():
                logger.debug(f"⏸️ Commerçant {conversation.merchant} actif dans le chat - IA n'intervient pas")
                return False
                
        except MerchantActivity.DoesNotExist:
            # Si pas d'info d'activité, l'IA peut intervenir
            logger.debug(f"✅ Aucune activité trouvée pour {conversation.merchant} - IA peut intervenir")
            pass
            
        # L'IA intervient seulement si toutes les conditions sont remplies
        logger.info(f"✅ IA autorisée à répondre pour la conversation {conversation.id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur dans should_use_ai: {e}")
        return False

def extract_price_from_message(message):
    """
    Extrait un prix d'un message texte avec plusieurs motifs
    """
    if not message:
        return None
        
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
        r'(\d+)\s*mille',
        r'(\d+(?:\.\d+)?)\s*$'
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            try:
                price_str = match.group(1).replace(',', '.')
                price = Decimal(price_str)
                
                # Validation du prix raisonnable
                if price > 0 and price < 10000000:  # Entre 0 et 10 millions
                    logger.debug(f"💰 Prix extrait: {price} CFA")
                    return price
            except (InvalidOperation, ValueError) as e:
                logger.debug(f"⚠️ Erreur conversion prix: {e}")
                continue
    
    logger.debug("❌ Aucun prix valide trouvé dans le message")
    return None

def is_negotiation_message(message):
    """
    Détermine si le message concerne une négociation de prix
    """
    if not message:
        return False
        
    negotiation_keywords = [
        'prix', 'cher', 'coût', 'tarif', 'proposition', 'offre', 
        'négocier', 'marchander', 'discuter', 'réduction', 'rabais',
        'solde', 'promotion', 'discount', 'baisser', 'réduire',
        'marchandage', 'arranger', 'concéder', 'discount', 'bon prix',
        'dernier prix', 'meilleur prix', 'prix final', 'trop cher',
        'moins cher', 'réduis', 'baisse', 'affaire', 'marge'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in negotiation_keywords)

def is_technical_question(message):
    """
    Détermine si le message est une question technique sur le produit
    """
    if not message:
        return False
        
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
        r'nettoyage',
        r'livraison',
        r'retour',
        r'garantie'
    ]
    
    message_lower = message.lower()
    return any(re.search(pattern, message_lower) for pattern in question_patterns)

def is_greeting_message(message):
    """
    Détermine si le message est une salutation
    """
    if not message:
        return False
        
    greeting_patterns = [
        r'bonjour',
        r'bonsoir',
        r'salut',
        r'coucou',
        r'hello',
        r'hi ',
        r'ça va',
        r'cv ',
        r'yo',
        r'bjr',
        r'slt'
    ]
    
    message_lower = message.lower()
    return any(re.search(pattern, message_lower) for pattern in greeting_patterns)

def build_product_context(product):
    """
    Construit un contexte détaillé sur le produit pour l'IA
    """
    try:
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
        variations = product.variations.filter(is_active=True)
        if variations.exists():
            context += "\n🎨 VARIATIONS DISPONIBLES :\n"
            for variation in variations:
                variation_price = product.price + variation.price_modifier
                context += f"- {variation.type} : {variation.value} "
                if variation.price_modifier != 0:
                    context += f"(+{variation.price_modifier} CFA) "
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
        
        return context
        
    except Exception as e:
        logger.error(f"❌ Erreur dans build_product_context: {e}")
        return f"Produit: {product.name}, Prix: {product.price} CFA"

def get_negotiation_parameters(conversation):
    """
    Récupère les paramètres de négociation pour une conversation
    """
    try:
        negotiation_settings = NegotiationSettings.objects.get(shop=conversation.product.shop)
        min_price = negotiation_settings.min_price_threshold
        max_discount = negotiation_settings.max_discount_percentage
        
        # Si pas de prix minimum défini, calculer automatiquement (70% du prix)
        if not min_price or min_price == 0:
            min_price = Decimal(conversation.product.price * Decimal('0.7'))
        
        return {
            'min_price': min_price,
            'max_discount': max_discount or Decimal('10.00'),
            'original_price': conversation.product.price
        }
    except NegotiationSettings.DoesNotExist:
        return {
            'min_price': Decimal(conversation.product.price * Decimal('0.7')),
            'max_discount': Decimal('10.00'),
            'original_price': conversation.product.price
        }

def analyze_user_intent(message, user_price_offer=None):
    """
    Analyse l'intention de l'utilisateur à partir de son message
    """
    intent = {
        'type': 'general',
        'confidence': 0.5,
        'needs_response': True
    }
    
    if not message:
        return intent
    
    message_lower = message.lower()
    
    # Détection de la négociation
    if user_price_offer is not None:
        intent.update({
            'type': 'price_negotiation',
            'confidence': 0.9,
            'price_offer': user_price_offer
        })
    elif is_negotiation_message(message):
        intent.update({
            'type': 'negotiation_inquiry',
            'confidence': 0.8
        })
    elif is_technical_question(message):
        intent.update({
            'type': 'technical_question',
            'confidence': 0.7
        })
    elif is_greeting_message(message):
        intent.update({
            'type': 'greeting',
            'confidence': 0.9
        })
    elif 'merci' in message_lower:
        intent.update({
            'type': 'thanks',
            'confidence': 0.8
        })
    elif any(word in message_lower for word in ['disponible', 'stock', 'livraison']):
        intent.update({
            'type': 'logistics',
            'confidence': 0.7
        })
    
    return intent

def generate_ai_response(product, user_message, conversation, user_price_offer=None):
    """
    Génère une réponse IA en fonction du contexte et de l'intention de l'utilisateur
    """
    # Analyse de l'intention
    intent = analyze_user_intent(user_message, user_price_offer)
    negotiation_params = get_negotiation_parameters(conversation)
    product_context = build_product_context(product)
    
    # Construction du prompt en fonction de l'intention
    if intent['type'] == 'price_negotiation':
        return handle_price_negotiation(product, user_price_offer, negotiation_params, conversation)
    elif intent['type'] == 'negotiation_inquiry':
        return handle_negotiation_inquiry(product, user_message, negotiation_params, conversation)
    elif intent['type'] == 'technical_question':
        return handle_technical_question(product, user_message, conversation)
    elif intent['type'] == 'greeting':
        return handle_greeting(conversation, product)
    elif intent['type'] == 'thanks':
        return handle_thanks()
    elif intent['type'] == 'logistics':
        return handle_logistics_question(product, user_message)
    else:
        return handle_general_message(conversation, product, user_message)

def handle_price_negotiation(product, user_price_offer, negotiation_params, conversation):
    """
    Gère la négociation de prix
    """
    original_price = negotiation_params['original_price']
    min_price = negotiation_params['min_price']
    
    if user_price_offer >= original_price:
        return f"🎉 Excellente nouvelle ! J'accepte votre offre de {user_price_offer} CFA. Le produit '{product.name}' est à vous !"
    
    elif user_price_offer >= min_price:
        # Calculer un prix intermédiaire
        counter_offer = (user_price_offer + original_price) / 2
        counter_offer = counter_offer.quantize(Decimal('0.01'))
        
        return f"💰 Je apprécie votre offre de {user_price_offer} CFA. Que diriez-vous de {counter_offer} CFA ? C'est un excellent compromis pour ce produit de qualité !"
    
    else:
        return f"⚖️ Je comprends votre budget, mais {user_price_offer} CFA est en dessous de mon prix minimum de {min_price} CFA. Je peux vous proposer {min_price} CFA si cela vous convient mieux."

def handle_negotiation_inquiry(product, user_message, negotiation_params, conversation):
    """
    Gère les demandes de négociation
    """
    merchant_name = conversation.merchant.first_name
    
    responses = [
        f"🔍 Je comprends que vous souhaitez discuter du prix. Le produit '{product.name}' est actuellement à {product.price} CFA. Avez-vous un budget spécifique en tête ?",
        f"💬 Je suis ouvert à la discussion ! Le prix de '{product.name}' est {product.price} CFA. Quelle offre envisagez-vous ?",
        f"🎯 Merci pour votre intérêt ! Le prix affiché pour '{product.name}' est {product.price} CFA. Je suis prêt à trouver un arrangement qui convienne à nous deux.",
    ]
    
    import random
    return random.choice(responses)

def handle_technical_question(product, user_message, conversation):
    """
    Gère les questions techniques
    """
    return f"🔧 Merci pour votre question technique concernant '{product.name}'. Le commerçant {conversation.merchant.first_name} vous fournira une réponse détaillée dès son retour. En attendant, n'hésitez pas à consulter les photos et descriptions disponibles !"

def handle_greeting(conversation, product):
    """
    Gère les salutations
    """
    merchant_name = conversation.merchant.first_name
    
    greetings = [
        f"👋 Bonjour ! Je suis l'assistant de {merchant_name}. Je vous aide en attendant son retour. Vous regardez '{product.name}' à {product.price} CFA. Comment puis-je vous aider ?",
        f"🛍️ Bienvenue ! {merchant_name} est actuellement indisponible, mais je peux vous aider avec '{product.name}'. Le prix est de {product.price} CFA. Avez-vous des questions ?",
        f"💼 Bonjour ! Je suis le assistant commercial de {merchant_name}. Le produit '{product.name}' est disponible au prix de {product.price} CFA. Que souhaitez-vous savoir ?",
    ]
    
    import random
    return random.choice(greetings)

def handle_thanks():
    """
    Gère les remerciements
    """
    return "🤝 Je vous en prie ! N'hésitez pas si vous avez d'autres questions. Le commerçant vous contactera bientôt pour finaliser votre achat."

def handle_logistics_question(product, user_message):
    """
    Gère les questions logistiques
    """
    if 'disponible' in user_message.lower() or 'stock' in user_message.lower():
        if product.stock > 0:
            return f"✅ Oui, le produit '{product.name}' est en stock ({product.stock} unités disponibles)."
        else:
            return f"❌ Désolé, le produit '{product.name}' est actuellement en rupture de stock."
    
    elif 'livraison' in user_message.lower():
        return "🚚 Les détails de livraison (frais, délais) vous seront communiqués par le commerçant lors de la finalisation de la commande."
    
    else:
        return "📦 Pour les questions de disponibilité et livraison, le commerçant vous donnera toutes les informations nécessaires à son retour."

def handle_general_message(conversation, product, user_message):
    """
    Gère les messages généraux
    """
    return f"💬 Merci pour votre message concernant '{product.name}'. Le commerçant {conversation.merchant.first_name} vous répondra personnellement très soon."

def get_ai_negotiation_response(product: Product, user_message: str, conversation: Conversation):
    """
    Point d'entrée principal pour obtenir une réponse IA de négociation
    """
    # Vérification préalable
    if not should_use_ai(conversation):
        logger.debug("⏸️ IA non autorisée à répondre")
        return None

    # Vérification de la configuration OpenRouter
    if not openrouter_client.is_configured():
        logger.error("❌ OpenRouter non configuré - utilisation du mode secours")
        return generate_ai_response(product, user_message, conversation)

    # Extraction du prix
    user_price_offer = extract_price_from_message(user_message)
    
    try:
        # Construction du contexte
        product_context = build_product_context(product)
        negotiation_params = get_negotiation_parameters(conversation)
        intent = analyze_user_intent(user_message, user_price_offer)
        
        # Construction des messages pour l'IA
        system_prompt = f"""Tu es {conversation.merchant.first_name}, assistant commercial intelligent pour la boutique "{conversation.product.shop.description}".

{product_context}

TON RÔLE :
- Tu assistes les clients en l'absence du commerçant
- Tu es courtois, professionnel et serviable
- Tu peux discuter des prix dans une certaine limite
- Tu ne prends pas de décisions définitives

STYLE DE RÉPONSE :
- Réponses courtes (1-2 phrases maximum)
- Ton conversationnel et amical
- Emojis occasionnels pour la convivialité
- Langage simple et accessible

IMPORTANT :
- Ne dis jamais que tu es une IA
- Présente-toi comme l'assistant du commerçant
- Encourage toujours le client à attendre le retour du commerçant pour les décisions finales"""

        user_prompt = f"Message du client : {user_message}"
        
        if user_price_offer:
            user_prompt += f"\n\nLe client a proposé le prix de : {user_price_offer} CFA"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Appel à l'API
        logger.info(f"🔗 Appel API OpenRouter pour conversation {conversation.id}")
        ai_response = openrouter_client.chat_completion(
            messages=messages,
            max_tokens=120,
            temperature=0.7
        )
        
        logger.info(f"✅ Réponse IA générée: {ai_response}")
        return ai_response

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'appel IA: {e}")
        # Retour au mode secours en cas d'erreur
        return generate_ai_response(product, user_message, conversation, user_price_offer)

def get_fallback_response(product, user_message, conversation):
    """
    Réponse de secours quand l'IA n'est pas disponible
    """
    user_price_offer = extract_price_from_message(user_message)
    return generate_ai_response(product, user_message, conversation, user_price_offer)

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
                logger.info(f"✅ Nouvelle activité créée pour {user.merchant}")
            else:
                logger.debug(f"🔄 Activité mise à jour pour {user.merchant}")
                
            activity.save()
            return activity
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour activité pour {user.merchant}: {e}")
    
    return None

def get_merchant_status(merchant):
    """
    Retourne le statut détaillé d'un commerçant
    """
    try:
        activity = MerchantActivity.objects.get(merchant=merchant)
        
        if not hasattr(activity, 'minutes_since_last_seen'):
            # Calcul manuel si la propriété n'existe pas
            minutes_since_seen = (timezone.now() - activity.last_seen).total_seconds() / 60
        else:
            minutes_since_seen = activity.minutes_since_last_seen
        
        if activity.is_online:
            if minutes_since_seen < 1:
                return {
                    'status': 'en_ligne_actif',
                    'label': '🟢 En ligne',
                    'description': 'Connecté et actif',
                    'can_use_ai': False
                }
            elif minutes_since_seen < 3:
                return {
                    'status': 'en_ligne_inactif',
                    'label': '🟡 En ligne',
                    'description': 'Connecté mais inactif',
                    'can_use_ai': False
                }
            else:
                return {
                    'status': 'en_ligne_absent',
                    'label': '🟠 Absent',
                    'description': 'Connecté mais absent',
                    'can_use_ai': True
                }
        else:
            if minutes_since_seen < 5:
                return {
                    'status': 'hors_ligne_recent',
                    'label': '🔴 Hors ligne',
                    'description': 'Déconnecté récemment',
                    'can_use_ai': True
                }
            else:
                return {
                    'status': 'hors_ligne',
                    'label': '🔴 Hors ligne',
                    'description': 'Déconnecté',
                    'can_use_ai': True
                }
                
    except MerchantActivity.DoesNotExist:
        return {
            'status': 'inconnu',
            'label': '⚫ Statut inconnu',
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
        'shop_name': conversation.merchant.shop.description or "Boutique",
        'openrouter_configured': openrouter_client.is_configured()
    }

def test_ai_connection():
    """
    Teste la connexion à l'API OpenRouter
    """
    if not openrouter_client.is_configured():
        return {
            'success': False,
            'message': '❌ Clé API OpenRouter non configurée',
            'details': 'Vérifiez la variable d\'environnement OPENROUTER_API_KEY'
        }
    
    try:
        test_response = openrouter_client.chat_completion(
            messages=[{"role": "user", "content": "Réponds simplement 'TEST OK'"}],
            max_tokens=10,
            temperature=0.1
        )
        
        return {
            'success': True,
            'message': '✅ Connexion OpenRouter fonctionnelle',
            'response': test_response,
            'details': 'L\'IA est correctement configurée'
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': '❌ Erreur de connexion OpenRouter',
            'details': str(e)
        }

# Initialisation au chargement du module
logger.info("🔄 Initialisation des services IA...")
if openrouter_client.is_configured():
    logger.info("✅ Service OpenRouter configuré")
else:
    logger.warning("⚠️ Service OpenRouter non configuré - mode secours activé")