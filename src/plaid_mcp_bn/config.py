"""Configuration : lecture du .env et constantes Plaid du projet."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Racine du dépôt (src/plaid_mcp_bn/config.py -> ../../)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Paramètres Plaid fixes pour ce projet
COUNTRY_CODES = ["CA"]
LANGUAGE = "fr"
PRODUCTS = ["transactions"]
CLIENT_NAME = "plaid-mcp-bn"

# Stockage local hors dépôt (repli du jeton si le trousseau est indisponible)
APP_DIR = Path(os.environ.get("PLAID_MCP_BN_HOME", Path.home() / ".config" / "plaid-mcp-bn"))

_VALID_ENVS = ("sandbox", "production")


class ConfigError(RuntimeError):
    """Configuration absente ou invalide."""


@dataclass(frozen=True)
class Config:
    client_id: str
    secret: str = field(repr=False)
    env: str
    redirect_uri: str | None = None

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def load_config(env_file: Path | None = None) -> Config:
    """Charge la configuration depuis l'environnement, complété par le .env du projet.

    Les variables déjà définies (ex. par Claude Desktop) ont priorité sur le .env.
    """
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)

    client_id = os.environ.get("PLAID_CLIENT_ID", "").strip()
    secret = os.environ.get("PLAID_SECRET", "").strip()
    env = os.environ.get("PLAID_ENV", "sandbox").strip().lower()
    redirect_uri = os.environ.get("PLAID_REDIRECT_URI", "").strip() or None

    missing = [name for name, value in (("PLAID_CLIENT_ID", client_id),
                                        ("PLAID_SECRET", secret)) if not value]
    if missing:
        raise ConfigError(
            f"Variables manquantes : {', '.join(missing)}. "
            "Copiez .env.example vers .env et remplissez-le."
        )
    if env not in _VALID_ENVS:
        raise ConfigError(f"PLAID_ENV doit valoir {' ou '.join(_VALID_ENVS)} (reçu : {env!r}).")

    return Config(client_id=client_id, secret=secret, env=env, redirect_uri=redirect_uri)
