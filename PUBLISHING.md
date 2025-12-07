# Release & Publishing

Everything is automated in a single workflow: `.github/workflows/release.yml`

## One-time Setup

1. **PyPI**: Configure trusted publishing at https://pypi.org/manage/project/first-agentic-csa/settings/publishing/
   - Workflow: `release.yml`, Environment: `pypi`

2. **MCP Registry**: Create a GitHub PAT at https://github.com/settings/tokens (no scopes needed), add as secret `MCP_REGISTRY_TOKEN`

## To Release

1. Go to Actions → Release → Run workflow
2. Choose bump type: `patch`, `minor`, or `major`
3. Done! The workflow will:
   - Bump version in `pyproject.toml` and `server.json`
   - Create git tag and GitHub Release
   - Publish to PyPI
   - Publish to MCP Registry

## Manual MCP Registry Publish

```bash
# Install mcp-publisher
brew install mcp-publisher  # macOS
# or download from https://github.com/modelcontextprotocol/registry/releases

mcp-publisher login github
mcp-publisher publish
```
