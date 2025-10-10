# shop/services.py - Version de secours
import logging

logger = logging.getLogger(__name__)

def get_ai_negotiation_response(product, user_message, conversation):
    """
    Version temporaire sans aucune dépendance externe
    """
    try:
        user_msg = user_message.lower()
        
        if any(word in user_msg for word in ['bonjour', 'salut', 'hello', 'coucou']):
            return "Bonjour ! Je suis l'assistant commercial. Comment puis-je vous aider ?"
        
        elif any(word in user_msg for word in ['prix', 'coût', 'tarif', 'combien']):
            price = getattr(product, 'price', 'non spécifié')
            return f"Le prix de ce produit est {price} CFA."
        
        elif any(word in user_msg for word in ['disponible', 'stock']):
            stock = getattr(product, 'stock', 0)
            return f"Oui, nous avons {stock} unités disponibles."
        
        elif any(word in user_msg for word in ['merci']):
            return "Je vous en prie ! N'hésitez pas pour d'autres questions."
        
        else:
            return "Merci pour votre message. Le commerçant vous répondra rapidement."
            
    except Exception as e:
        return "Service momentanément indisponible. Réessayez plus tard."

def should_use_ai(conversation):
    """Toujours activé pour les tests"""
    return True

def update_merchant_activity(user):
    """Fonction vide pour l'instant"""
    return None

def get_merchant_status(merchant):
    """Statut par défaut"""
    return {
        'status': 'inconnu', 
        'can_use_ai': True,
        'label': 'Statut inconnu'
    }
