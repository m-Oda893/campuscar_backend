from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings



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
        if self.statut != 'en_attente':
            raise ValueError("Cette demande n'est plus en attente.")
        if self.trajet.places_dispo <= 0:
            raise ValueError("Il n'y a plus de place disponible.")
        self.trajet.places_dispo -= 1
        self.trajet.save()
        self.statut = 'confirmee'
        self.save()

    def annuler(self):
        """Le passager annule sa réservation."""
        if self.statut in ('annulee', 'refusee'):
            raise ValueError("Cette réservation est déjà terminée.")
        # Si elle était confirmée, la place est libérée
        if self.statut == 'confirmee':
            self.trajet.places_dispo += 1
            self.trajet.save()
        self.statut = 'annulee'
        self.save()

    def calculer_montant(self):
        """Une place = le prix par place fixé par le chauffeur."""
        return self.trajet.prix_par_place