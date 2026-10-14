# plaid-mcp-bn

Serveur MCP (FastMCP, transport stdio) qui permet à Claude de consulter **en lecture seule**
un compte de la Banque Nationale via l'API Plaid.

## Sécurité

- Lecture seule stricte : aucun endpoint de paiement ou de transfert n'est appelé.
- Aucun secret ni jeton dans git : `.env` est exclu ; l'`access_token` est stocké dans le
  trousseau macOS (repli : `~/.config/plaid-mcp-bn/`, permissions `600`).
- Les journaux ne contiennent ni numéros de compte complets ni données de transactions brutes.
- Les transactions sont gardées en mémoire seulement, jamais écrites sur le disque.

## Installation

```bash
uv sync
cp .env.example .env   # puis remplir PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV
uv run pytest
```

## Liaison du compte

```bash
uv run plaid-bn link            # ouvre Plaid Link sur http://localhost:8765/
uv run plaid-bn status          # état de la liaison et comptes (numéros masqués)
uv run plaid-bn link --update   # reconnexion après ITEM_LOGIN_REQUIRED
uv run plaid-bn revoke          # révoque l'accès chez Plaid (/item/remove) et efface le jeton
```

En Sandbox, utilisez les identifiants de test `user_good` / `pass_good`.

Un jeton est conservé par environnement (`sandbox`, `production`) : changer `PLAID_ENV`
ne détruit pas l'autre.

Si l'institution exige OAuth en Production, enregistrez `http://localhost:8765/oauth-return`
dans le tableau de bord Plaid (API > Allowed redirect URIs) et dans `PLAID_REDIRECT_URI`.

## Tests

```bash
uv run pytest            # tests unitaires, sans réseau
uv run pytest -m sandbox # intégration réelle avec Plaid Sandbox (clés Sandbox requises)
```

## À venir

Serveur MCP, configuration Claude Desktop.
