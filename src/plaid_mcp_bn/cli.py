"""Commandes : plaid-bn link [--update] | status | revoke."""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_config
from .errors import PlaidError
from .link import DEFAULT_PORT, LinkError, run_link
from .plaid_client import ReadOnlyPlaid
from .redact import masquer_compte, masquer_identifiant
from .token_store import TokenStore


def _cmd_link(args, client: ReadOnlyPlaid, store: TokenStore) -> int:
    if not args.update and store.load() is not None:
        print("Un compte est déjà lié dans cet environnement.\n"
              "  - Reconnexion (mot de passe changé, ITEM_LOGIN_REQUIRED) : plaid-bn link --update\n"
              "  - Repartir à zéro : plaid-bn revoke, puis plaid-bn link", file=sys.stderr)
        return 1
    result = run_link(client, store, update=args.update, port=args.port,
                      open_browser=not args.no_browser)
    action = "reconnecté" if args.update else "lié"
    print(f"Compte {action} : {result.institution or 'institution inconnue'}")
    for account in result.accounts:
        print(f"  - {account['name']} {masquer_compte(account['mask'])}")
    if not args.update:
        print(f"Jeton stocké dans : {store.location()}")
    return 0


def _cmd_status(args, client: ReadOnlyPlaid, store: TokenStore) -> int:
    stored = store.load()
    if stored is None:
        print("Aucun compte lié. Lancez : plaid-bn link")
        return 1
    print(f"Stockage   : {store.location()}")
    print(f"Item       : {masquer_identifiant(stored.item_id)}")
    item = client.get_item(stored.access_token)["item"]
    print(f"Institution: {item.get('institution_id') or '—'}")
    if item.get("consent_expiration_time"):
        print(f"Consentement expire le : {item['consent_expiration_time']}")
    if item.get("error"):
        code = item["error"].get("error_code")
        print(f"État       : ERREUR {code} — relancez : plaid-bn link --update")
    else:
        print("État       : OK")
    for account in client.get_accounts(stored.access_token)["accounts"]:
        print(f"  - {account['name']} ({account['subtype']}) {masquer_compte(account.get('mask'))}")
    return 0


def _cmd_revoke(args, client: ReadOnlyPlaid, store: TokenStore) -> int:
    stored = store.load()
    if stored is None:
        print("Aucun compte lié : rien à révoquer.")
        return 0
    if not args.yes:
        reponse = input(f"Révoquer définitivement l'accès Plaid ({store.env}) ? [o/N] ")
        if reponse.strip().lower() not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return 1
    try:
        client.remove_item(stored.access_token)
    except PlaidError as exc:
        # Item déjà supprimé côté Plaid : on nettoie quand même le jeton local
        if exc.error_code not in ("ITEM_NOT_FOUND", "INVALID_ACCESS_TOKEN"):
            raise
    store.delete()
    print("Accès révoqué chez Plaid (/item/remove) et jeton local supprimé.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plaid-bn", description="Liaison Plaid (lecture seule).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_link = sub.add_parser("link", help="lier un compte via Plaid Link")
    p_link.add_argument("--update", action="store_true",
                        help="reconnexion d'un compte existant (ITEM_LOGIN_REQUIRED)")
    p_link.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_link.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    p_link.set_defaults(func=_cmd_link)

    sub.add_parser("status", help="état de la liaison").set_defaults(func=_cmd_status)

    p_revoke = sub.add_parser("revoke", help="révoquer l'accès (/item/remove)")
    p_revoke.add_argument("--yes", action="store_true", help="sans confirmation")
    p_revoke.set_defaults(func=_cmd_revoke)

    args = parser.parse_args(argv)
    try:
        config = load_config()
        print(f"[environnement Plaid : {config.env}]", file=sys.stderr)
        return args.func(args, ReadOnlyPlaid(config), TokenStore(config.env))
    except (ConfigError, LinkError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Erreur : {exc} (port déjà utilisé ? essayez --port)", file=sys.stderr)
        return 1
    except PlaidError as exc:
        print(f"Erreur Plaid : {exc}", file=sys.stderr)
        if exc.needs_relink:
            print("Relancez la connexion : plaid-bn link --update", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
