# Pre-Commit Hooks Setup

```bash
# Install pre-commit
uv pip install pre-commit

# Install hooks into repo
pre-commit install
```

Skip hooks if needed:

```bash
git commit --no-verify
```

## Troubleshooting

### Hook fails with merge markers

Resolve `<<<<<<<` or `>>>>>>>` manually.

### Ruff fails but code looks correct

```bash
uv run ruff check --fix .
```

### Disable a hook permanently

Edit `.pre-commit-config.yaml` and remove the hook's `id` line.
