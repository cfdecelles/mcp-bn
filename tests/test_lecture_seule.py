"""Garantit par analyse statique que le code n'appelle que des endpoints Plaid autorisés."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "plaid_mcp_bn"

AUTORISES = {
    "link_token_create",
    "item_public_token_exchange",
    "item_get",
    "accounts_get",
    "accounts_balance_get",
    "transactions_sync",
    "item_remove",
}


def _arbre(nom: str) -> ast.Module:
    return ast.parse((PKG / nom).read_text())


def test_seul_plaid_client_utilise_plaid_api():
    for fichier in PKG.glob("*.py"):
        if fichier.name == "plaid_client.py":
            continue
        source = fichier.read_text()
        assert "plaid.api" not in source and "PlaidApi" not in source, fichier.name
        assert "._api" not in source, fichier.name


def test_appels_plaid_dans_la_liste_blanche():
    appels = set()
    acces_directs = []
    for node in ast.walk(_arbre("plaid_client.py")):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_call"):
            premier = node.args[0]
            assert isinstance(premier, ast.Constant), "le nom d'endpoint doit être littéral"
            appels.add(premier.value)
        # Tout accès self._api.<méthode> contournerait la liste blanche
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                and node.value.attr == "_api"):
            acces_directs.append(node.attr)
    assert appels <= AUTORISES, appels - AUTORISES
    assert not acces_directs, acces_directs


def test_aucun_modele_de_paiement_importe():
    interdits = ("transfer", "payment", "bank_transfer", "signal", "processor", "sandbox")
    for node in ast.walk(_arbre("plaid_client.py")):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("plaid.model"):
            assert not any(m in node.module for m in interdits), node.module
