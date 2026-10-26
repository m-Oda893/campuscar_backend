from covoiturage.models import Zone, Trajet
from covoiturage.matching import trouver_zone

# (nom, alias, latitude, longitude) : remplace les None par tes valeurs Google Maps
ZONES = [
    ("UCAD", "fst, flsh,faseg,fmpos,fsjp,fastef,ucad II", 14.6937958, -17.4723872),
    ("Pikine", "pikine, thiaroye, rue 10, talli bou makk, talli bou bess, bountou pikine", 14.7552616, -17.4060248),
    ("Parcelles Assainies", "parcelles assainies, case bi , hlm grand médine,unité 19, unité 9, fadia", 14.7598765, -17.4520565),
    ("Mbao", "brioche dorée mbao, villeneuve, petit mbao", 14.7298923, -17.3464167),
    ("Keur Massar", "pénitence , auchan keur massar , jamil carreaux, brioche dorée keur massar", 14.7864083, -17.3325407),
    ("Rufisque", "rufisque , gare pnr , auchan rufisque , cite tacko", 14.7155803, -17.2915287),
    ("Jaxaay", "jaxaay 1, jaxaay 2 , sedima ,brioche dorée jaxaay , almadies 2, kounoune, darou thioub", 14.765717, -17.3120328),
    ("Yoff", "yoff, ouest foire , nord foire , auchan yoff", 14.7460066, -17.4981919),
    ("Castor", "khar yalla , zone de captage , grand yoff", 14.7245899, -17.4540061),
    ("Guediawaye", "guediawaye,malika", 14.7676938, -17.3717578),
    ("Plateau", "dakar plateau, sandaga", 14.6776122, -17.4484715),
    
    
]

for nom, alias, lat, lng in ZONES:
    if lat is None or lng is None:
        print("À compléter :", nom)
        continue
    # update_or_create : on peut relancer le script sans créer de doublons
    Zone.objects.update_or_create(
        nom=nom,
        defaults={'alias': alias, 'latitude': lat, 'longitude': lng},
    )
    print("OK :", nom)

# On donne leurs coordonnées aux trajets déjà créés
for t in Trajet.objects.all():
    d, a = trouver_zone(t.depart), trouver_zone(t.arrivee)
    t.depart_lat, t.depart_lng = (d.latitude, d.longitude) if d else (None, None)
    t.arrivee_lat, t.arrivee_lng = (a.latitude, a.longitude) if a else (None, None)
    t.save()
print("Trajets mis à jour :", Trajet.objects.count())