from datetime import datetime
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Avg
from django.conf import settings
from django.utils import timezone

#UTILISATEUR
class Utilisateur(AbstractUser):
    email = models.EmailField(unique=True, null=True, blank=True)
    telephone = models.CharField(max_length=20)
    date_naissance = models.DateField(null=True, blank=True)
    est_personnel = models.BooleanField(default=False)
    identifiant = models.CharField(max_length=50, unique=True, null=True, blank=True)
    photo = models.ImageField(upload_to='photos/', null=True, blank=True)
    note = models.FloatField(default=0)

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def est_chauffeur_verifie(self):
        # getattr évite une erreur si la personne n'a pas encore de profil
        profil = getattr(self, 'profil_chauffeur', None)
        return bool(profil and profil.verifie)



class ProfilChauffeur(models.Model):
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='profil_chauffeur'
    )
    numero_permis = models.CharField(max_length=30)
    photo_permis = models.ImageField(upload_to='permis/')
    verifie = models.BooleanField(default=False)  # coché par l'administrateur
    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Permis de {self.utilisateur} ({'vérifié' if self.verifie else 'en attente'})"





#VOITURE
class Voiture(models.Model):
    # Un utilisateur peut posséder plusieurs voitures (UML : 1 — 1..*)
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='voitures'
    )
    matricule = models.CharField(max_length=9, unique=True)  # unique : une plaque = une voiture
    marque = models.CharField(max_length=50)
    modele = models.CharField(max_length=50)
    couleur = models.CharField(max_length=30)
    # Places pour les passagers (sans compter le chauffeur)
    nbre_place = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.marque} {self.modele} ({self.matricule})"



#TRAJET
class Trajet(models.Model):
    # Les choix possibles pour le statut du trajet
    STATUTS = [
        ("ouvert", "Ouvert"),      # le trajet accepte encore des réservations
        ("complet", "Complet"),    # plus de places libres
        ("termine", "Terminé"),    # le trajet a eu lieu
        ("annule", "Annulé"),      # le chauffeur a annulé
    ]

    # Le chauffeur = un utilisateur. Un utilisateur peut avoir plusieurs trajets.
    chauffeur = models.ForeignKey(
        "Utilisateur", on_delete=models.CASCADE, related_name="trajets"
    )

    # La voiture utilisée pour ce trajet (UML : 0..1)
    voiture = models.ForeignKey(
        Voiture, on_delete=models.PROTECT, null=True, blank=True,
        related_name="trajets"
    )

    # Départ : un texte lisible (ex : "UCAD, entrée principale")
    depart = models.CharField(max_length=200)
    # Latitude et longitude : facultatives pour l'instant, on les remplira avec la carte plus tard
    depart_lat = models.FloatField(null=True, blank=True)
    depart_lng = models.FloatField(null=True, blank=True)

    # Arrivée : même principe que le départ
    arrivee = models.CharField(max_length=200)
    arrivee_lat = models.FloatField(null=True, blank=True)
    arrivee_lng = models.FloatField(null=True, blank=True)

    date_depart = models.DateField()
    heure_depart = models.TimeField()

    # Prix pour une place en FCFA (nombre entier)
    prix_par_place = models.PositiveIntegerField()
    # Nombre de places encore libres (au début = nombre de places proposées)
    places_dispo = models.PositiveSmallIntegerField()

    statut = models.CharField(max_length=10, choices=STATUTS, default="ouvert")

    # Rempli automatiquement à la création du trajet
    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Ce qui s'affiche dans l'admin Django
        return f"{self.depart} → {self.arrivee} ({self.date_depart})"



    def libelle(self):
        """Texte court utilisé dans les notifications."""
        return f"{self.depart} → {self.arrivee} du {self.date_depart:%d/%m/%Y}"

    def depart_depasse(self):
        """Vrai si la date/heure de départ est déjà passée."""
        moment = datetime.combine(self.date_depart, self.heure_depart)
        if timezone.is_naive(moment) and settings.USE_TZ:
            moment = timezone.make_aware(moment)
        return timezone.now() >= moment

    
    
    # Opérations du diagramme
    def annuler(self):
        """Le chauffeur annule son trajet : les demandes en cours sont annulées aussi."""
        if self.statut in ('annule', 'termine'):
            raise ValueError("Ce trajet est déjà terminé ou annulé.")
        with transaction.atomic():
            # On garde les passagers concernés AVANT de changer les statuts
            concernees = list(self.reservations.filter(
                statut__in=['en_attente', 'confirmee']
            ).select_related('passager'))
            self.reservations.filter(
                statut__in=['en_attente', 'confirmee']
            ).update(statut='annulee')
            self.statut = 'annule'
            self.save()
            Notification.objects.bulk_create([
                Notification(
                    destinataire=r.passager, type='trajet_annule',
                    message=f"Le chauffeur a annulé le trajet {self.libelle()}.",
                ) for r in concernees
            ])

    def terminer(self):
        """Le chauffeur termine son trajet (possible seulement après l'heure de départ)."""
        if self.statut in ('annule', 'termine'):
            raise ValueError("Ce trajet est déjà terminé ou annulé.")
        if not self.depart_depasse():
            raise ValueError("Le trajet n'a pas encore commencé.")
        with transaction.atomic():
            confirmees = list(self.reservations.filter(
                statut='confirmee'
            ).select_related('passager'))
            # Les demandes jamais acceptées sont annulées, les confirmées restent
            self.reservations.filter(statut='en_attente').update(statut='annulee')
            self.statut = 'termine'
            self.save()
            Notification.objects.bulk_create([
                Notification(
                    destinataire=r.passager, type='trajet_termine',
                    message=f"Trajet terminé : {self.libelle()}. Note ton chauffeur !",
                ) for r in confirmees
            ])


    def verifier_modifiable(self):
        """Lève une ValueError si le trajet ne peut plus être modifié."""
        if self.statut in ('annule', 'termine'):
            raise ValueError("Ce trajet est annulé ou terminé, il ne peut plus être modifié.")
        moment = datetime.combine(self.date_depart, self.heure_depart)
        if timezone.is_naive(moment) and settings.USE_TZ:
            moment = timezone.make_aware(moment)
        if timezone.now() >= moment:
            raise ValueError("L'heure de départ est dépassée, ce trajet ne peut plus être modifié.")
        if self.reservations.filter(statut__in=['en_attente', 'confirmee']).exists():
            raise ValueError("Des passagers ont une demande sur ce trajet. Annule-le puis republie-le.") 



