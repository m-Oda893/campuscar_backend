from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import Utilisateur, Trajet


class InscriptionSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'first_name', 'last_name', 'date_naissance', 'telephone',
            'identifiant', 'email', 'est_personnel', 'photo', 'password',
        ]

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate(self, data):
        if not data.get('email') and not data.get('identifiant'):
            raise serializers.ValidationError(
                "Renseignez un email ou un identifiant."
            )
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        email = validated_data.get('email') or None
        identifiant = validated_data.get('identifiant') or None
        validated_data['email'] = email
        validated_data['identifiant'] = identifiant
        validated_data['username'] = email or identifiant

        user = Utilisateur(**validated_data)
        user.set_password(password)
        user.save()
        return user



class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = [
            'id', 'first_name', 'last_name', 'date_naissance', 'telephone',
            'identifiant', 'email', 'est_personnel', 'photo', 'note',
        ]       




from datetime import date


class TrajetSerializer(serializers.ModelSerializer):
    # Le chauffeur est rempli par le serveur, l'appli ne l'envoie pas.
    # On affiche ses infos en lecture seule.
    chauffeur = UtilisateurSerializer(read_only=True)

    class Meta:
        model = Trajet
        fields = [
            'id', 'chauffeur', 'depart', 'depart_lat', 'depart_lng',
            'arrivee', 'arrivee_lat', 'arrivee_lng', 'date_depart',
            'heure_depart', 'prix_par_place', 'places_dispo',
            'statut', 'cree_le',
        ]
        # Ces champs ne peuvent pas être modifiés par l'appli
        read_only_fields = ['statut', 'cree_le']

    def validate_date_depart(self, value):
        # Refuse un trajet dans le passé
        if value < date.today():
            raise serializers.ValidationError("La date est déjà passée.")
        return value

    def validate_places_dispo(self, value):
        # Il faut proposer au moins une place
        if value < 1:
            raise serializers.ValidationError("Proposez au moins une place.")
        return value 