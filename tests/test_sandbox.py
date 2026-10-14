"""Intégration réelle avec Plaid Sandbox : uv run pytest -m sandbox

Requiert PLAID_CLIENT_ID / PLAID_SECRET Sandbox dans .env. Ne touche pas au jeton stocké.
"""

import os

import pytest
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest

from plaid_mcp_bn.config import load_config
from plaid_mcp_bn.plaid_client import ReadOnlyPlaid

pytestmark = pytest.mark.sandbox

# Institution Sandbox ; surcharger si elle n'est pas offerte pour le Canada
INSTITUTION = os.environ.get("PLAID_SANDBOX_INSTITUTION", "ins_109508")


@pytest.fixture(scope="module")
def client():
    config = load_config()
    if config.env != "sandbox":
        pytest.skip("Les tests d'intégration s'exécutent seulement en Sandbox.")
    return ReadOnlyPlaid(config)


@pytest.fixture(scope="module")
def access_token(client):
    # Endpoint propre au Sandbox, utilisé ici seulement (jamais dans le code de l'application)
    public_token = client._api.sandbox_public_token_create(SandboxPublicTokenCreateRequest(
        institution_id=INSTITUTION, initial_products=[Products("transactions")],
    )).public_token
    token, _item_id = client.exchange_public_token(public_token)
    yield token
    client.remove_item(token)


def test_link_token(client):
    assert client.create_link_token().startswith("link-sandbox-")


def test_comptes_et_item(client, access_token):
    assert client.get_accounts(access_token)["accounts"]
    assert client.get_item(access_token)["item"]["item_id"]
