# Contributing to Discordeerr

## Setup

```bash
git clone https://github.com/your-username/discordeerr.git
cd discordeerr
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install ruff black pre-commit
pre-commit install
cp env.example .env
# Edit .env with your config
```

> [!NOTE]
> Make sure to fork the repository first on GitHub before cloning.

## Code Style

- **Black** for formatting
- **Ruff** for linting
- **Type hints** required
- **Google-style docstrings**

```bash
black .
ruff check . --fix
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
feat(admin): add force-link command
fix(webhook): handle null username
docs: update README
```

## Pull Request

1. Create feature branch: `git checkout -b feature/name`
2. Make changes following code style
3. Test locally
4. Rebase on main: `git rebase main`
5. Push and create PR

> [!TIP]
> Keep PRs focused on a single feature or fix. Large changes should be split into multiple PRs.

## Issues

- Check existing issues first
- Provide clear description and steps to reproduce
- Include environment details and logs

> [!WARNING]
> Please search existing issues before creating new ones to avoid duplicates.
