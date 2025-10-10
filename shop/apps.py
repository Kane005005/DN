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
            
            # Démarrez les tâches en arrière-plan seulement si elles ne tournent pas déjà
            if not update_merchant_online_status.tasks.exists():
                update_merchant_online_status(repeat=30)  # Répéter toutes les 30 secondes
                logger.info("Tâche update_merchant_online_status démarrée")
            
            if not check_chat_activity.tasks.exists():
                check_chat_activity(repeat=60)  # Répéter toutes les 60 secondes
                logger.info("Tâche check_chat_activity démarrée")
                
        except Exception as e:
            logger.error(f"Erreur démarrage tâches: {e}")