"""Liaison du compte via Plaid Link, servi par une page HTML locale (127.0.0.1 seulement).

Flux : link_token → page locale → Plaid Link → public_token → access_token → trousseau.
En mode update (ITEM_LOGIN_REQUIRED), l'access_token existant reste valide : aucun échange.
"""

from __future__ import annotations

import hmac
import json
import secrets
import threading
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import urlsplit

from .errors import PlaidError
from .plaid_client import ReadOnlyPlaid
from .token_store import StoredItem, TokenStore

DEFAULT_PORT = 8765
OAUTH_PATH = "/oauth-return"  # à utiliser dans PLAID_REDIRECT_URI : http://localhost:8765/oauth-return
_MAX_BODY = 16 * 1024


class LinkError(RuntimeError):
    """La liaison n'a pas abouti (annulée, erreur Plaid, délai dépassé)."""


@dataclass
class LinkResult:
    institution: str | None = None
    accounts: list[dict] = field(default_factory=list)  # [{"name": ..., "mask": ...}]


@dataclass
class _Session:
    client: ReadOnlyPlaid
    store: TokenStore
    update: bool
    link_token: str
    port: int
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    done: threading.Event = field(default_factory=threading.Event)
    result: LinkResult | None = None
    error: str | None = None


def _render_page(session: _Session) -> bytes:
    template = resources.files(__package__).joinpath("static/link.html").read_text("utf-8")
    cfg = json.dumps({"link_token": session.link_token, "nonce": session.nonce,
                      "update": session.update, "oauth_path": OAUTH_PATH})
    # Empêche toute fermeture prématurée de la balise <script>
    return template.replace("__CONFIG__", cfg.replace("</", "<\\/")).encode("utf-8")


def _make_handler(session: _Session) -> type[BaseHTTPRequestHandler]:
    allowed_hosts = {f"localhost:{session.port}", f"127.0.0.1:{session.port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "plaid-mcp-bn"

        def log_message(self, *args):  # aucune URL ni corps de requête dans les journaux
            pass

        def _send(self, status: HTTPStatus, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: HTTPStatus, payload: dict) -> None:
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _host_ok(self) -> bool:
            # Protection contre le DNS rebinding
            return self.headers.get("Host", "") in allowed_hosts

        def do_GET(self):
            if not self._host_ok():
                return self._send(HTTPStatus.FORBIDDEN, b"", "text/plain")
            if urlsplit(self.path).path in ("/", OAUTH_PATH):
                return self._send(HTTPStatus.OK, _render_page(session), "text/html; charset=utf-8")
            self._send(HTTPStatus.NOT_FOUND, b"", "text/plain")

        def do_POST(self):
            if not self._host_ok():
                return self._send(HTTPStatus.FORBIDDEN, b"", "text/plain")
            length = int(self.headers.get("Content-Length") or 0)
            if length > _MAX_BODY or "application/json" not in self.headers.get("Content-Type", ""):
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
            try:
                data = json.loads(self.rfile.read(length))
            except ValueError:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
            if not hmac.compare_digest(str(data.get("nonce", "")), session.nonce):
                return self._json(HTTPStatus.FORBIDDEN, {"ok": False})
            if session.done.is_set():
                return self._json(HTTPStatus.CONFLICT, {"ok": False, "message": "Déjà terminé."})

            path = urlsplit(self.path).path
            if path == "/api/success":
                return self._on_success(data)
            if path == "/api/exit":
                code = data.get("error_code")
                msg = data.get("error_message")
                session.error = f"{code} : {msg}" if code else "Liaison annulée."
                session.done.set()
                return self._json(HTTPStatus.OK, {"ok": True})
            self._json(HTTPStatus.NOT_FOUND, {"ok": False})

        def _on_success(self, data: dict) -> None:
            result = LinkResult(
                institution=data.get("institution"),
                accounts=[{"name": a.get("name"), "mask": a.get("mask")}
                          for a in data.get("accounts") or [] if isinstance(a, dict)],
            )
            if not session.update:
                public_token = data.get("public_token")
                if not isinstance(public_token, str) or not public_token:
                    return self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
                try:
                    access_token, item_id = session.client.exchange_public_token(public_token)
                    session.store.save(StoredItem(access_token=access_token, item_id=item_id))
                except PlaidError as exc:
                    session.error = str(exc)
                    session.done.set()
                    return self._json(HTTPStatus.BAD_GATEWAY, {"ok": False, "message": str(exc)})
            session.result = result
            session.done.set()
            self._json(HTTPStatus.OK, {"ok": True})

    return Handler


def run_link(client: ReadOnlyPlaid, store: TokenStore, *, update: bool = False,
             port: int = DEFAULT_PORT, open_browser: bool = True,
             timeout: float = 600) -> LinkResult:
    """Lance Plaid Link et bloque jusqu'au succès, à l'annulation ou au délai."""
    access_token = None
    if update:
        existing = store.load()
        if existing is None:
            raise LinkError("Aucun compte lié : lancez d'abord « plaid-bn link ».")
        access_token = existing.access_token

    session = _Session(client=client, store=store, update=update, port=port,
                       link_token=client.create_link_token(access_token=access_token))
    server = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(session))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://localhost:{port}/"
    try:
        print(f"Ouvrez {url} pour vous connecter à votre banque.")
        if open_browser:
            webbrowser.open(url)
        if not session.done.wait(timeout):
            raise LinkError("Délai dépassé : liaison non terminée.")
    finally:
        server.shutdown()
        server.server_close()

    if session.error:
        raise LinkError(session.error)
    assert session.result is not None
    return session.result
