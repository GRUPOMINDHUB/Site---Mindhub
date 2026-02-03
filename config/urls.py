"""
URL Configuration - Mindhub OS
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.usuarios.urls')),
    path('', include('apps.ia_engine.urls')),
    path('', include('apps.trilha.urls')),
    path('trilha/', include('apps.trilha.urls')), # Redundancia para compatibilidade
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
