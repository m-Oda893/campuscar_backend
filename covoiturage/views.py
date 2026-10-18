from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication

from .models import Utilisateur, Trajet
from .serializers import InscriptionSerializer, UtilisateurSerializer, TrajetSerializer
from .serializers import InscriptionSerializer, UtilisateurSerializer






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