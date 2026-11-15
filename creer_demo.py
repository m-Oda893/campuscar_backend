
from datetime import timedelta, time
from django.db.models import Q
from django.utils import timezone

from covoiturage.models import (
    Utilisateur, ProfilChauffeur, Voiture, Trajet, Reservation, Avis,
    Notification, Paiement,
)
from covoiturage.matching import trouver_zone


MOT_DE_PASSE = "Demo1234!"

maintenant = timezone.localtime()
aujourdhui = maintenant.date()

# Laisser vide pour préserver les comptes de test créés manuellement.
# Ajouter un numéro uniquement si tu souhaites supprimer volontairement
# le compte correspondant et toutes ses données.
AUTRES_TELEPHONES = []


def jour(n):
    return aujourdhui + timedelta(days=n)


# ============================================================
# 1. NETTOYAGE DES ANCIENNES DONNÉES DE DÉMONSTRATION
# ============================================================

a_supprimer = Utilisateur.objects.filter(
    Q(username__startswith="demo_")
    | Q(telephone__in=AUTRES_TELEPHONES),
    is_superuser=False,
)

Paiement.objects.filter(
    Q(utilisateur__in=a_supprimer)
    | Q(reservation__passager__in=a_supprimer)
    | Q(reservation__trajet__chauffeur__in=a_supprimer)
).delete()

Reservation.objects.filter(
    Q(passager__in=a_supprimer)
    | Q(trajet__chauffeur__in=a_supprimer)
).delete()

Trajet.objects.filter(chauffeur__in=a_supprimer).delete()
Notification.objects.filter(destinataire__in=a_supprimer).delete()
Voiture.objects.filter(proprietaire__in=a_supprimer).delete()

a_supprimer.delete()


# ============================================================
# 2. FONCTIONS UTILITAIRES
# ============================================================

def utilisateur(username, prenom, nom, telephone, email, compteur=0):
    u = Utilisateur.objects.create(
        username=username,
        first_name=prenom,
        last_name=nom,
        telephone=telephone,
        email=email,
        annulations_tardives=compteur,
        note=0,
    )
    u.set_password(MOT_DE_PASSE)
    u.save()
    return u


def chauffeur_verifie(u, numero):
    ProfilChauffeur.objects.update_or_create(
        utilisateur=u,
        defaults={
            "numero_permis": numero,
            "photo_permis": "permis/demo.jpg",
            "verifie": True,
        },
    )


def voiture(proprietaire, matricule, marque, modele, couleur, places):
    return Voiture.objects.create(
        proprietaire=proprietaire,
        matricule=matricule,
        marque=marque,
        modele=modele,
        couleur=couleur,
        nbre_place=places,
    )


def trajet(
    chauffeur, voit, depart, arrivee, date, heure,
    prix, places, statut="ouvert"
):
    d = trouver_zone(depart)
    a = trouver_zone(arrivee)

    if isinstance(heure, tuple):
        heure = time(*heure)

    return Trajet.objects.create(
        chauffeur=chauffeur,
        voiture=voit,
        depart=depart,
        arrivee=arrivee,
        depart_lat=d.latitude if d else None,
        depart_lng=d.longitude if d else None,
        arrivee_lat=a.latitude if a else None,
        arrivee_lng=a.longitude if a else None,
        date_depart=date,
        heure_depart=heure,
        prix_par_place=prix,
        places_dispo=places,
        statut=statut,
    )


def reservation(t, passager, statut):
    return Reservation.objects.create(
        trajet=t,
        passager=passager,
        statut=statut,
    )


# ============================================================
# 3. CRÉATION DES CINQ COMPTES
# ============================================================

mamadou = utilisateur(
    "demo_chauffeur", "Mamadou", "Diop",
    "770000001", "mamadou.demo@ucad.edu.sn"
)

awa = utilisateur(
    "demo_chauffeur2", "Awa", "Ba",
    "770000002", "awa.demo@ucad.edu.sn",
    compteur=1
)

fatou = utilisateur(
    "demo_passager", "Fatou", "Ndiaye",
    "770000003", "fatou.demo@ucad.edu.sn"
)

moussa = utilisateur(
    "demo_passager2", "Moussa", "Sow",
    "770000004", "moussa.demo@ucad.edu.sn"
)

ibrahima = utilisateur(
    "demo_bloque", "Ibrahima", "Fall",
    "770000005", "ibrahima.demo@ucad.edu.sn",
    compteur=3
)


# Vérification des chauffeurs
chauffeur_verifie(mamadou, "DEMO-0001")
chauffeur_verifie(awa, "DEMO-0002")


