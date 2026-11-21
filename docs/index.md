# FriPeri documentation

This is the full documentation for **FriPeri**, a self-hosted personal publishing application built with FastAPI, Jinja2, and SQLite. The [repository README](../README.md) provides a short introduction and quick start; the guides below contain the complete instructions and reference material.

## Start here

| Guide | What it covers |
| --- | --- |
| [Overview and features](overview.md) | Purpose, features, technology stack, supported scope and limitations |
| [Installation and initial setup](installation.md) | Requirements, local setup, CLI initialization, first administrator account |
| [Administrator user guide](user-guide.md) | Posts, categories, visual editor, homepages, media, languages, contact inbox |
| [Users, roles, and category permissions](user-roles.md) | Content creator, editor, administrator, category grants and post ownership |
| [Troubleshooting](troubleshooting.md) | Login, database, uploads, backup, language, editor and deployment problems |

## Operations and maintenance

| Guide | What it covers |
| --- | --- |
| [Configuration and persistent data](configuration.md) | Environment variables, defaults, secrets, paths and data locations |
| [Production deployment](deployment.md) | systemd, reverse proxy, HTTPS and security hardening |
| [Maintenance, backup and recovery](maintenance.md) | Secure backup/restore, updating, rollback, factory reset |
| [Security policy](../SECURITY.md) | Private vulnerability reporting, supported versions, security measures |
| [Dependency security review](dependency-security.md) | Package version advisories and verification requirements |

## Developer reference

| Guide | What it covers |
| --- | --- |
| [Development](development.md) | Repository structure, CSS builds and contributor validation |
| [Local regression and browser testing](testing.md) | pytest, optional Playwright checks, manual verification |
| [Application architecture](architecture.md) | Modules, request lifecycle, security-sensitive operations |
| [HTTP route reference](http-routes.md) | Public, authentication and admin endpoints |
| [SQLite data model](data-model.md) | Tables, persistence and database lifecycle |
| [Contributing and support](support.md) | Issue reports, contribution practices and sensitive reports |

## Licenses and other references

- [Project MIT License](../LICENSE)
- [Third-party components and asset notices](../THIRD_PARTY_NOTICES.md)
- [Third-party license texts](../licenses/)
- [Pinned Python dependencies](../requirements.txt)
- [Language migration design](../translations/LANGUAGE_MIGRATION.md)

The authenticated administrator interface also offers a read-only Markdown documentation viewer under **Configuration → Documentation**.

**Release validation:** Run tests locally, not through GitHub Actions. Protect uninitialized instances and private files, including credentials, databases, messages and backups. Verify dependency advisories and installation behavior before deployment.
