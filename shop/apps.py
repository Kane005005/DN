# shop/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shop'
    
def ready(self):
    # Commente tout le code des tâches pour l'instant
    # try:
    #     from .tasks import update_merchant_online_status, check_chat_activity
    #     # ...
    # except Exception as e:
    #     logger.error(f"Erreur démarrage tâches: {e}")
    pass