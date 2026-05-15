# Contributing to VexDB Active Memory

Thanks for your interest! Here's how to contribute.

## Getting Started

```bash
git clone https://github.com/MiniosZou/vexdb-active-memory.git
cd vexdb-active-memory
python -m pip install -e .[dev]
```

## Running Tests

```bash
# Unit tests (no database needed)
python -m pytest tests -k "not integration"

# Full suite (requires VexDB running)
python -m pytest tests

# CLI smoke tests
PYTHONPATH=python python -m vexdb_active_memory.cli mcp-smoke
PYTHONPATH=python python -m vexdb_active_memory.cli smoke-test
PYTHONPATH=python python -m vexdb_active_memory.cli conflict-decay-test
```

## Code Style

- Python 3.10+, type hints, no external linter required for v0.1
- Keep SQL functions in `sql/` in order: schema → functions → triggers → indexes → hooks
- Test file naming: `test_<module>.py`

## Pull Requests

1. Fork the repo and create your branch from `main`
2. Make sure tests pass: `python -m pytest tests`
3. Add/update tests for your changes
4. Update `CHANGELOG.md` with your change
5. Open a PR with a clear description of what and why

## Reporting Issues

- Bug reports: include VexDB version, Python version, error message, and reproduction steps
- Feature requests: describe the use case and expected behavior
- Security issues: please email privately before opening a public issue

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
