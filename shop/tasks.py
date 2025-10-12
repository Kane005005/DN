# shop/tasks.py (reste inchangé)
from django.utils import timezone
from datetime import timedelta
from django.contrib.sessions.models import Session
from .models import MerchantActivity, Message, Conversation
import logging

logger = logging.getLogger(__name__)

def update_merchant_online_status():
    """
    Tâche principale qui met à jour le statut en ligne/hors ligne des commerçants
    """
    try:
        # Ton code existant...
        online_threshold = timezone.now() - timedelta(minutes=2)
        offline_threshold = timezone.now() - timedelta(minutes=5)
        
        offline_count = MerchantActivity.objects.filter(
            last_seen__lt=offline_threshold,
            is_online=True
        ).update(is_online=False)
        
        online_count = MerchantActivity.objects.filter(
            last_seen__gte=online_threshold,
            is_online=False
        ).update(is_online=True)
        
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        expired_count = expired_sessions.count()
        expired_sessions.delete()
        
        logger.info(f"Statut mis à jour: {online_count} en ligne, {offline_count} hors ligne, {expired_count} sessions expirées")
        
    except Exception as e:
        logger.error(f"Erreur dans update_merchant_online_status: {e}")

def check_chat_activity():
    """
    Vérifie l'activité spécifique dans les conversations
    """
    try:
        # Ton code existant...
        chat_active_threshold = timezone.now() - timedelta(minutes=10)
        
        recent_chat_merchants = Message.objects.filter(
            timestamp__gte=chat_active_threshold,
            sender__merchant__isnull=False
        ).values_list('sender__merchant', flat=True).distinct()
        
        MerchantActivity.objects.filter(merchant_id__in=recent_chat_merchants).update(is_active_in_chat=True)
        MerchantActivity.objects.exclude(merchant_id__in=recent_chat_merchants).update(is_active_in_chat=False)
        
        logger.info(f"Activité chat vérifiée: {len(recent_chat_merchants)} commerçants actifs")
        
    except Exception as e:
        logger.error(f"Erreur dans check_chat_activity: {e}")