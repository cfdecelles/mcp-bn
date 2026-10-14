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

## Utilisation

_À venir : liaison du compte (`plaid-bn link`), serveur MCP, configuration Claude Desktop,
révocation (`plaid-bn revoke`)._
