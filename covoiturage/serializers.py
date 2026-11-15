from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import Notification, Paiement, ProfilChauffeur, Reservation, Utilisateur, Trajet, Voiture, Signalement
from datetime import date, datetime, timedelta
from .matching import trouver_zone
from django.conf import settings
import re
from .models import PointPassage, Zone
from .outils import normaliser_telephone

# Mot qui permet de reconnaître UCAD dans le nom d'une zone
# (même valeur que kMotUcad dans l'appli Flutter)
MOT_UCAD = 'ucad'


def est_ucad(texte):
    # On passe d'abord par la zone officielle (si le texte en désigne une),
    # sinon on regarde le texte tel quel
    if not texte:
        return False
    zone = trouver_zone(texte)
    nom = zone.nom if zone else texte
    return MOT_UCAD in nom.lower()


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


    def validate_telephone(self, value):
        n = normaliser_telephone(value)
        if not re.fullmatch(r'7\d{8}', n):
            raise serializers.ValidationError(
                "Numéro invalide (9 chiffres commençant par 7)."
            )
        if Utilisateur.objects.filter(telephone=n).exists():
            raise serializers.ValidationError("Ce numéro est déjà utilisé.")
        return n



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
    suspendu = serializers.BooleanField(source='est_suspendu', read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'first_name', 'last_name', 'date_naissance', 'telephone',
            'identifiant', 'email', 'est_personnel', 'photo', 'note',
            'annulations_tardives', 'suspendu',
        ]
        read_only_fields = ['annulations_tardives']


class UtilisateurPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['id', 'first_name', 'last_name', 'photo', 'note', 'annulations_tardives']



class ProfilModificationSerializer(serializers.ModelSerializer):
    # Déclarés ici pour interdire un prénom ou un nom vide
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    class Meta:
        model = Utilisateur
        # Seuls ces champs peuvent changer : tout autre champ envoyé est ignoré
        fields = ['first_name', 'last_name', 'telephone', 'photo']

    def validate_telephone(self, value):
        chiffres = ''.join(c for c in value if c.isdigit())
        if len(chiffres) < 9:
            raise serializers.ValidationError("Numéro de téléphone invalide.")
        return value
    



