from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import Reservation, Utilisateur, Trajet, Voiture
from datetime import date

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


#UTILISATEUR
class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = [
            'id', 'first_name', 'last_name', 'date_naissance', 'telephone',
            'identifiant', 'email', 'est_personnel', 'photo', 'note',
        ]       


class UtilisateurPublicSerializer(serializers.ModelSerializer):
    # Seulement ce que les AUTRES utilisateurs peuvent voir
    class Meta:
        model = Utilisateur
        fields = ['id', 'first_name', 'last_name', 'photo', 'note']



#VOITURE
class VoitureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voiture
        fields = ['id', 'matricule', 'marque', 'modele', 'couleur', 'nbre_place']

    def validate_matricule(self, value):
        # On uniformise : "dk-123-ab " -> "DK-123-AB"
        value = value.strip().upper()
        if Voiture.objects.filter(matricule=value).exists():
            raise serializers.ValidationError("Cette plaque est déjà enregistrée.")
        return value

    def validate_nbre_place(self, value):
        # Places pour les passagers : entre 1 et 8
        if value < 1 or value > 8:
            raise serializers.ValidationError("Entre 1 et 8 places pour les passagers.")
        return value


    


class VoiturePublicSerializer(serializers.ModelSerializer):
    # Ce que les AUTRES voient : de quoi reconnaître la voiture, sans la plaque
    class Meta:
        model = Voiture
        fields = ['id', 'marque', 'modele', 'couleur']




#TRAJET
class TrajetSerializer(serializers.ModelSerializer):
    chauffeur = UtilisateurPublicSerializer(read_only=True)
    # Lecture : la voiture affichée aux autres
    voiture = VoiturePublicSerializer(read_only=True)
    # Écriture : l'appli envoie seulement le numéro de sa voiture
    voiture_id = serializers.PrimaryKeyRelatedField(
        queryset=Voiture.objects.all(), source='voiture', write_only=True
    )

    class Meta:
        model = Trajet
        fields = [
            'id', 'chauffeur', 'voiture', 'voiture_id',
            'depart', 'depart_lat', 'depart_lng',
            'arrivee', 'arrivee_lat', 'arrivee_lng', 'date_depart',
            'heure_depart', 'prix_par_place', 'places_dispo',
            'statut', 'cree_le',
        ]
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

    def validate(self, data):
        # Règles qui comparent plusieurs champs entre eux
        request = self.context['request']
        voiture = data['voiture']

        # Règle 1 : on ne peut publier un trajet qu'avec SA voiture
        if voiture.proprietaire != request.user:
            raise serializers.ValidationError(
                {'voiture_id': "Cette voiture ne t'appartient pas."}
            )
        # Règle 2 : pas plus de places que la voiture n'en a
        if data['places_dispo'] > voiture.nbre_place:
            raise serializers.ValidationError(
                {'places_dispo': f"Cette voiture a {voiture.nbre_place} place(s) passager au maximum."}
            )
        return data

    



#RESERVATION
class ReservationSerializer(serializers.ModelSerializer):
    trajet = TrajetSerializer(read_only=True)
    passager = UtilisateurPublicSerializer(read_only=True)

    montant = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    matricule = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            'id', 'trajet', 'passager', 'date_heure_reservation',
            'statut', 'caution', 'montant', 'contact', 'matricule',
        ]

    def get_montant(self, obj):
        return obj.calculer_montant()

    def get_contact(self, reservation):
        # Le téléphone n'est donné qu'après confirmation
        if reservation.statut != 'confirmee':
            return None
        request = self.context.get('request')
        if request is None:
            return None
        user = request.user
        if user == reservation.passager:
            return reservation.trajet.chauffeur.telephone
        if user == reservation.trajet.chauffeur:
            return reservation.passager.telephone
        return None

    def get_matricule(self, reservation):
        # Seul le passager d'une réservation confirmée voit la plaque
        request = self.context.get('request')
        if request is None or reservation.statut != 'confirmee':
            return None
        if request.user != reservation.passager:
            return None
        voiture = reservation.trajet.voiture
        # Anciens trajets sans voiture : null au lieu d'un plantage
        return voiture.matricule if voiture else None