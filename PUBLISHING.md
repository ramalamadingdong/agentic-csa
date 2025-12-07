# Publishing to MCP Registry

Publish to the official MCP Registry at [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).

## Automated Publishing

The workflow `.github/workflows/publish-mcp-registry.yml` automatically publishes after PyPI publication.

### Setup (one-time)

1. Create a GitHub PAT at https://github.com/settings/tokens (no scopes needed for public repos)
2. Add it as repository secret: Settings → Secrets → `MCP_REGISTRY_TOKEN`

The workflow runs automatically after each PyPI publish, or manually via workflow_dispatch.

## Manual Publishing

```bash
# Login (opens browser for GitHub OAuth)
npx @modelcontextprotocol/publisher login

# Validate and publish
npx @modelcontextprotocol/publisher validate server.json
npx @modelcontextprotocol/publisher publish server.json
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Auth errors | Run `npx @modelcontextprotocol/publisher login` |
| Validation errors | Check `server.json` matches schema, version matches PyPI |
| Publish fails | Ensure package is on PyPI first, server name is unique |

## Resources

- [MCP Registry Docs](https://modelcontextprotocol.info/tools/registry/)
- [VS Code MCP Guide](https://code.visualstudio.com/api/extension-guides/mcp)