#RESERVATION
class Reservation(models.Model):
    STATUTS = [
        ('en_attente', 'En attente'),
        ('confirmee', 'Confirmée'),
        ('refusee', 'Refusée'),
        ('annulee', 'Annulée'),
    ]

    # Relations du diagramme : Trajet 1 — 0..* Reservation
    #                          Passager 1 — 0..* Reservation
    trajet = models.ForeignKey(
        Trajet, on_delete=models.CASCADE, related_name='reservations'
    )
    passager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reservations'
    )

    # Attributs du diagramme
    date_heure_reservation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default='en_attente')
    caution = models.IntegerField(default=0)

    class Meta:
        ordering = ['-date_heure_reservation']  # les plus récentes d'abord

    def __str__(self):
        return f'{self.passager} -> {self.trajet} ({self.statut})'

    # Opérations du diagramme
    def valider(self):
        """Le chauffeur accepte la demande."""
        with transaction.atomic():
            # select_for_update verrouille les lignes : deux validations
            # simultanées passent l'une après l'autre, jamais en même temps
            trajet = Trajet.objects.select_for_update().get(pk=self.trajet_id)
            reservation = Reservation.objects.select_for_update().get(pk=self.pk)
            if reservation.statut != 'en_attente':
                raise ValueError("Cette demande n'est plus en attente.")
            if trajet.statut != 'ouvert' or trajet.places_dispo <= 0:
                raise ValueError("Ce trajet n'est plus disponible.")
            if trajet.depart_depasse():
                raise ValueError("Le trajet est déjà parti, tu ne peux plus accepter de demande.")
            trajet.places_dispo -= 1
            if trajet.places_dispo == 0:
                trajet.statut = 'complet'   # plus de place : le trajet est complet
            trajet.save()
            reservation.statut = 'confirmee'
            reservation.save()
            Notification.objects.create(
                destinataire=reservation.passager, type='demande_confirmee',
                message=f"Ta demande pour {trajet.libelle()} a été confirmée.",
            )
        # On recharge cet objet pour que la vue renvoie les valeurs à jour
        self.refresh_from_db()

    def annuler(self):
        """Le passager annule sa réservation."""
        if self.statut in ('annulee', 'refusee'):
            raise ValueError("Cette réservation est déjà terminée.")
        if self.trajet.statut == 'termine':
            raise ValueError("Ce trajet est terminé, tu ne peux plus annuler.")
        with transaction.atomic():
            # Si elle était confirmée, la place est libérée
            if self.statut == 'confirmee':
                self.trajet.places_dispo += 1
                if self.trajet.statut == 'complet':
                    self.trajet.statut = 'ouvert'   # une place s'est libérée
                self.trajet.save()
            self.statut = 'annulee'
            self.save()
            Notification.objects.create(
                destinataire=self.trajet.chauffeur, type='reservation_annulee',
                message=f"{self.passager.first_name} a annulé sa réservation pour {self.trajet.libelle()}.",
            )


    def calculer_montant(self):
        """Une place = le prix par place fixé par le chauffeur."""
        return self.trajet.prix_par_place
    


    def noter(self, note, commentaire=''):
        """Le passager note le chauffeur après le trajet."""
        if self.statut != 'confirmee':
            raise ValueError("Seule une réservation confirmée peut être notée.")
        if self.trajet.statut != 'termine':
            raise ValueError("Le trajet n'est pas encore terminé.")
        if hasattr(self, 'avis'):
            raise ValueError("Tu as déjà noté cette réservation.")
        if not (1 <= note <= 5):
            raise ValueError("La note doit être entre 1 et 5.")
        with transaction.atomic():
            avis = Avis.objects.create(
                reservation=self, note=note, commentaire=commentaire
            )
            # On recalcule la moyenne du chauffeur sur tous ses avis
            chauffeur = self.trajet.chauffeur
            moyenne = Avis.objects.filter(
                reservation__trajet__chauffeur=chauffeur
            ).aggregate(m=Avg('note'))['m']
            chauffeur.note = round(moyenne, 1)
            chauffeur.save(update_fields=['note'])
        return avis



 #AVIS