#PERMIS (visible seulement par son propriétaire, jamais imbriqué ailleurs)
class ProfilChauffeurSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfilChauffeur
        fields = ['numero_permis', 'photo_permis', 'verifie']
        read_only_fields = ['verifie']  # impossible de se valider soi-même



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
    modifiable = serializers.SerializerMethodField()
    etapes = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    points_passage = serializers.SerializerMethodField()
    itineraire_points = serializers.SerializerMethodField()

    class Meta:
        model = Trajet
        fields = [
            'id', 'chauffeur', 'voiture', 'voiture_id',
            'depart', 'depart_lat', 'depart_lng',
            'arrivee', 'arrivee_lat', 'arrivee_lng', 'date_depart',
            'heure_depart', 'prix_par_place', 'places_dispo',
            'statut', 'cree_le', 'modifiable', 'etapes', 'points_passage', 'itineraire_points'
        ]
        read_only_fields = ['statut', 'cree_le']


    def get_points_passage(self, trajet):
        return [
            p.zone.nom
            for p in trajet.points_passage.select_related('zone')
        ]

    def get_itineraire_points(self, trajet):
        points = []

        # 1. Point de départ
        points.append({
            'type': 'depart',
            'nom': trajet.depart,
            'latitude': trajet.depart_lat,
            'longitude': trajet.depart_lng,
        })

        # 2. Étapes intermédiaires
        passages = trajet.points_passage.select_related('zone').all()

        for passage in passages:
            points.append({
                'type': 'etape',
                'nom': passage.zone.nom,
                'latitude': passage.zone.latitude,
                'longitude': passage.zone.longitude,
            })

        # 3. Point d'arrivée
        points.append({
            'type': 'arrivee',
            'nom': trajet.arrivee,
            'latitude': trajet.arrivee_lat,
            'longitude': trajet.arrivee_lng,
        })

        return points

    def validate_etapes(self, value):
        zones = list(Zone.objects.all())
        resultat = []
        for texte in value:
            zone = trouver_zone(texte, zones)
            if zone is None:
                dispo = ', '.join(z.nom for z in zones)
                raise serializers.ValidationError(
                    f"Zone inconnue : {texte}. Zones disponibles : {dispo}."
                )
            resultat.append(zone)
        return resultat

    def _enregistrer_etapes(self, trajet, zones):
        trajet.points_passage.all().delete()
        for i, zone in enumerate(zones, start=1):
            PointPassage.objects.create(trajet=trajet, zone=zone, ordre=i)


    def get_modifiable(self, trajet):
        # Seul le chauffeur du trajet peut le modifier
        request = self.context.get('request')
        if request is None or request.user != trajet.chauffeur:
            return False
        try:
            trajet.verifier_modifiable()
        except ValueError:
            return False
        return True
    

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


    def validate_prix_par_place(self, value):
        mini = settings.PRIX_MIN_PAR_PLACE
        maxi = settings.PRIX_MAX_PAR_PLACE
        if value < mini or value > maxi:
            raise serializers.ValidationError(
               f"Le prix par place doit être compris entre {mini} et {maxi} FCFA."
        )
        return value
        


    def validate(self, data):
        request = self.context['request']
        # À la modification, un champ absent = on garde la valeur actuelle
        voiture = data.get('voiture') or (self.instance.voiture if self.instance else None)
        places = data.get(
            'places_dispo', self.instance.places_dispo if self.instance else None
        )

        if voiture is not None:
            # Règle 1 : on ne peut utiliser que SA voiture
            if voiture.proprietaire != request.user:
                raise serializers.ValidationError(
                    {'voiture_id': "Cette voiture ne t'appartient pas."}
                )
            # Règle 2 : pas plus de places que la voiture n'en a
            if places is not None and places > voiture.nbre_place:
                raise serializers.ValidationError(
                    {'places_dispo': f"Cette voiture a {voiture.nbre_place} place(s) passager au maximum."}
                )

        # Règle 3 (encadreur) : UCAD doit être le départ OU l'arrivée
        # (jamais les deux, jamais aucun des deux).
        # À la modification, un champ absent = on garde la valeur actuelle.
        depart = data.get('depart', self.instance.depart if self.instance else None)
        arrivee = data.get('arrivee', self.instance.arrivee if self.instance else None)
        if depart is not None and arrivee is not None:
            if est_ucad(depart) == est_ucad(arrivee):
                raise serializers.ValidationError(
                    "Le départ ou l'arrivée doit être UCAD (mais pas les deux)."
                )

        # Règle 4 : un chauffeur ne publie pas deux trajets trop proches dans le temps
        # (même jour ou veille/lendemain proche), quelles que soient les zones.
        # À la modification, un champ absent = on garde la valeur actuelle.
        chauffeur = self.instance.chauffeur if self.instance else request.user
        jour = data.get('date_depart', self.instance.date_depart if self.instance else None)
        heure = data.get('heure_depart', self.instance.heure_depart if self.instance else None)
        if jour is not None and heure is not None:
            heures = getattr(settings, 'DELAI_MIN_ENTRE_TRAJETS_HEURES', 2)
            ecart = timedelta(hours=heures)
            moment = datetime.combine(jour, heure)
            autres = Trajet.objects.filter(
                chauffeur=chauffeur, statut__in=['ouvert', 'complet'],
                date_depart__range=(jour - timedelta(days=1), jour + timedelta(days=1)),
            )
            if self.instance:
                autres = autres.exclude(pk=self.instance.pk)  # on ne se compare pas à soi-même
            for autre in autres:
                if abs(datetime.combine(autre.date_depart, autre.heure_depart) - moment) < ecart:
                    raise serializers.ValidationError(
                        f"Tu as déjà un trajet ({autre.libelle()} à {autre.heure_depart:%H:%M}) "
                        f"à moins de {heures} h de celui-ci."
                    )
        return data


    def _remplir_coordonnees(self, donnees):
        # Le serveur déduit lat/lng du texte saisi, grâce aux zones connues
        for cote in ('depart', 'arrivee'):
            if cote in donnees:
                zone = trouver_zone(donnees[cote])
                donnees[f'{cote}_lat'] = zone.latitude if zone else None
                donnees[f'{cote}_lng'] = zone.longitude if zone else None

    def create(self, validated_data):
        etapes = validated_data.pop('etapes', [])
        self._remplir_coordonnees(validated_data)
        trajet = super().create(validated_data)
        self._enregistrer_etapes(trajet, etapes)
        return trajet

    def update(self, instance, validated_data):
        etapes = validated_data.pop('etapes', None)
        self._remplir_coordonnees(validated_data)
        trajet = super().update(instance, validated_data)
        if etapes is not None:
            self._enregistrer_etapes(trajet, etapes)
        return trajet
    



#RESERVATION
class ReservationSerializer(serializers.ModelSerializer):
    trajet = TrajetSerializer(read_only=True)
    passager = UtilisateurPublicSerializer(read_only=True)

    montant = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    matricule = serializers.SerializerMethodField()
    peut_etre_notee = serializers.SerializerMethodField()
    deja_notee = serializers.SerializerMethodField()
    ma_note = serializers.SerializerMethodField()
    


    class Meta:
        model = Reservation
        fields = [
            'id', 'trajet', 'passager', 'date_heure_reservation',
            'statut', 'montant', 'contact', 'matricule',
            'peut_etre_notee', 'deja_notee', 'ma_note','paye'
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

    def get_deja_notee(self, reservation):
        return hasattr(reservation, 'avis')

    def get_peut_etre_notee(self, reservation):
        request = self.context.get('request')
        if request is None or request.user != reservation.passager:
            return False
        return (
            reservation.statut == 'confirmee'
            and reservation.trajet.statut == 'termine'
            and not hasattr(reservation, 'avis')
        )

    def get_ma_note(self, reservation):
        # Seul le passager voit la note qu'il a donnée
        request = self.context.get('request')
        if request is None or request.user != reservation.passager:
            return None
        return reservation.avis.note if hasattr(reservation, 'avis') else None

    paye = serializers.SerializerMethodField()

    def get_paye(self, obj):
        return obj.paiements.filter(type='trajet', statut='reussi').exists()



#NOTIFICATION
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'message', 'lue', 'cree_le']



#SIGNALEMENT
class SignalementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signalement
        fields = ['id', 'reservation', 'motif', 'description', 'statut', 'cree_le']
        read_only_fields = ['statut', 'cree_le']




#PAIEMENT 
class PaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ['id', 'plateforme', 'type', 'reservation', 'montant',
                  'statut', 'id_transaction', 'date_heure']
        read_only_fields = ['id', 'type', 'reservation', 'montant', 'statut',
                            'id_transaction', 'date_heure']