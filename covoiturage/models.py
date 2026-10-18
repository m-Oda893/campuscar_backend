from django.contrib.auth.models import AbstractUser
from django.db import models

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