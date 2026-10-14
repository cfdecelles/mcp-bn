import pytest

from plaid_mcp_bn.config import ConfigError, load_config


@pytest.fixture(autouse=True)
def _env_propre(monkeypatch, tmp_path):
    for var in ("PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ENV", "PLAID_REDIRECT_URI"):
        monkeypatch.delenv(var, raising=False)
    # Fichier .env vide pour ne jamais lire le vrai .env du projet
    vide = tmp_path / ".env"
    vide.write_text("")
    return vide


def test_variables_manquantes(_env_propre):
    with pytest.raises(ConfigError, match="PLAID_CLIENT_ID, PLAID_SECRET"):
        load_config(_env_propre)


def test_env_invalide(monkeypatch, _env_propre):
    monkeypatch.setenv("PLAID_CLIENT_ID", "id")
    monkeypatch.setenv("PLAID_SECRET", "s3cr3t")
    monkeypatch.setenv("PLAID_ENV", "development")
    with pytest.raises(ConfigError, match="PLAID_ENV"):
        load_config(_env_propre)


def test_lecture_fichier_env_et_secret_masque(tmp_path):
    fichier = tmp_path / ".env"
    fichier.write_text("PLAID_CLIENT_ID=id\nPLAID_SECRET=s3cr3t\nPLAID_ENV=Production\n")
    config = load_config(fichier)
    assert config.env == "production" and config.is_production
    assert "s3cr3t" not in repr(config)
