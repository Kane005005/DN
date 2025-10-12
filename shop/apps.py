# shop/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shop'
    
    def ready(self):
        # Importez les tâches ici pour éviter les imports circulaires
        try:
            from .tasks import update_merchant_online_status, check_chat_activity
            
            # CORRECTION : Vérifie différemment si les tâches tournent
            # Cette méthode est plus fiable
            update_merchant_online_status(repeat=30, verbose_name="Update merchant status")
            check_chat_activity(repeat=60, verbose_name="Check chat activity")
            
            logger.info("Tâches background démarrées")
                
        except Exception as e:
            logger.error(f"Erreur démarrage tâches: {e}")