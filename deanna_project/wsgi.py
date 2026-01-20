"""
Fichier WSGI pour PythonAnywhere
"""
import os
import sys

# Chemin vers votre projet
path = '/home/Deanna0025/DN'  # Remplacez 'username' par votre nom d'utilisateur PythonAnywhere
if path not in sys.path:
    sys.path.insert(0, path)

# Définir le module de settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'deanna_project.settings'

# Importer l'application Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()