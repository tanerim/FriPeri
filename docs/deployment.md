## Deployment

### Running as a Linux Service

The following example assumes FriPeri is installed at `/opt/friperi`, its virtual environment is at `/opt/friperi/.venv`, and a dedicated `friperi` service account already exists. Adjust the paths and account for your server. The account needs read access to the application and write access to the database, upload, and backup directories. Restoring bundled images or `.env` through the panel also requires permission to overwrite those files.

Create `/etc/systemd/system/friperi.service`:

```ini
[Unit]
Description=FriPeri personal publishing site
After=network.target

[Service]
User=friperi
Group=friperi
WorkingDirectory=/opt/friperi
EnvironmentFile=-/opt/friperi/.env
Environment=SESSION_COOKIE_SECURE=true
ExecStart=/opt/friperi/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now friperi
sudo systemctl status friperi
```

Inspect its logs with:

```bash
sudo journalctl -u friperi -f
```

### Serving a Public Website

Place a reverse proxy such as Nginx or Caddy in front of `127.0.0.1:8000` and configure HTTPS for your domain. Complete first-run setup before opening the installation to public traffic.

Use a domain such as `example.com` in deployment configuration and replace it with your own domain. Forward the original host and scheme from your trusted proxy. Keep `SESSION_COOKIE_SECURE=true` in production, including in `.env` if that file is used. The service example runs one Uvicorn process; configure additional workers only after validating your storage and deployment needs.

Ensure proxy upload limits accommodate your intended image and video uploads, including multipart request overhead. Serve only the intended public paths; database files, backups, and `.env` are private application data.

Do not use Uvicorn's development `--reload` option for the service. If exposing `/health`, note that its response includes the configured database and upload paths.


---

[Documentation index](index.md) · [Complete README](../README.md)
