"""Construction des requêtes Plaid, sans réseau."""

import pytest

from plaid_mcp_bn.config import Config
from plaid_mcp_bn.plaid_client import ReadOnlyPlaid


@pytest.fixture
def capture(monkeypatch):
    client = ReadOnlyPlaid(Config(client_id="id", secret="s", env="sandbox",
                                  redirect_uri="http://localhost:8765/oauth-return"))
    appels = []

    def faux_call(method, request):
        appels.append((method, request.to_dict()))
        return {"link_token": "link-sandbox-1"}

    monkeypatch.setattr(client, "_call", faux_call)
    return client, appels


def test_link_token_initial(capture):
    client, appels = capture
    client.create_link_token()
    method, req = appels[0]
    assert method == "link_token_create"
    assert req["country_codes"] == ["CA"] and req["language"] == "fr"
    assert req["products"] == ["transactions"]
    assert req["transactions"] == {"days_requested": 730}
    assert req["redirect_uri"] == "http://localhost:8765/oauth-return"
    assert "access_token" not in req


def test_link_token_mode_update(capture):
    client, appels = capture
    client.create_link_token(access_token="access-sandbox-1")
    _, req = appels[0]
    assert req["access_token"] == "access-sandbox-1"
    assert "products" not in req
