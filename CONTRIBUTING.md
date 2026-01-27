# Contributing

## Branch Strategy

This project uses a two-branch workflow:

```
feature branches → dev → main
```

### Branches

| Branch | Purpose | PyPI Package | Auto-publish |
|--------|---------|-------------|--------------|
| `main` | Stable releases | `first-agentic-csa` | Manual (workflow_dispatch) |
| `dev` | Pre-release testing | `first-agentic-csa-dev` | On push to dev |

### Workflow

1. **Create a feature branch** off `dev`:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-change
   ```

2. **Make your changes**, commit, and push:
   ```bash
   git push -u origin feature/my-change
   ```

3. **Open a PR targeting `dev`**. CI will run tests automatically.

4. **Merge into `dev`**. This triggers:
   - CI tests on Python 3.11 and 3.12
   - Auto-publish to PyPI as `first-agentic-csa-dev` (dev release)
   - Testers can install with `uvx first-agentic-csa-dev`

5. **When dev is stable**, open a PR from `dev` → `main`.

6. **After merging to main**, manually trigger the Release workflow:
   - Go to Actions → Release → Run workflow
   - Choose patch/minor/major bump
   - This publishes to PyPI as `first-agentic-csa` and the MCP Registry

### Important Notes

- **Never push directly to `main`** — always go through `dev` first
- **`dev` branch** uses package name `first-agentic-csa-dev` and `.devN` versions
- **`main` branch** uses package name `first-agentic-csa` and clean semver versions
- Both release workflows verify the correct package name before publishing

## Development Setup

```bash
git clone https://github.com/ramalamadingdong/agentic-csa.git
cd agentic-csa
git checkout dev
uv sync --all-extras
uv run pytest tests/ -v
```

## Running Tests

```bash
uv run pytest tests/ -v
```
