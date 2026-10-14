"""Client Plaid restreint à une liste blanche d'appels en lecture seule.

C'est le SEUL module autorisé à manipuler `PlaidApi`. Aucun endpoint de paiement,
de transfert ou d'écriture sur le compte n'est exposé (vérifié par tests/test_lecture_seule.py).
"""

from __future__ import annotations

from typing import Any

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_transactions import LinkTokenTransactions
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from .config import CLIENT_NAME, COUNTRY_CODES, LANGUAGE, PRODUCTS, Config
from .errors import PlaidError

_HOSTS = {"sandbox": plaid.Environment.Sandbox, "production": plaid.Environment.Production}

# Identifiant stable et non personnel de l'utilisateur unique de cet outil
_CLIENT_USER_ID = "plaid-mcp-bn-local-user"

# Historique demandé à la première liaison (maximum permis par Plaid)
_DAYS_REQUESTED = 730


class ReadOnlyPlaid:
    def __init__(self, config: Config):
        self.config = config
        configuration = plaid.Configuration(
            host=_HOSTS[config.env],
            api_key={"clientId": config.client_id, "secret": config.secret},
        )
        self._api = plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def _call(self, method: str, request: Any) -> dict:
        try:
            return getattr(self._api, method)(request).to_dict()
        except ApiException as exc:
            raise PlaidError.from_api_exception(exc) from None

    # --- Liaison ----------------------------------------------------------------

    def create_link_token(self, access_token: str | None = None) -> str:
        """Crée un link_token. Avec un access_token : mode update (reconnexion)."""
        kwargs: dict[str, Any] = {
            "client_name": CLIENT_NAME,
            "language": LANGUAGE,
            "country_codes": [CountryCode(c) for c in COUNTRY_CODES],
            "user": LinkTokenCreateRequestUser(client_user_id=_CLIENT_USER_ID),
        }
        if access_token:
            kwargs["access_token"] = access_token  # mode update : pas de products
        else:
            kwargs["products"] = [Products(p) for p in PRODUCTS]
            kwargs["transactions"] = LinkTokenTransactions(days_requested=_DAYS_REQUESTED)
        if self.config.redirect_uri:
            kwargs["redirect_uri"] = self.config.redirect_uri
        return self._call("link_token_create", LinkTokenCreateRequest(**kwargs))["link_token"]

    def exchange_public_token(self, public_token: str) -> tuple[str, str]:
        """Retourne (access_token, item_id)."""
        resp = self._call("item_public_token_exchange",
                          ItemPublicTokenExchangeRequest(public_token=public_token))
        return resp["access_token"], resp["item_id"]

    # --- Lecture ----------------------------------------------------------------

    def get_item(self, access_token: str) -> dict:
        return self._call("item_get", ItemGetRequest(access_token=access_token))

    def get_accounts(self, access_token: str) -> dict:
        return self._call("accounts_get", AccountsGetRequest(access_token=access_token))

    def get_balances(self, access_token: str) -> dict:
        return self._call("accounts_balance_get",
                          AccountsBalanceGetRequest(access_token=access_token))

    def sync_transactions(self, access_token: str, cursor: str | None = None,
                          count: int = 500) -> dict:
        kwargs: dict[str, Any] = {"access_token": access_token, "count": count}
        if cursor:
            kwargs["cursor"] = cursor
        return self._call("transactions_sync", TransactionsSyncRequest(**kwargs))

    # --- Révocation -------------------------------------------------------------

    def remove_item(self, access_token: str) -> None:
        self._call("item_remove", ItemRemoveRequest(access_token=access_token))
