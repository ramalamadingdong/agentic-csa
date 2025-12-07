# Publishing to MCP Registry

Publish to the official MCP Registry at [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).

## Automated Publishing

The workflow `.github/workflows/publish-mcp-registry.yml` automatically publishes after PyPI publication.

### Setup (one-time)

1. Create a GitHub PAT at https://github.com/settings/tokens (no scopes needed for public repos)
2. Add it as repository secret: Settings → Secrets → `MCP_REGISTRY_TOKEN`

## Manual Publishing

```bash
npx @modelcontextprotocol/publisher login
npx @modelcontextprotocol/publisher publish server.json
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Auth errors | Run `npx @modelcontextprotocol/publisher login` |
| Validation errors | Check `server.json` version matches PyPI |
| Publish fails | Ensure package is on PyPI first |
