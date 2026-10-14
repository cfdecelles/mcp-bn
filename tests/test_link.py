"""Serveur de liaison local, avec un faux client Plaid (aucun appel réseau)."""

import json
import re
import socket
import threading
import urllib.error
import urllib.request

import pytest

from plaid_mcp_bn.link import LinkError, run_link
from plaid_mcp_bn.token_store import StoredItem, TokenStore


class FauxClient:
    def __init__(self):
        self.echanges = []
        self.tokens_update = []

    def create_link_token(self, access_token=None):
        self.tokens_update.append(access_token)
        return "link-sandbox-</script>-abc"

    def exchange_public_token(self, public_token):
        self.echanges.append(public_token)
        return "access-sandbox-xyz", "item-42"


def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _requete(port, chemin, donnees=None, host=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{chemin}",
        data=json.dumps(donnees).encode() if donnees is not None else None,
        headers={"Content-Type": "application/json", "Host": host or f"127.0.0.1:{port}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as rep:
            return rep.status, rep.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def _lancer(client, store, **kwargs):
    port = _port_libre()
    sortie = {}

    def cible():
        try:
            sortie["resultat"] = run_link(client, store, port=port, open_browser=False,
                                          timeout=10, **kwargs)
        except Exception as exc:  # noqa: BLE001
            sortie["erreur"] = exc

    thread = threading.Thread(target=cible)
    thread.start()
    for _ in range(100):  # attendre le démarrage du serveur
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            threading.Event().wait(0.05)
    return port, thread, sortie


def _nonce(page):
    cfg = re.search(r'<script id="cfg" type="application/json">(.*?)</script>', page, re.DOTALL)
    return json.loads(cfg.group(1).replace("<\\/", "</"))["nonce"]


@pytest.fixture
def store(tmp_path):
    return TokenStore("sandbox", app_dir=tmp_path, use_keyring=False)


def test_liaison_complete(store):
    client = FauxClient()
    port, thread, sortie = _lancer(client, store)

    statut, page = _requete(port, "/")
    assert statut == 200
    assert "link-sandbox-<\\/script>-abc" in page, "le jeton doit être échappé"
    nonce = _nonce(page)

    assert _requete(port, "/", host="evil.example:80")[0] == 403
    assert _requete(port, "/api/success", {"nonce": "faux", "public_token": "p"})[0] == 403

    statut, _ = _requete(port, "/api/success", {
        "nonce": nonce, "public_token": "public-sandbox-1",
        "institution": "Banque Nationale",
        "accounts": [{"name": "Chèques", "mask": "1234"}],
    })
    thread.join(5)
    assert statut == 200
    assert client.echanges == ["public-sandbox-1"]
    assert store.load() == StoredItem("access-sandbox-xyz", "item-42")
    assert sortie["resultat"].institution == "Banque Nationale"


def test_annulation(store):
    port, thread, sortie = _lancer(FauxClient(), store)
    nonce = _nonce(_requete(port, "/")[1])
    _requete(port, "/api/exit", {"nonce": nonce})
    thread.join(5)
    assert isinstance(sortie["erreur"], LinkError)
    assert store.load() is None


def test_mode_update_sans_echange(store):
    store.save(StoredItem("access-existant", "item-1"))
    client = FauxClient()
    port, thread, sortie = _lancer(client, store, update=True)
    nonce = _nonce(_requete(port, "/oauth-return?oauth_state_id=x")[1])
    _requete(port, "/api/success", {"nonce": nonce, "public_token": "ignoré"})
    thread.join(5)
    assert "erreur" not in sortie
    assert client.tokens_update == ["access-existant"]
    assert client.echanges == []
    assert store.load().access_token == "access-existant"


def test_mode_update_sans_compte_lie(store):
    with pytest.raises(LinkError):
        run_link(FauxClient(), store, update=True, open_browser=False)
