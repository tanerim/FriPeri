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

| Getting started & content | Operations & development |
| --- | --- |
| [Overview and features](docs/overview.md) | [Configuration and data storage](docs/configuration.md) |
| [Installation and setup](docs/installation.md) | [Production deployment](docs/deployment.md) |
| [Administrator user guide](docs/user-guide.md) | [Maintenance, backup and recovery](docs/maintenance.md) |
| [Troubleshooting](docs/troubleshooting.md) | [Development and testing](docs/development.md) |
| [Contributing and support](docs/support.md) | [Security policy](SECURITY.md) |
| [Documentation index](docs/index.md) | [Third-party licenses and notices](THIRD_PARTY_NOTICES.md) |

More technical references—including [application architecture](docs/architecture.md), [HTTP routes](docs/http-routes.md), [database structure](docs/data-model.md), [local test instructions](docs/testing.md), and [dependency security](docs/dependency-security.md)—are linked from the [documentation index](docs/index.md).

The application also has an authenticated, read-only documentation viewer under **Configuration → Documentation**.

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

The project incorporates adapted HyperUI patterns and compiled Tailwind CSS, each under its own MIT notice. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [licenses/](licenses/) for third-party attribution and additional asset-rights information.
