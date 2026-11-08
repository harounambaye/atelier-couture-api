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


def verifier_telephone(valeur: str) -> str:
    """Normalise le numéro (RG1) ou lève ValueError (=> 422 dans un schéma Pydantic)."""
    telephone = normaliser_telephone(valeur)
    if not telephone_est_valide(telephone):
        raise ValueError("Numéro de téléphone invalide : 6 à 20 chiffres, « + » initial facultatif")
    return telephone
