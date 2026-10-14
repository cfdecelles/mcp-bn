"""Erreurs Plaid normalisées (la gestion fine — reprises, limites de taux — vient à l'étape 4)."""

from __future__ import annotations

import json

from plaid.exceptions import ApiException

# Codes qui exigent de relancer Link en mode update
LOGIN_REQUIRED_CODES = {"ITEM_LOGIN_REQUIRED", "PENDING_EXPIRATION", "PENDING_DISCONNECT"}


class PlaidError(RuntimeError):
    """Erreur renvoyée par Plaid, sans aucune donnée sensible."""

    def __init__(self, error_type: str, error_code: str, message: str,
                 request_id: str | None = None, status: int | None = None):
        self.error_type = error_type
        self.error_code = error_code
        self.request_id = request_id
        self.status = status
        super().__init__(f"{error_code} ({error_type}) : {message}")

    @property
    def needs_relink(self) -> bool:
        return self.error_code in LOGIN_REQUIRED_CODES

    @classmethod
    def from_api_exception(cls, exc: ApiException) -> PlaidError:
        try:
            body = json.loads(exc.body or "{}")
        except (TypeError, ValueError):
            body = {}
        return cls(
            error_type=body.get("error_type", "API_ERROR"),
            error_code=body.get("error_code", f"HTTP_{exc.status}"),
            message=body.get("display_message") or body.get("error_message") or str(exc.reason),
            request_id=body.get("request_id"),
            status=exc.status,
        )
