
import math
import re
import unicodedata
from datetime import datetime

from .models import Zone


SEUIL_KM = 3.0
FENETRE_MINUTES = 20
MARGE = 0.05


def _normaliser(texte):
    texte = unicodedata.normalize('NFD', texte or '')
    texte = ''.join(
        c for c in texte
        if unicodedata.category(c) != 'Mn'
    )
    return texte.lower().strip()


def parser_heure(texte):
    if not texte:
        return None

    try:
        return datetime.strptime(texte[:5], '%H:%M').time()
    except ValueError:
        return None


def trouver_zone(texte, zones=None):
    texte = _normaliser(texte)

    if not texte:
        return None

    meilleure, longueur = None, 0

    for zone in (zones if zones is not None else Zone.objects.all()):
        for mot in zone.mots_cles():
            m = _normaliser(mot)

            if (
                m
                and re.search(r'\b' + re.escape(m) + r'\b', texte)
                and len(m) > longueur
            ):
                meilleure = zone
                longueur = len(m)

    return meilleure


def _distance_plan(a, b):
    """Distance approximative en kilomètres entre deux coordonnées."""
    lat0 = math.radians(a[0])

    dx = (b[1] - a[1]) * 111.32 * math.cos(lat0)
    dy = (b[0] - a[0]) * 110.57

    return math.hypot(dx, dy)


def position_sur_segment(point, a, b):
    """
    Projette un point sur un segment.
    Les coordonnées sont au format (latitude, longitude).
    Retourne la position t et la distance minimale en kilomètres.
    """
    lat0 = math.radians(a[0])

    def plan(p):
        return (
            (p[1] - a[1]) * 111.32 * math.cos(lat0),
            (p[0] - a[0]) * 110.57
        )

    bx, by = plan(b)
    px, py = plan(point)

    longueur2 = bx * bx + by * by

    if longueur2 == 0:
        return 0.0, math.hypot(px, py)

    t = (px * bx + py * by) / longueur2
    t_borne = max(0.0, min(1.0, t))

    distance = math.hypot(
        px - t_borne * bx,
        py - t_borne * by
    )

    return t_borne, distance


def _coordonnees_valides(latitude, longitude):
    return latitude is not None and longitude is not None


def _construire_parcours(trajet):
    """
    Construit le parcours ordonné :
    départ -> points de passage -> arrivée.
    """
    if not all((
        _coordonnees_valides(trajet.depart_lat, trajet.depart_lng),
        _coordonnees_valides(trajet.arrivee_lat, trajet.arrivee_lng)
    )):
        return []

    parcours = [
        (float(trajet.depart_lat), float(trajet.depart_lng))
    ]

    passages = trajet.points_passage.select_related('zone').all()

    for passage in passages:
        zone = passage.zone

        if _coordonnees_valides(zone.latitude, zone.longitude):
            parcours.append((
                float(zone.latitude),
                float(zone.longitude)
            ))

    parcours.append((
        float(trajet.arrivee_lat),
        float(trajet.arrivee_lng)
    ))

    return parcours


def _position_sur_parcours(point, parcours):
    """
    Recherche le segment le plus proche du point.
    Retourne :
    - sa distance au parcours ;
    - sa progression normalisée entre 0 et 1.

    La progression tient compte de la longueur cumulée des segments.
    """
    if len(parcours) < 2:
        return None

    longueurs = [
        _distance_plan(parcours[i], parcours[i + 1])
        for i in range(len(parcours) - 1)
    ]

    longueur_totale = sum(longueurs)

    if longueur_totale == 0:
        return None

    meilleure_distance = None
    meilleure_progression = None
    distance_cumulee = 0.0

    for i, longueur in enumerate(longueurs):
        a = parcours[i]
        b = parcours[i + 1]

        if longueur == 0:
            distance_cumulee += longueur
            continue

        t, distance = position_sur_segment(point, a, b)

        progression = (
            distance_cumulee + t * longueur
        ) / longueur_totale

        if (
            meilleure_distance is None
            or distance < meilleure_distance
        ):
            meilleure_distance = distance
            meilleure_progression = progression

        distance_cumulee += longueur

    if meilleure_distance is None:
        return None

    return meilleure_progression, meilleure_distance


def evaluer(
    trajet,
    depart_txt,
    arrivee_txt,
    zone_dep,
    zone_arr,
    heure_voulue
):
    """
    Évalue la correspondance entre une recherche et un trajet.

    Vérifications :
    1. Proximité horaire.
    2. Proximité géographique du parcours.
    3. Respect de l'ordre départ -> arrivée.
    4. Calcul du score de correspondance.
    """

    # 1. Vérification de l'heure
    ecart_h = 0.0

    if heure_voulue is not None:
        h = trajet.heure_depart

        minutes = abs(
            (h.hour * 60 + h.minute)
            - (heure_voulue.hour * 60 + heure_voulue.minute)
        )

        ecart_h = minutes / 60

        if minutes > FENETRE_MINUTES:
            return None

    # 2. Construction du parcours avec les étapes intermédiaires
    parcours = _construire_parcours(trajet)

    progression_dep = None
    progression_arr = None
    km = 0.0

    # 3. Vérification du point de départ recherché
    if depart_txt:
        if zone_dep is not None and parcours:
            point = (
                zone_dep.latitude,
                zone_dep.longitude
            )

            resultat = _position_sur_parcours(point, parcours)

            if resultat is not None:
                progression_dep, distance = resultat

                if distance > SEUIL_KM:
                    return None

                km += distance

            else:
                if (
                    _normaliser(depart_txt)
                    not in _normaliser(trajet.depart)
                ):
                    return None

        elif (
            _normaliser(depart_txt)
            not in _normaliser(trajet.depart)
        ):
            return None

    # 4. Vérification du point d'arrivée recherché
    if arrivee_txt:
        if zone_arr is not None and parcours:
            point = (
                zone_arr.latitude,
                zone_arr.longitude
            )

            resultat = _position_sur_parcours(point, parcours)

            if resultat is not None:
                progression_arr, distance = resultat

                if distance > SEUIL_KM:
                    return None

                km += distance

            else:
                if (
                    _normaliser(arrivee_txt)
                    not in _normaliser(trajet.arrivee)
                ):
                    return None

        elif (
            _normaliser(arrivee_txt)
            not in _normaliser(trajet.arrivee)
        ):
            return None

    # 5. Vérification du sens du trajet
    if (
        progression_dep is not None
        and progression_arr is not None
    ):
        # Le passager doit monter avant de descendre.
        if progression_arr - progression_dep <= MARGE:
            return None

    elif progression_dep is not None:
        # Le départ recherché ne doit pas être presque à destination.
        if progression_dep >= 1 - MARGE:
            return None

    elif progression_arr is not None:
        # L'arrivée recherchée ne doit pas être presque au départ.
        if progression_arr <= MARGE:
            return None

    # 6. Calcul du score
    note = trajet.chauffeur.note or 0

    score = km + 2 * ecart_h - 0.3 * note

    return {
        'km': round(km, 1),
        'ecart_minutes': int(round(ecart_h * 60)),
        'geo': (
            progression_dep is not None
            or progression_arr is not None
        ),
        'score': score
    }
