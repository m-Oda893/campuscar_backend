from datetime import timedelta
from django.utils import timezone
from covoiturage.models import (
    Utilisateur, ProfilChauffeur, Voiture, Trajet, Reservation, Avis, Notification,
)
from covoiturage.matching import trouver_zone

MOT_DE_PASSE = "Demo1234!"
maintenant = timezone.localtime()
aujourdhui = maintenant.date()


def jour(n):
    return aujourdhui + timedelta(days=n)


# 1. Nettoyage : on supprime seulement les données des comptes demo_
demo = Utilisateur.objects.filter(username__startswith='demo_')
Trajet.objects.filter(chauffeur__in=demo).delete()       # supprime aussi réservations et avis
Reservation.objects.filter(passager__in=demo).delete()
Notification.objects.filter(destinataire__in=demo).delete()


# 2. Fonctions utiles
def utilisateur(username, prenom, nom, telephone, email, compteur=0):
    u, _ = Utilisateur.objects.get_or_create(username=username)
    u.first_name, u.last_name = prenom, nom
    u.telephone, u.email = telephone, email
    u.annulations_tardives = compteur
    u.note = 0
    u.set_password(MOT_DE_PASSE)
    u.save()
    return u


def chauffeur_verifie(u, numero):
    # La photo du permis est un chemin fictif : suffisant pour la démo
    ProfilChauffeur.objects.update_or_create(
        utilisateur=u,
        defaults={'numero_permis': numero, 'photo_permis': 'permis/demo.jpg', 'verifie': True},
    )


def voiture(proprietaire, matricule, marque, modele, couleur, places):
    v, _ = Voiture.objects.update_or_create(
        matricule=matricule,
        defaults={'proprietaire': proprietaire, 'marque': marque, 'modele': modele,
                  'couleur': couleur, 'nbre_place': places},
    )
    return v


def trajet(chauffeur, voit, depart, arrivee, date, heure, prix, places, statut='ouvert'):
    d, a = trouver_zone(depart), trouver_zone(arrivee)
    return Trajet.objects.create(
        chauffeur=chauffeur, voiture=voit, depart=depart, arrivee=arrivee,
        depart_lat=d.latitude if d else None, depart_lng=d.longitude if d else None,
        arrivee_lat=a.latitude if a else None, arrivee_lng=a.longitude if a else None,
        date_depart=date, heure_depart=heure,
        prix_par_place=prix, places_dispo=places, statut=statut,
    )


def reservation(t, passager, statut):
    return Reservation.objects.create(trajet=t, passager=passager, statut=statut)


# 3. Comptes (même mot de passe pour tous, affiché à la fin)
# Si ton écran de connexion refuse ces emails, adapte-les au format que tu acceptes
mamadou = utilisateur('demo_chauffeur', 'Mamadou', 'Diop', '770000001', 'mamadou.demo@ucad.sn')
awa = utilisateur('demo_chauffeur2', 'Awa', 'Ba', '770000002', 'awa.demo@ucad.sn', compteur=1)
fatou = utilisateur('demo_passager', 'Fatou', 'Ndiaye', '770000003', 'fatou.demo@ucad.sn')
moussa = utilisateur('demo_passager2', 'Moussa', 'Sow', '770000004', 'moussa.demo@ucad.sn')
ibrahima = utilisateur('demo_bloque', 'Ibrahima', 'Fall', '770000005', 'ibrahima.demo@ucad.sn', compteur=3)

chauffeur_verifie(mamadou, 'DEMO-0001')
chauffeur_verifie(awa, 'DEMO-0002')

corolla = voiture(mamadou, 'AA-123-AB', 'Toyota', 'Corolla', 'Gris', 4)
i10 = voiture(awa, 'DK-456-CD', 'Hyundai', 'i10', 'Rouge', 2)


# 4. Trajets ouverts (visibles dans la recherche)
t_ouvert = trajet(mamadou, corolla, 'UCAD', 'Pikine', jour(1), (7, 30), 500, 3)
trajet(mamadou, corolla, 'Pikine', 'UCAD', jour(1), (17, 30), 500, 3)
trajet(mamadou, corolla, 'UCAD', 'Parcelles Assainies', jour(2), (8, 0), 700, 3)
trajet(awa, i10, 'Guediawaye', 'UCAD', jour(1), (7, 15), 600, 2)
trajet(awa, i10, 'Keur Massar', 'UCAD', jour(2), (6, 45), 1000, 2)
trajet(awa, i10, 'Rufisque', 'UCAD', jour(3), (7, 0), 1000, 2)

# Une demande en attente : le chauffeur peut la valider devant le jury
reservation(t_ouvert, moussa, 'en_attente')
Notification.objects.create(
    destinataire=mamadou, type='demande_recue',
    message=f"{moussa.first_name} demande une place pour {t_ouvert.libelle()}.",
)

# Un trajet complet (2 places, 2 confirmées)
t_complet = trajet(awa, i10, 'UCAD', 'Mbao', jour(1), (18, 0), 500, 0, statut='complet')
reservation(t_complet, fatou, 'confirmee')
reservation(t_complet, moussa, 'confirmee')

# Un trajet annulé
trajet(mamadou, corolla, 'UCAD', 'Yoff', jour(2), (9, 0), 500, 3, statut='annule')


# 5. Trajets terminés : un déjà noté, un à noter devant le jury
t_note = trajet(mamadou, corolla, 'UCAD', 'Pikine', jour(-1), (17, 45), 500, 3, statut='termine')
r_note = reservation(t_note, fatou, 'confirmee')
Avis.objects.create(reservation=r_note, note=5, commentaire="Chauffeur ponctuel et agréable.")
mamadou.note = 5.0
mamadou.save(update_fields=['note'])

t_a_noter = trajet(awa, i10, 'Pikine', 'UCAD', jour(-2), (7, 30), 500, 2, statut='termine')
reservation(t_a_noter, fatou, 'confirmee')
Notification.objects.create(
    destinataire=fatou, type='trajet_termine',
    message=f"Trajet terminé : {t_a_noter.libelle()}. Note ton chauffeur !",
)
awa.note = 4.5   # valeur de démonstration, sans avis réels derrière
awa.save(update_fields=['note'])


# 6. Pour montrer l'annulation tardive : départ dans 1 h 30, Fatou a une place confirmée
bientot = maintenant + timedelta(minutes=90)
t_bientot = trajet(
    mamadou, corolla, 'UCAD', 'Parcelles Assainies',
    bientot.date(), bientot.time().replace(second=0, microsecond=0), 700, 2,
)
reservation(t_bientot, fatou, 'confirmee')
Notification.objects.create(
    destinataire=fatou, type='demande_confirmee',
    message=f"Ta demande pour {t_bientot.libelle()} a été confirmée.",
)

print("Trajets de démo créés :", Trajet.objects.filter(chauffeur__in=demo).count())
print("Mot de passe commun :", MOT_DE_PASSE)
for u in demo:
    print(" -", u.email, "|", u.get_full_name(), "| annulations tardives :", u.annulations_tardives)