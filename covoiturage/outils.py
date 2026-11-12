import re


def normaliser_telephone(valeur):
    chiffres = re.sub(r'\D', '', valeur or '')
    if chiffres.startswith('221') and len(chiffres) == 12:
        chiffres = chiffres[3:]
    return chiffres