# Fichier : shop/services.py
import os
from decimal import Decimal
from openai import OpenAI
from .models import Product, NegotiationSettings, Conversation, Message

def get_ai_negotiation_response(product: Product, user_price_offer: Decimal, conversation: Conversation):
    """
    Appelle l'API d'OpenRouter pour générer une réponse de négociation de l'IA.
    """
    # Récupère la clé d'API depuis les variables d'environnement
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )

    # Récupère les paramètres de négociation du commerçant
    try:
        negotiation_settings = NegotiationSettings.objects.get(shop=conversation.merchant.shop)
        min_price = negotiation_settings.min_price_threshold
        max_discount_percentage = negotiation_settings.max_discount_percentage
    except NegotiationSettings.DoesNotExist:
        # Valeurs par défaut si les paramètres n'existent pas
        min_price = Decimal(product.price * Decimal('0.7'))
        max_discount_percentage = Decimal('10.00')

    # Prépare le prompt système
    system_prompt = (
        "Tu es un assistant de négociation pour un site e-commerce. "
        "Ton rôle est d'aider un client et un commerçant à trouver un prix d'accord. "
        f"Le prix initial du produit '{product.name}' est de {product.price} CFA. "
        f"Le prix minimum de vente est de {min_price} CFA. "
        f"La réduction maximale que tu peux offrir est de {max_discount_percentage}%. "
        "Si l'offre du client est inférieure au prix minimum, refuse poliment et propose le prix minimum. "
        "Si l'offre du client est raisonnable, fais une contre-offre. "
        "Si le client propose un prix supérieur ou égal au prix initial, accepte. "
        "Ne donne pas de prix finaux s'ils ne sont pas spécifiquement demandés. "
        "Réponds de manière concise et professionnelle en français. Ne propose que le prix ou une phrase courte, sans ajouter de phrases supplémentaires."
    )

    # C'est ICI que la variable 'conversation_history' est définie.
    # Elle n'est utilisée qu'à l'intérieur de cette fonction.
    conversation_history = [
        {"role": "system", "content": system_prompt}
    ]
    # Ajoute les messages existants
    for message in conversation.messages.order_by('timestamp'):
        role = "user" if message.sender == conversation.client else "assistant"
        conversation_history.append({"role": role, "content": message.text})
    
    # Ajoute la nouvelle offre du client
    conversation_history.append({"role": "user", "content": f"Ma proposition est de {user_price_offer} CFA."})

    # Appel à l'API d'OpenRouter
    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://8000-firebase-dn-1756411287077.cluster-cbeiita7rbe7iuwhvjs5zww2i4.cloudworkstations.dev",
                "X-Title": "DEANNA E-commerce",
            },
            model="deepseek/deepseek-chat-v3.1:free",
            messages=conversation_history,
            max_tokens=200
        )
        ai_message = completion.choices[0].message.content
        return ai_message
    except Exception as e:
        print(f"Erreur lors de l'appel à l'API de l'IA : {e}")
        return "Je suis désolé, je n'ai pas pu traiter votre requête pour le moment. Veuillez réessayer plus tard."