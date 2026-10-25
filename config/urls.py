from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('covoiturage.urls')),
]

# Sert les photos envoyées (/media/...) pendant le développement.
# Ne fonctionne que si DEBUG = True, ce qui est ton cas.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)