from django.urls import path

from .views import (
    ConnexionView, InscriptionView,
    TrajetCreerView, TrajetRechercheView, MesTrajetsView,
    ReservationCreerView, MesReservationsView, ReservationsRecuesView,
    ReservationValiderView, ReservationRefuserView, ReservationAnnulerView,
    VoitureListeCreerView,
)

urlpatterns = [
    path('inscription/', InscriptionView.as_view(), name='inscription'),
    path('connexion/', ConnexionView.as_view(), name='connexion'),
    path('trajets/', TrajetCreerView.as_view(), name='trajet-creer'),
    path('trajets/recherche/', TrajetRechercheView.as_view(), name='trajet-recherche'),
    path('trajets/mes-trajets/', MesTrajetsView.as_view(), name='mes-trajets'),
    path('reservations/', ReservationCreerView.as_view()),
    path('reservations/mes-reservations/', MesReservationsView.as_view()),
    path('reservations/recues/', ReservationsRecuesView.as_view()),
    path('reservations/<int:pk>/valider/', ReservationValiderView.as_view()),
    path('reservations/<int:pk>/refuser/', ReservationRefuserView.as_view()),
    path('reservations/<int:pk>/annuler/', ReservationAnnulerView.as_view()),
    path('voitures/', VoitureListeCreerView.as_view()),
]