from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

hacheur = PasswordHasher()


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return hacheur.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, mot_de_passe_hash: str) -> bool:
    try:
        return hacheur.verify(mot_de_passe_hash, mot_de_passe)
    except (VerificationError, InvalidHashError):
        return False


def creer_jeton(utilisateur_id: int) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    contenu = {"sub": str(utilisateur_id), "exp": expiration}
    return jwt.encode(contenu, settings.secret_key, algorithm=settings.algorithm)


def lire_jeton(jeton: str) -> int | None:
    try:
        contenu = jwt.decode(
            jeton,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    return int(contenu["sub"])