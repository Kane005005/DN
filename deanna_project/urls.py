# deanna_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Importe les paramètres
from django.conf.urls.static import static # Importe la fonction static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
]

# Sert les fichiers médias en mode développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
