from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from .models import Utilisateur, Trajet , Reservation , Voiture
from .serializers import InscriptionSerializer, ReservationSerializer, UtilisateurSerializer, TrajetSerializer , VoitureSerializer
from .serializers import InscriptionSerializer, UtilisateurSerializer
from .serializers import ReservationSerializer




#VUE UTILISATEUR(INSCRIPTION, CONNEXION)
class InscriptionView(generics.CreateAPIView):
    serializer_class = InscriptionSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'utilisateur': serializer.data},
            status=status.HTTP_201_CREATED,
        )


class ConnexionView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        login = (request.data.get('login') or '').strip()
        password = request.data.get('password') or ''

        if not login or not password:
            return Response(
                {'detail': "Identifiant et mot de passe requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = Utilisateur.objects.filter(
            Q(email__iexact=login) | Q(identifiant=login)
        ).first()

        if user is None or not user.check_password(password) or not user.is_active:
            return Response(
                {'detail': "Identifiants incorrects."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'utilisateur': UtilisateurSerializer(user).data,
        })


    


#VUE VOITURE
class VoitureListeCreerView(generics.ListCreateAPIView):
    """GET : mes voitures. POST : j'ajoute une voiture."""
    serializer_class = VoitureSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Seulement MES voitures : personne ne voit celles des autres
        return Voiture.objects.filter(proprietaire=self.request.user)

    def perform_create(self, serializer):
        # Le propriétaire est l'utilisateur connecté, l'appli ne l'envoie pas
        serializer.save(proprietaire=self.request.user)





#VUE TRAJET
class TrajetCreerView(generics.CreateAPIView):
    """Le chauffeur propose un trajet."""
    serializer_class = TrajetSerializer
    authentication_classes = [TokenAuthentication]   # lit le token envoyé par l'appli
    permission_classes = [permissions.IsAuthenticated]  # refuse si pas connecté

    def perform_create(self, serializer):
        # Le chauffeur est l'utilisateur connecté
        serializer.save(chauffeur=self.request.user)


class TrajetRechercheView(generics.ListAPIView):
    """Le passager cherche des trajets (filtres facultatifs)."""
    serializer_class = TrajetSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # On part des trajets encore ouverts, avec des places, et pas dans le passé
        trajets = Trajet.objects.filter(
            statut='ouvert',
            places_dispo__gt=0,
            date_depart__gte=timezone.localdate(),
        ).exclude(chauffeur=self.request.user)  # on ne montre pas mes propres trajets
         
        

        # Filtres lus dans l'adresse : /trajets/recherche/?depart=ucad&arrivee=pikine&date=2026-10-20
        depart = self.request.query_params.get('depart')
        arrivee = self.request.query_params.get('arrivee')
        jour = self.request.query_params.get('date')

        if depart:
            trajets = trajets.filter(depart__icontains=depart)   # contient ce texte
        if arrivee:
            trajets = trajets.filter(arrivee__icontains=arrivee)
        if jour:
            trajets = trajets.filter(date_depart=jour)

        return trajets.order_by('date_depart', 'heure_depart')


class MesTrajetsView(generics.ListAPIView):
    """Liste des trajets que je propose."""
    serializer_class = TrajetSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Trajet.objects.filter(
            chauffeur=self.request.user
        ).order_by('-date_depart', '-heure_depart')







#VUE RESERVATION
class ReservationCreerView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        trajet_id = request.data.get('trajet')
        if not trajet_id:
            return Response({'detail': "Trajet manquant."}, status=400)

        trajet = get_object_or_404(Trajet, pk=trajet_id)

        # Règle 1 : pas de réservation sur son propre trajet
        if trajet.chauffeur == request.user:
            return Response(
                {'detail': "Tu ne peux pas réserver ton propre trajet."},
                status=400,
            )
        # Règle 2 : le trajet doit être ouvert et avoir de la place
        if trajet.statut != 'ouvert' or trajet.places_dispo <= 0:
            return Response(
                {'detail': "Ce trajet n'est plus disponible."}, status=400
            )
        # Règle 3 : pas de double demande
        deja = Reservation.objects.filter(
            trajet=trajet,
            passager=request.user,
            statut__in=['en_attente', 'confirmee'],
        ).exists()
        if deja:
            return Response(
                {'detail': "Tu as déjà une demande pour ce trajet."},
                status=400,
            )

        reservation = Reservation.objects.create(
            trajet=trajet, passager=request.user
        )
        return Response(
            ReservationSerializer(reservation, context={'request': request}).data, status=201
        )



class MesReservationsView(generics.ListAPIView):
    """Les réservations que J'AI faites (côté passager)."""
    serializer_class = ReservationSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(passager=self.request.user)


class ReservationsRecuesView(generics.ListAPIView):
    """Les demandes faites SUR MES trajets (côté chauffeur)."""
    serializer_class = ReservationSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(trajet__chauffeur=self.request.user)


class ReservationValiderView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        # Seul le chauffeur du trajet peut accepter
        if reservation.trajet.chauffeur != request.user:
            return Response({'detail': "Action non autorisée."}, status=403)
        try:
            reservation.valider()  # la méthode du modèle fait les vérifications
        except ValueError as erreur:
            return Response({'detail': str(erreur)}, status=400)
        return Response(ReservationSerializer(reservation, context={'request': request}).data)


class ReservationRefuserView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        if reservation.trajet.chauffeur != request.user:
            return Response({'detail': "Action non autorisée."}, status=403)
        if reservation.statut != 'en_attente':
            return Response(
                {'detail': "Cette demande n'est plus en attente."}, status=400
            )
        reservation.statut = 'refusee'
        reservation.save()
        return Response(ReservationSerializer(reservation, context={'request': request}).data)


class ReservationAnnulerView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        # Seul le passager qui a réservé peut annuler
        if reservation.passager != request.user:
            return Response({'detail': "Action non autorisée."}, status=403)
        try:
            reservation.annuler()
        except ValueError as erreur:
            return Response({'detail': str(erreur)}, status=400)
        return Response(ReservationSerializer(reservation, context={'request': request}).data)
       