# Véhicules
corolla = voiture(
    mamadou, "AA-123-AB",
    "Toyota", "Corolla", "Gris", 4
)

i10 = voiture(
    awa, "DK-456-CD",
    "Hyundai", "i10", "Rouge", 2
)


# Caution déjà payée uniquement pour Ibrahima.
Paiement.objects.create(
    utilisateur=ibrahima,
    type="caution",
    montant=3000,
    plateforme="wave",
)


# ============================================================
# 4. TRAJETS PRÉPARÉS POUR LES FONCTIONNALITÉS SECONDAIRES
#    Ces trajets appartiennent principalement à Awa.
# ============================================================

# Trajet ouvert avec demande en attente de Moussa.
t_ouvert = trajet(
    awa, i10,
    "UCAD", "Pikine",
    jour(1), (7, 30),
    500, 3
)

reservation(t_ouvert, moussa, "en_attente")

Notification.objects.create(
    destinataire=awa,
    type="demande_recue",
    message=f"{moussa.first_name} demande une place pour {t_ouvert.libelle()}.",
)


# Trajet complet : deux réservations confirmées.
t_complet = trajet(
    awa, i10,
    "UCAD", "Mbao",
    jour(1), (18, 0),
    500, 0,
    statut="complet"
)

reservation(t_complet, moussa, "confirmee")
reservation(t_complet, ibrahima, "confirmee")


# Trajet annulé.
trajet(
    awa, i10,
    "UCAD", "Yoff",
    jour(2), (9, 0),
    500, 3,
    statut="annule"
)


# ============================================================
# 5. TRAJETS TERMINÉS ET AVIS
# ============================================================

# Trajet déjà noté.
t_note = trajet(
    awa, i10,
    "UCAD", "Pikine",
    jour(-1), (17, 45),
    500, 2,
    statut="termine"
)

r_note = reservation(t_note, moussa, "confirmee")

Avis.objects.create(
    reservation=r_note,
    note=5,
    commentaire="Chauffeur ponctuel et agréable."
)

awa.note = 5.0
awa.save(update_fields=["note"])


# Trajet terminé en attente d'un avis.
t_a_noter = trajet(
    awa, i10,
    "Pikine", "UCAD",
    jour(-2), (7, 30),
    500, 2,
    statut="termine"
)

reservation(t_a_noter, moussa, "confirmee")

Notification.objects.create(
    destinataire=moussa,
    type="trajet_termine",
    message=f"Trajet terminé : {t_a_noter.libelle()}. Note ton chauffeur !",
)


# ============================================================
# 6. ANNULATION TARDIVE
#    Mamadou est chauffeur, Awa est passagère.
# ============================================================

bientot = maintenant + timedelta(minutes=90)

t_bientot = trajet(
    mamadou,
    corolla,
    "UCAD",
    "Parcelles Assainies",
    bientot.date(),
    bientot.time().replace(second=0, microsecond=0),
    700,
    1,
)

reservation(t_bientot, awa, "confirmee")

Notification.objects.create(
    destinataire=awa,
    type="demande_confirmee",
    message=f"Ta demande pour {t_bientot.libelle()} a été confirmée.",
)


# ============================================================
# 7. CLÔTURE AUTOMATIQUE D'UN ANCIEN TRAJET
#    Trajet d'Awa parti il y a cinq heures.
# ============================================================

il_y_a_5h = maintenant - timedelta(hours=5)

t_oublie = trajet(
    awa,
    i10,
    "Pikine",
    "UCAD",
    il_y_a_5h.date(),
    il_y_a_5h.time().replace(second=0, microsecond=0),
    500,
    1,
)

reservation(t_oublie, moussa, "confirmee")


# ============================================================
# 8. RÉCAPITULATIF
# ============================================================

demo = Utilisateur.objects.filter(username__startswith="demo_")

print("\n========== CAMPUSCAR : DONNÉES DE DÉMONSTRATION ==========")

print(
    "Nombre de trajets créés :",
    Trajet.objects.filter(chauffeur__in=demo).count()
)

print("Mot de passe commun :", MOT_DE_PASSE)

for u in demo:
    print(
        u.telephone,
        "|", u.email,
        "|", u.get_full_name(),
        "| Annulations tardives :", u.annulations_tardives
    )

print("\nRépartition prévue :")
print("- Mamadou : chauffeur principal pour la publication en direct.")
print("- Fatou : passagère sans réservation préexistante.")
print("- Awa : chauffeur secondaire et scénario d'annulation tardive.")
print("- Moussa : demandes et réservations préparées.")
print("- Ibrahima : compte avec trois annulations tardives.")

print("\n========== PRÉPARATION TERMINÉE ==========\n")
