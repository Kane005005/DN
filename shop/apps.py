# shop/apps.py
from django.apps import AppConfig
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import sys

logger = logging.getLogger(__name__)

class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shop'
    
    def ready(self):
        # Évite de démarrer le scheduler pendant les commandes manage.py
        if 'runserver' in sys.argv or 'uwsgi' in sys.argv:
            self.start_scheduler()
    
    def start_scheduler(self):
        try:
            from .tasks import update_merchant_online_status, check_chat_activity
            
            # Crée le scheduler
            scheduler = BackgroundScheduler(daemon=True)
            
            # Ajoute la tâche de statut des commerçants (toutes les 30 secondes)
            scheduler.add_job(
                update_merchant_online_status,
                trigger=IntervalTrigger(seconds=30),
                id='update_merchant_status',
                name='Mise à jour statut commerçants',
                replace_existing=True,
                max_instances=1
            )
            
            # Ajoute la tâche d'activité chat (toutes les minutes)
            scheduler.add_job(
                check_chat_activity,
                trigger=IntervalTrigger(minutes=1),
                id='check_chat_activity',
                name='Vérification activité chat',
                replace_existing=True,
                max_instances=1
            )
            
            # Démarre le scheduler
            scheduler.start()
            logger.info("✅ APScheduler démarré avec succès")
            logger.info("📋 Tâches planifiées :")
            logger.info("   - Mise à jour statut commerçants : toutes les 30 secondes")
            logger.info("   - Vérification activité chat : toutes les minutes")
            
            # Arrête proprement le scheduler à la fermeture
            atexit.register(lambda: scheduler.shutdown(wait=False))
                
        except Exception as e:
            logger.error(f"❌ Erreur démarrage APScheduler: {e}")