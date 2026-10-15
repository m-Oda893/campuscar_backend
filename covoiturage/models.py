from django.contrib.auth.models import AbstractUser
from django.db import models


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