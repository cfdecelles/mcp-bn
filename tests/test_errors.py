import json

from plaid.exceptions import ApiException

from plaid_mcp_bn.errors import PlaidError


def test_conversion_erreur_plaid():
    exc = ApiException(status=400, reason="Bad Request")
    exc.body = json.dumps({"error_type": "ITEM_ERROR", "error_code": "ITEM_LOGIN_REQUIRED",
                           "error_message": "the login details have changed",
                           "request_id": "req-1"})
    err = PlaidError.from_api_exception(exc)
    assert err.error_code == "ITEM_LOGIN_REQUIRED" and err.needs_relink
    assert err.request_id == "req-1" and err.status == 400


def test_corps_illisible():
    exc = ApiException(status=502, reason="Bad Gateway")
    exc.body = "<html>"
    err = PlaidError.from_api_exception(exc)
    assert err.error_code == "HTTP_502" and not err.needs_relink
