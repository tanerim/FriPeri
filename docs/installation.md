## Installation

### Requirements

- Python 3.11 or newer as a starting baseline, including the `venv` module and pip. The pinned packages in `requirements.txt` must also support your chosen interpreter and platform; this checkout does not declare a tested Python-version matrix.
- A Unix-like environment with Python's `fcntl` module, which the first-run initializer uses for file locking. On Windows, use a Linux environment such as WSL rather than native Windows Python.
- Write access to the database directory and upload directory.
- A modern browser for the admin interface.
- Git if cloning the repository; alternatively, download and extract the source archive.

Contact-form messages are stored in the admin **Messages** inbox. No email service or SMTP configuration is required. See [Contact Details and Messages](../README.md#contact-details-and-messages).

### 1. Get the source code

```bash
git clone https://github.com/tanerim/friperi.git
cd friperi
```

If you downloaded an archive, extract it and open a terminal in the directory containing `main.py` and `requirements.txt`.

For a specific website design you can colen repository with site name
```bash
git clone https://github.com/tanerim/friperi.git MyWebSite
cd MyWebSite
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

The commands below assume this environment is active and your current directory is the project root.

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Start the application

For local HTTP development, disable the session cookie's HTTPS-only flag for this process:

```bash
SESSION_COOKIE_SECURE=false python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser. A new installation opens the first-run setup screen.

Use the default `SESSION_COOKIE_SECURE=true` when serving the site over HTTPS. Complete setup locally or through restricted access before exposing a fresh installation publicly.

### 5. Complete first-run setup

Enter your site name and description, homepage welcome text, and administrator credentials. You can also configure an optional secondary language, social links, a contact email address, and initial hero image settings.

The administrator password must contain at least eight characters and match its confirmation. Setup stores a salted password hash in SQLite; it does not write a plaintext password to an environment file.

After completing setup, sign in at **http://127.0.0.1:8000/login**. Your administration panel is available at **http://127.0.0.1:8000/admin**. The login card displays the FriPeri logo and a project link to [FriPeri on NextNLP](https://nextnlp.com/pages/friperi), which opens in a new tab.

By default, the database is created at `db/site.db`. No manual SQL import, separate database-generation step, or restart is needed. An existing initialized database is migrated at startup instead of being reinstalled.

### Optional command-line initialization

For scripted or terminal-based installation, use the same initializer through the CLI:

```bash
python scripts/generate_db.py
```

To inspect non-interactive options:

```bash
python scripts/generate_db.py --help
```

The initializer refuses to overwrite an initialized database. If you specify `--db-path`, configure the application with the same `SITE_DB_PATH` before starting it.


---

[Documentation index](index.md) · [Complete README](../README.md)
