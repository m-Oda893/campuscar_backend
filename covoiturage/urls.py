from django.urls import path

from .views import (
    ConnexionView, InscriptionView,
    TrajetCreerView, TrajetRechercheView, MesTrajetsView,
)

urlpatterns = [
    path('inscription/', InscriptionView.as_view(), name='inscription'),
    path('connexion/', ConnexionView.as_view(), name='connexion'),
    path('trajets/', TrajetCreerView.as_view(), name='trajet-creer'),
    path('trajets/recherche/', TrajetRechercheView.as_view(), name='trajet-recherche'),
    path('trajets/mes-trajets/', MesTrajetsView.as_view(), name='mes-trajets'),
]