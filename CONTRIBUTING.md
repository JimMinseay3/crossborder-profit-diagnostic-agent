# Contributing

Thanks for helping improve this cross-border ecommerce agent prototype.

## Development setup

1. Create and activate a Python virtual environment.
2. Install dependencies with `python -m pip install -r requirements.txt`.
3. Keep `MODEL_PROVIDER=mock` while developing deterministic behavior.
4. Run `python -m pytest -q` before opening a pull request.

## Design principles

- Keep business calculations and safety decisions deterministic and testable.
- Treat model output as optional enhancement, never as hidden ground truth.
- Preserve evidence, warnings, and human-review reasons in every run.
- Do not commit credentials, customer personal data, store exports, or SQLite databases.
- Add synthetic fixtures and regression tests for every new rule.

## Pull requests

Describe the business problem, expected behavior, test evidence, and any change to safety boundaries. Small, focused pull requests are preferred.

