from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Utilisateur
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