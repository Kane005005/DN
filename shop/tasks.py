# Fichier : shop/tasks.py
from background_task import background
from django.utils import timezone
from datetime import timedelta
from django.contrib.sessions.models import Session
from .models import MerchantActivity
import logging

logger = logging.getLogger(__name__)

@background(schedule=30)  # Exécuter toutes les 30 secondes
def update_merchant_online_status():
    """
    Tâche principale qui met à jour le statut en ligne/hors ligne des commerçants
    """
    try:
        # Seuils de temps
        online_threshold = timezone.now() - timedelta(minutes=2)  # 2 minutes = en ligne
        offline_threshold = timezone.now() - timedelta(minutes=5)  # 5 minutes = hors ligne
        
        # Marquer comme hors ligne les commerçants inactifs
        offline_count = MerchantActivity.objects.filter(
            last_seen__lt=offline_threshold,
            is_online=True
        ).update(is_online=False)
        
        # Marquer comme en ligne les commerçants actifs récemment
        online_count = MerchantActivity.objects.filter(
            last_seen__gte=online_threshold,
            is_online=False
        ).update(is_online=True)
        
        # Nettoyer les sessions expirées
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        expired_count = expired_sessions.count()
        expired_sessions.delete()
        
        logger.info(f"Statut mis à jour: {online_count} en ligne, {offline_count} hors ligne, {expired_count} sessions expirées")
        
    except Exception as e:
        logger.error(f"Erreur dans update_merchant_online_status: {e}")

@background(schedule=60)  # Exécuter toutes les minutes
def check_chat_activity():
    """
    Vérifie l'activité spécifique dans les conversations
    """
    try:
        from .models import Message, Conversation
        
        # Seuil pour considérer un commerçant comme "actif dans le chat"
        chat_active_threshold = timezone.now() - timedelta(minutes=10)
        
        # Trouver les commerçants qui ont envoyé des messages récemment
        recent_chat_merchants = Message.objects.filter(
            timestamp__gte=chat_active_threshold,
            sender__merchant__isnull=False
        ).values_list('sender__merchant', flat=True).distinct()
        
        # Mettre à jour le statut d'activité dans le chat
        MerchantActivity.objects.filter(merchant_id__in=recent_chat_merchants).update(is_active_in_chat=True)
        
        # Marquer comme inactifs ceux qui n'ont pas parlé récemment
        MerchantActivity.objects.exclude(merchant_id__in=recent_chat_merchants).update(is_active_in_chat=False)
        
        logger.info(f"Activité chat vérifiée: {len(recent_chat_merchants)} commerçants actifs")
        
    except Exception as e:
        logger.error(f"Erreur dans check_chat_activity: {e}")