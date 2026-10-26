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

from .models import Utilisateur, Trajet , Reservation , Voiture , Notification
from .serializers import InscriptionSerializer, ReservationSerializer, UtilisateurSerializer, TrajetSerializer , VoitureSerializer
from .serializers import InscriptionSerializer, UtilisateurSerializer , NotificationSerializer
from .serializers import ReservationSerializer
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from .models import ProfilChauffeur
from .serializers import ProfilChauffeurSerializer
from .matching import evaluer, parser_heure, trouver_zone
from .models import Zone



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
        if not self.request.user.est_chauffeur_verifie:
            raise PermissionDenied("Ton permis doit être vérifié avant d'ajouter une voiture.")
        # Le propriétaire est l'utilisateur connecté, l'appli ne l'envoie pas
        serializer.save(proprietaire=self.request.user)





#VUE TRAJET
class TrajetCreerView(generics.CreateAPIView):
    """Le chauffeur propose un trajet."""
    serializer_class = TrajetSerializer
    authentication_classes = [TokenAuthentication]   # lit le token envoyé par l'appli
    permission_classes = [permissions.IsAuthenticated]  # refuse si pas connecté

    def perform_create(self, serializer):
        if not self.request.user.est_chauffeur_verifie:
            raise PermissionDenied("Ton permis doit être vérifié avant de publier un trajet.")
        # Le chauffeur est l'utilisateur connecté
        serializer.save(chauffeur=self.request.user)


class TrajetRechercheView(generics.ListAPIView):
    """Le passager cherche des trajets : fenêtre horaire + proximité géographique."""
    serializer_class = TrajetSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        maintenant = timezone.localtime()
        trajets = Trajet.objects.filter(
            statut='ouvert', places_dispo__gt=0,
        ).filter(
            # un jour futur, OU aujourd'hui avec une heure pas encore passée
            Q(date_depart__gt=maintenant.date()) |
            Q(date_depart=maintenant.date(), heure_depart__gt=maintenant.time())
        ).exclude(chauffeur=self.request.user).select_related('chauffeur', 'voiture')

        jour = self.request.query_params.get('date')
        if jour:
            trajets = trajets.filter(date_depart=jour)
        return trajets.order_by('date_depart', 'heure_depart')

    def list(self, request, *args, **kwargs):
        depart = (request.query_params.get('depart') or '').strip()
        arrivee = (request.query_params.get('arrivee') or '').strip()
        heure = parser_heure(request.query_params.get('heure'))

        # On traduit ce que le passager a tapé en zones connues (ou None)
        zones = list(Zone.objects.all())
        zone_dep = trouver_zone(depart, zones)
        zone_arr = trouver_zone(arrivee, zones)

        retenus = []
        for trajet in self.get_queryset():
            info = evaluer(trajet, depart, arrivee, zone_dep, zone_arr, heure)
            if info is not None:
                retenus.append((trajet, info))

        # Avec un critère : meilleur score d'abord (le tri garde l'ordre
        # chronologique en cas d'égalité). Sans critère : ordre chronologique.
        if depart or arrivee or heure is not None:
            retenus.sort(key=lambda x: x[1]['score'])

        resultat = []
        for trajet, info in retenus:
            ligne = dict(TrajetSerializer(
                trajet, context=self.get_serializer_context()
            ).data)
            ligne['match'] = {
                'km': info['km'],
                'ecart_minutes': info['ecart_minutes'],
                'geo': info['geo'],
            }
            resultat.append(ligne)
        return Response(resultat)
    


class MesTrajetsView(generics.ListAPIView):
    """Liste des trajets que je propose."""
    serializer_class = TrajetSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Trajet.objects.filter(
            chauffeur=self.request.user
        ).order_by('-date_depart', '-heure_depart')



class TrajetAnnulerView(APIView):
    """Le chauffeur annule l'un de SES trajets."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        trajet = get_object_or_404(Trajet, pk=pk)
        # Seul le chauffeur du trajet peut l'annuler
        if trajet.chauffeur != request.user:
            return Response({'detail': "Action non autorisée."}, status=403)
        try:
         trajet.annuler()
        except ValueError as erreur:
            return Response({'detail': str(erreur)}, status=400)
        return Response(TrajetSerializer(trajet, context={'request': request}).data)



class TrajetModifierView(APIView):
    """Le chauffeur modifie l'un de SES trajets (PATCH : seulement les champs envoyés)."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        trajet = get_object_or_404(Trajet, pk=pk)
        if trajet.chauffeur != request.user:
            return Response({'detail': "Action non autorisée."}, status=403)
        try:
            trajet.verifier_modifiable()
        except ValueError as erreur:
            return Response({'detail': str(erreur)}, status=400)
        # partial=True : on peut n'envoyer que les champs à changer
        serializer = TrajetSerializer(
            trajet, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)



