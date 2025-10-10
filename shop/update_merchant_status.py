# Fichier : shop/management/commands/update_merchant_status.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from shop.models import MerchantActivity

class Command(BaseCommand):
    help = 'Met à jour le statut en ligne des commerçants'

    def handle(self, *args, **options):
        # Considère comme "hors ligne" les commerçants non actifs depuis 5 minutes
        offline_threshold = timezone.now() - timedelta(minutes=5)
        
        MerchantActivity.objects.filter(
            last_seen__lt=offline_threshold,
            is_online=True
        ).update(is_online=False)
        
        self.stdout.write(
            self.style.SUCCESS('Statut des commerçants mis à jour avec succès')
        )