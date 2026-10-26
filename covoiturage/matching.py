import math
import re
import unicodedata
from datetime import datetime

from .models import Zone

SEUIL_KM = 3.0           # un point doit être à moins de 3 km du trajet
FENETRE_HEURES = 1.0     # écart d'heure maximal accepté
MARGE = 0.05             # le passager doit monter un peu avant de descendre


def _normaliser(texte):
    """'  Guédiawaye ' -> 'guediawaye' (minuscules, sans accents)."""
    texte = unicodedata.normalize('NFD', texte or '')
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return texte.lower().strip()


def parser_heure(texte):
    """'18:30' -> time, ou None si absent ou invalide."""
    if not texte:
        return None
    try:
        return datetime.strptime(texte[:5], '%H:%M').time()
    except ValueError:
        return None


def trouver_zone(texte, zones=None):
    """Cherche la zone dont le nom ou un alias apparaît dans le texte.
    S'il y en a plusieurs, on garde le mot-clé le plus long (le plus précis)."""
    texte = _normaliser(texte)
    if not texte:
        return None
    meilleure, longueur = None, 0
    for zone in (zones if zones is not None else Zone.objects.all()):
        for mot in zone.mots_cles():
            m = _normaliser(mot)
            # \b = mot entier : "fst" ne se trouve pas dans "fastidieux"
            if m and re.search(r'\b' + re.escape(m) + r'\b', texte) and len(m) > longueur:
                meilleure, longueur = zone, len(m)
    return meilleure


def position_sur_segment(point, a, b):
    """Projette 'point' sur le segment a -> b (tous en (lat, lng)).
    Renvoie (t, distance_km) :
      t = 0 au départ du chauffeur, 1 à son arrivée (hors de [0, 1] = avant/après)
      distance_km = distance du point au segment."""
    # Plan local en km (x vers l'est, y vers le nord) : suffisant à l'échelle de Dakar
    lat0 = math.radians(a[0])

    def plan(p):
        return ((p[1] - a[1]) * 111.32 * math.cos(lat0), (p[0] - a[0]) * 110.57)

    bx, by = plan(b)
    px, py = plan(point)
    longueur2 = bx * bx + by * by
    if longueur2 == 0:
        return 0.0, math.hypot(px, py)
    t = (px * bx + py * by) / longueur2          # produit scalaire normalisé
    t_borne = max(0.0, min(1.0, t))              # point le plus proche DANS le segment
    return t, math.hypot(px - t_borne * bx, py - t_borne * by)


def evaluer(trajet, depart_txt, arrivee_txt, zone_dep, zone_arr, heure_voulue):
    """Renvoie un dict (infos + score) si le trajet convient, sinon None."""
    # 1. Fenêtre horaire
    ecart_h = 0.0
    if heure_voulue is not None:
        h = trajet.heure_depart
        minutes = abs((h.hour * 60 + h.minute) - (heure_voulue.hour * 60 + heure_voulue.minute))
        ecart_h = minutes / 60
        if ecart_h > FENETRE_HEURES:
            return None

    # 2. Géographie (si les coordonnées existent), sinon recherche par texte
    coords_ok = None not in (
        trajet.depart_lat, trajet.depart_lng, trajet.arrivee_lat, trajet.arrivee_lng
    )
    a = (trajet.depart_lat, trajet.depart_lng)
    b = (trajet.arrivee_lat, trajet.arrivee_lng)
    km = 0.0
    t_dep = t_arr = None

    if depart_txt:
        if zone_dep and coords_ok:
            t_dep, d = position_sur_segment((zone_dep.latitude, zone_dep.longitude), a, b)
            if d > SEUIL_KM:
                return None
            km += d
        elif _normaliser(depart_txt) not in _normaliser(trajet.depart):
            return None

    if arrivee_txt:
        if zone_arr and coords_ok:
            t_arr, d = position_sur_segment((zone_arr.latitude, zone_arr.longitude), a, b)
            if d > SEUIL_KM:
                return None
            km += d
        elif _normaliser(arrivee_txt) not in _normaliser(trajet.arrivee):
            return None

    # 3. Sens du trajet : on doit monter AVANT de descendre
    if t_dep is not None and t_arr is not None:
        if t_arr - t_dep <= MARGE:
            return None
    elif t_dep is not None and t_dep >= 1 - MARGE:
        return None
    elif t_arr is not None and t_arr <= MARGE:
        return None

    # 4. Score : plus il est petit, meilleur est le trajet (coefficients arbitraires, réglables)
    note = trajet.chauffeur.note or 0
    score = km + 2 * ecart_h - 0.3 * note
    return {
        'km': round(km, 1),
        'ecart_minutes': int(round(ecart_h * 60)),
        'geo': t_dep is not None or t_arr is not None,
        'score': score,
    }