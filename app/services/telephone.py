CARACTERES_A_SUPPRIMER = [" ", ".", "-", "(", ")"]


def normaliser_telephone(telephone: str) -> str:
    resultat = telephone.strip()
    for caractere in CARACTERES_A_SUPPRIMER:
        resultat = resultat.replace(caractere, "")
    return resultat


def telephone_est_valide(telephone: str) -> bool:
    chiffres = telephone
    if chiffres.startswith("+"):
        chiffres = chiffres[1:]
    if not chiffres.isascii() or not chiffres.isdigit():
        return False
    return 6 <= len(chiffres) <= 20