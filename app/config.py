from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base de données
    database_url: str

    # Sécurité JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Premier administrateur (utilisé par python -m app.seed)
    admin_email: str
    admin_telephone: str
    admin_nom_complet: str
    admin_mot_de_passe: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()