class Avis(models.Model):
    # Un seul avis par réservation
    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name='avis'
    )
    note = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    commentaire = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.note}/5 pour {self.reservation}"

    

#NOTIFICATION
class Notification(models.Model):
    TYPES = [
        ('demande_recue', 'Demande reçue'),
        ('demande_confirmee', 'Demande confirmée'),
        ('demande_refusee', 'Demande refusée'),
        ('reservation_annulee', 'Réservation annulée'),
        ('trajet_annule', 'Trajet annulé'),
        ('trajet_termine', 'Trajet terminé'),
    ]
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(max_length=30, choices=TYPES)
    message = models.TextField()
    lue = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cree_le']   # les plus récentes d'abord

    def __str__(self):
        return f"{self.type} pour {self.destinataire}"





#ZONE
class Zone(models.Model):
    """Un lieu connu de la communauté : le serveur en déduit les coordonnées d'un trajet."""
    nom = models.CharField(max_length=100, unique=True)
    # Autres écritures possibles, séparées par des virgules
    alias = models.CharField(max_length=300, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.nom

    def mots_cles(self):
        mots = [self.nom] + self.alias.split(',')
        return [m.strip() for m in mots if m.strip()]





#SIGNALEMENT
class Signalement(models.Model):
    MOTIFS = [
        ('comportement', 'Comportement inapproprié'),
        ('absence', 'Absent au rendez-vous'),
        ('annulation', 'Annulation de dernière minute'),
        ('conduite', 'Conduite dangereuse'),
        ('fraude', 'Faux profil ou fraude'),
        ('autre', 'Autre'),
    ]
    STATUTS = [
        ('nouveau', 'Nouveau'),
        ('traite', 'Traité'),
        ('rejete', 'Rejeté'),
    ]
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='signalements_faits'
    )
    cible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='signalements_recus'
    )
    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE, related_name='signalements'
    )
    motif = models.CharField(max_length=20, choices=MOTIFS)
    description = models.TextField(blank=True)
    statut = models.CharField(max_length=10, choices=STATUTS, default='nouveau')
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.auteur} signale {self.cible} ({self.motif})"