from django.urls import path

from .views import (
    ConnexionView, DeconnexionView, InscriptionView, NotificationLueView, NotificationsListeView, NotificationsNonLuesView, NotificationsToutLireView, ProfilChauffeurView, ProfilView, ReservationNoterView, SignalementCreerView, TrajetAnnulerView,
    TrajetCreerView, TrajetModifierView, TrajetRechercheView, MesTrajetsView,
    ReservationCreerView, MesReservationsView, ReservationsRecuesView,
    ReservationValiderView, ReservationRefuserView, ReservationAnnulerView, TrajetTerminerView,
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
    path('profil/permis/', ProfilChauffeurView.as_view()),
    path('profil/', ProfilView.as_view(), name='profil'),
    path('trajets/<int:pk>/annuler/', TrajetAnnulerView.as_view()),
    path('trajets/<int:pk>/terminer/', TrajetTerminerView.as_view()),
    path('reservations/<int:pk>/noter/', ReservationNoterView.as_view()),
    path('trajets/<int:pk>/modifier/', TrajetModifierView.as_view()),
    path('deconnexion/', DeconnexionView.as_view()),
    path('notifications/', NotificationsListeView.as_view()),
    path('notifications/non-lues/', NotificationsNonLuesView.as_view()),
    path('notifications/tout-lire/', NotificationsToutLireView.as_view()), 
    path('notifications/<int:pk>/lue/', NotificationLueView.as_view()),
    path('signalements/', SignalementCreerView.as_view()),
    
]