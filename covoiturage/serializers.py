from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import Utilisateur


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