class TrajetTerminerView(APIView):
    """Le chauffeur termine l'un de SES trajets."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        trajet = get_object_or_404(Trajet, pk=pk)
        if trajet.chauffeur != request.user:
            return Response({'detail': "Action non autorisée."}, status=403)
        try:
            trajet.terminer()
        except ValueError as erreur:
            return Response({'detail': str(erreur)}, status=400)
        return Response(TrajetSerializer(trajet, context={'request': request}).data)




    
    





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

        # Règle 2 bis : le trajet ne doit pas être déjà parti
        if trajet.depart_depasse():
            return Response({'detail': "Ce trajet est déjà parti."}, status=400)
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
        Notification.objects.create(
            destinataire=trajet.chauffeur, type='demande_recue',
            message=f"{request.user.first_name} demande une place pour {trajet.libelle()}.",
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
        Notification.objects.create(
            destinataire=reservation.passager, type='demande_refusee',
            message=f"Le chauffeur a refusé ta demande pour {reservation.trajet.libelle()}.",
        )
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


class ReservationNoterView(APIView):
    """Le passager note le chauffeur d'une réservation terminée."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        if reservation.passager != request.user:
            return Response({'detail': "Action non autorisée."}, status=403)
        try:
            note = int(request.data.get('note'))
        except (TypeError, ValueError):
            return Response({'detail': "Note manquante ou invalide."}, status=400)
        commentaire = (request.data.get('commentaire') or '').strip()
        try:
            reservation.noter(note, commentaire)
        except ValueError as erreur:
            return Response({'detail': str(erreur)}, status=400)
        return Response(ReservationSerializer(reservation, context={'request': request}).data)

    
       


#PROFIL
class ProfilView(generics.RetrieveAPIView):
    """Renvoie le profil complet de la personne CONNECTÉE, et de personne d'autre."""
    serializer_class = UtilisateurSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Pas d'id dans l'URL : on prend toujours l'utilisateur du token.
        # Impossible donc de lire le profil d'un autre en changeant un numéro.
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()

        # get_serializer() donne au serializer la requête (le "context"),
        # ce qui permet à Django de renvoyer l'URL complète de la photo
        data = dict(self.get_serializer(user).data)

        # Rôles déduits de ce que la personne a réellement fait
        est_chauffeur = (
            Voiture.objects.filter(proprietaire=user).exists()
            or Trajet.objects.filter(chauffeur=user).exists()
        )
        # Passager si elle a déjà réservé, ou par défaut si elle n'est pas chauffeur
        est_passager = (
            Reservation.objects.filter(passager=user).exists()
            or not est_chauffeur
        )

        roles = []
        if est_passager:
            roles.append('passager')
        if est_chauffeur:
            roles.append('chauffeur')
        data['roles'] = roles

        return Response(data)

    

#PERMIS
class ProfilChauffeurView(APIView):
    """GET : l'état de mon permis. POST : j'envoie mon permis (numéro + photo)."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # car il y a une photo

    def get(self, request):
        profil = getattr(request.user, 'profil_chauffeur', None)
        if profil is None:
            return Response({'statut': 'aucun'})
        data = dict(ProfilChauffeurSerializer(profil, context={'request': request}).data)
        data['statut'] = 'verifie' if profil.verifie else 'en_attente'
        return Response(data)

    def post(self, request):
        profil = getattr(request.user, 'profil_chauffeur', None)
        if profil is not None and profil.verifie:
            return Response({'detail': "Ton permis est déjà vérifié."}, status=400)
        # Si un profil existe déjà (en attente), on le remplace
        serializer = ProfilChauffeurSerializer(
            profil, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(utilisateur=request.user, verifie=False)
        return Response({**serializer.data, 'statut': 'en_attente'}, status=201)


    #DÉCONNEXION
class DeconnexionView(APIView):
    """Supprime le token : il ne peut plus servir, même s'il a été copié."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)




#NOTIFICATIONS
class NotificationsListeView(generics.ListAPIView):
    """Mes 50 dernières notifications."""
    serializer_class = NotificationSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(destinataire=self.request.user)[:50]


class NotificationsNonLuesView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        n = Notification.objects.filter(destinataire=request.user, lue=False).count()
        return Response({'non_lues': n})


class NotificationLueView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # Filtrer par destinataire : impossible de toucher celles des autres (404)
        notif = get_object_or_404(Notification, pk=pk, destinataire=request.user)
        notif.lue = True
        notif.save(update_fields=['lue'])
        return Response(NotificationSerializer(notif).data)


class NotificationsToutLireView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(destinataire=request.user, lue=False).update(lue=True)
        return Response(status=204)