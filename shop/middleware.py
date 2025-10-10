# Fichier : shop/middleware.py
from django.utils import timezone
from .models import MerchantActivity
import logging

logger = logging.getLogger(__name__)

class MerchantActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Traite la requête d'abord
        response = self.get_response(request)
        
        # Met à jour l'activité après la requête
        self.track_merchant_activity(request)
        
        return response
    
    def track_merchant_activity(self, request):
        """Met à jour l'activité du commerçant connecté"""
        if request.user.is_authenticated and hasattr(request.user, 'merchant'):
            try:
                session_key = request.session.session_key
                MerchantActivity.update_activity(
                    merchant=request.user.merchant,
                    session_key=session_key
                )
                
                logger.debug(f"Activité mise à jour pour {request.user.merchant}")
                
            except Exception as e:
                logger.error(f"Erreur suivi activité pour {request.user.merchant}: {e}")