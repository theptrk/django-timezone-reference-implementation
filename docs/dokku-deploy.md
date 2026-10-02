# Dokku deployment

The public teaching demo runs at https://timezone.delmarscience.com on the same
Dokku host as TodoBud. Its app and database are separate:

- Host: `dokku@delmarscience.com`
- App: `timezone`
- PostgreSQL service: `timezone-db`
- Git remote: `dokku@delmarscience.com:timezone`
- Python buildpack: `https://github.com/heroku/heroku-buildpack-python.git`
- Formation: one Gunicorn web process. No workers or Redis required.

Production is deployed from the exact clean GitHub `origin/main` commit:

```bash
git remote add dokku dokku@delmarscience.com:timezone
./scripts/deploy-production.sh
```

The buildpack installs locked dependencies and runs collectstatic. WhiteNoise
serves static assets. The release process applies migrations and seeds the
nonprivileged public demo account; web startup follows successful health checks.
The database lives in the Dokku PostgreSQL service, not in the application image.

Required config variables: `DJANGO_SETTINGS_MODULE=config.settings`,
`DJANGO_DEBUG=False`, a unique `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS=timezone.delmarscience.com,localhost,127.0.0.1`, and
`DJANGO_CSRF_TRUSTED_ORIGINS=https://timezone.delmarscience.com`.
`DATABASE_URL` is supplied by `postgres:link`. Enable TLS with the Let's Encrypt
plugin, then set `DJANGO_SECURE_SSL_REDIRECT=True`. Keep HTTP redirect off only
while bootstrapping the first certificate. Dokku terminates TLS and supplies
`X-Forwarded-Proto`; do not expose the Gunicorn port publicly.

The root page is a read-only inspector. The `/profile/` teaching account uses
`demouser` / `demopassword`. It is shared and public: use sample events only.
The demo is not an account-registration or private-data service.

Verification:

```bash
curl --fail https://timezone.delmarscience.com/health/
ssh dokku@delmarscience.com ps:report timezone
ssh dokku@delmarscience.com logs timezone --num 50
```

Before future migrations, export a backup using `postgres:export timezone-db`.
Retain the deployed GitHub SHA and review migration compatibility before a rollback.
