import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app

# --- Sécurité : on ne lance jamais les tests sur la base de développement ---
if not settings.test_database_url:
    pytest.exit("TEST_DATABASE_URL est absente du fichier .env")
if settings.test_database_url == settings.database_url:
    pytest.exit("TEST_DATABASE_URL doit être différente de DATABASE_URL")

engine_test = create_engine(settings.test_database_url)
SessionTest = sessionmaker(bind=engine_test, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def preparer_base_de_test():
    # Crée le schéma avec les migrations Alembic (comme en production)
    config_alembic = Config("alembic.ini")
    config_alembic.set_main_option(
        "sqlalchemy.url", settings.test_database_url.replace("%", "%%")
    )
    command.upgrade(config_alembic, "head")
    yield
    engine_test.dispose()


@pytest.fixture(autouse=True)
def vider_les_tables():
    yield
    # Après chaque test : on vide toutes les tables (les enfants d'abord)
    with engine_test.begin() as connexion:
        for table in reversed(Base.metadata.sorted_tables):
            connexion.execute(table.delete())


@pytest.fixture
def db():
    session = SessionTest()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def get_db_test():
        session = SessionTest()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = get_db_test
    with TestClient(app) as client_test:
        yield client_test
    app.dependency_overrides.clear()