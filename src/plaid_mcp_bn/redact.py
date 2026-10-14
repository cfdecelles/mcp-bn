"""Masquage des données sensibles avant tout affichage ou journal."""

from __future__ import annotations


def masquer_compte(mask: str | None) -> str:
    """Affiche seulement les derniers chiffres fournis par Plaid (« mask »), jamais le numéro complet."""
    return f"••••{mask}" if mask else "••••"


def masquer_identifiant(value: str | None, visible: int = 6) -> str:
    """Tronque un identifiant opaque (item_id, account_id) pour l'affichage."""
    if not value:
        return "—"
    return value[:visible] + "…" if len(value) > visible else value
