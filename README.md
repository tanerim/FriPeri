# FriPeri

<p align="center">
  <img src="static/images/FriPeri_Logo.png" alt="FriPeri logo" height="210">
</p>

<p align="center"><strong>A free, self-hosted personal publishing framework.</strong></p>

FriPeri lets you build and publish a personal website, blog, portfolio, or project site from your own server. It combines a public website and a browser-based admin panel, with SQLite storage, a multilingual content editor, and a choice of automatic content feeds or a fully customizable homepage.

Built with **Python · FastAPI · SQLite · Jinja2**. No external database server, Node.js runtime, hosted editor account, or frontend build is required to run the distributed application.

## At a glance

- **Publish:** articles, notes, categories, tags, custom pages, and an About page using a visual block editor.
- **Customize:** choose a content-feed homepage or build a custom layout with reusable blocks, images, and video.
- **Organize:** nested navigation, category presentation controls, built-in social profile links, and contact messages.
- **Translate:** English content with an optional secondary language and English fallback.
- **Manage:** browser-based first-run installation, administrator login, media cropping, backups, and recovery.
- **Own your data:** content and settings are stored in SQLite; uploaded media stays on your server.

For exact behavior, limitations, and examples, see the [full feature overview](docs/overview.md) and [administrator guide](docs/user-guide.md).

## Quick start

Requires **Python 3.11+** and a Unix-like environment (Linux or WSL on Windows). To run locally:

```bash
git clone https://github.com/tanerim/FriPeri.git
cd FriPeri
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
SESSION_COOKIE_SECURE=false python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** to complete first-run setup and create your administrator account. For HTTPS production deployments, keep `SESSION_COOKIE_SECURE=true`, complete setup before exposing the site publicly, and follow the [deployment guide](docs/deployment.md).

**Need another installation method?** The [installation guide](docs/installation.md) covers custom clone directory names, command-line setup, prerequisites, and first-run behavior.

## Documentation

Everything you need to set up, manage, and extend FriPeri. Browse the [complete documentation](docs/index.md) or jump directly to a guide below.

### Getting started

- **[Overview and features](docs/overview.md)** — What FriPeri does and how it works.
- **[Installation and setup](docs/installation.md)** — Requirements, first-run setup, and CLI installation.
- **[Administrator user guide](docs/user-guide.md)** — Publishing, pages, homepage design, and languages.

### Running your site

- **[Configuration and data storage](docs/configuration.md)** — Site settings, environment variables, and persistence.
- **[Production deployment](docs/deployment.md)** — HTTPS, systemd, and reverse proxy setup.
- **[Maintenance, backup and recovery](docs/maintenance.md)** — Updates, backups, and restoration.
- **[Troubleshooting](docs/troubleshooting.md)** — Solutions to common problems.

### Development and project resources

- **[Development and testing](docs/development.md)** — Source layout, styling, and validation.
- **[Technical reference](docs/index.md#developer-reference)** — Architecture, HTTP routes, database model, and browser tests.
- **[Contributing and support](docs/support.md)** — Bug reports and contribution guidelines.
- **[Security policy](SECURITY.md)** · **[Dependency security](docs/dependency-security.md)** · **[Third-party notices](THIRD_PARTY_NOTICES.md)**

The administrator interface also includes a read-only documentation viewer under **Configuration → Documentation**.

## Development and verification

Install local test dependencies and run the regression suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q tests/
```

Optional browser tests require a disposable running test instance; see [docs/testing.md](docs/testing.md). No GitHub Actions are used for this project.

For vulnerability reports, follow [SECURITY.md](SECURITY.md) instead of publishing sensitive details in a public issue. For general bug reports and contributions, see [docs/support.md](docs/support.md).

## License and attribution

FriPeri source code is released under the [MIT License](LICENSE).

Copyright © 2026 **Taner Sezer — NextNLP**.

For third-party licenses and attribution, see the [licenses directory](licenses/).
