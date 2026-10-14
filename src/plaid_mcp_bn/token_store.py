"""Stockage de l'access_token : trousseau (keyring) de préférence, sinon fichier 600 hors dépôt.

Un jeton par environnement (sandbox / production), pour que les deux coexistent.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import keyring
from keyring.backends import fail
from keyring.errors import KeyringError

from . import config

SERVICE = "plaid-mcp-bn"


@dataclass(frozen=True)
class StoredItem:
    access_token: str = field(repr=False)
    item_id: str


def _keyring_available() -> bool:
    return not isinstance(keyring.get_keyring(), fail.Keyring)


class TokenStore:
    def __init__(self, env: str, app_dir: Path | None = None, use_keyring: bool | None = None):
        self.env = env
        self.app_dir = app_dir or config.APP_DIR
        self.use_keyring = _keyring_available() if use_keyring is None else use_keyring

    @property
    def _key(self) -> str:
        return f"item:{self.env}"

    @property
    def _file(self) -> Path:
        return self.app_dir / f"{self.env}.json"

    def location(self) -> str:
        return f"trousseau ({SERVICE})" if self.use_keyring else str(self._file)

    def save(self, item: StoredItem) -> None:
        payload = json.dumps(asdict(item))
        if self.use_keyring:
            try:
                keyring.set_password(SERVICE, self._key, payload)
                return
            except KeyringError:
                self.use_keyring = False
        self.app_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.app_dir, 0o700)
        # Création directe en 600 : le jeton n'est jamais lisible par d'autres, même brièvement
        fd = os.open(self._file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(payload)
        os.chmod(self._file, 0o600)

    def load(self) -> StoredItem | None:
        payload = None
        if self.use_keyring:
            try:
                payload = keyring.get_password(SERVICE, self._key)
            except KeyringError:
                payload = None
        if payload is None and self._file.exists():
            payload = self._file.read_text()
        return StoredItem(**json.loads(payload)) if payload else None

    def delete(self) -> None:
        if self.use_keyring:
            try:
                keyring.delete_password(SERVICE, self._key)
            except KeyringError:
                pass
        self._file.unlink(missing_ok=True)
