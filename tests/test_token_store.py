import stat

import keyring
import pytest
from keyring.backend import KeyringBackend

from plaid_mcp_bn.token_store import StoredItem, TokenStore


class MemoireKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.data = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        self.data.pop((service, username), None)


ITEM = StoredItem(access_token="access-sandbox-secret", item_id="item-123")


def test_repli_fichier_permissions_600(tmp_path):
    app_dir = tmp_path / "app"
    store = TokenStore("sandbox", app_dir=app_dir, use_keyring=False)
    store.save(ITEM)
    fichier = app_dir / "sandbox.json"
    assert stat.S_IMODE(fichier.stat().st_mode) == 0o600
    assert stat.S_IMODE(app_dir.stat().st_mode) == 0o700
    assert store.load() == ITEM
    store.delete()
    assert store.load() is None and not fichier.exists()


def test_trousseau_et_environnements_separes(tmp_path):
    precedent = keyring.get_keyring()
    backend = MemoireKeyring()
    keyring.set_keyring(backend)
    try:
        sandbox = TokenStore("sandbox", app_dir=tmp_path, use_keyring=True)
        production = TokenStore("production", app_dir=tmp_path, use_keyring=True)
        sandbox.save(ITEM)
        assert sandbox.load() == ITEM
        assert production.load() is None
        assert not list(tmp_path.iterdir()), "rien ne doit être écrit sur le disque"
        sandbox.delete()
        assert sandbox.load() is None
    finally:
        keyring.set_keyring(precedent)


@pytest.mark.parametrize("valeur", [ITEM])
def test_jeton_absent_du_repr(valeur):
    assert "access-sandbox-secret" not in repr(valeur)
