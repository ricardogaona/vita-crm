# vita-crm

Proyecto Django con PostgreSQL, ambos en Docker. Postgres queda publicado en el puerto **5433** de la Mac.

## Requisitos

- Docker Desktop

## Arranque

```bash
docker compose up --build
```

- App: http://localhost:8000
- Admin: http://localhost:8000/admin/
- Postgres desde la Mac: `localhost:5433`

```text
host:     localhost
port:     5433
database: vita_crm
user:     vita
password: vita
```

Dentro de la red de Docker, Django se conecta a `db:5432`. El mapeo `5433:5432` es solo para clientes en la Mac (psql, TablePlus, DBeaver).

## Frontend

La interfaz usa Django Templates, Tabler UI y HTMX. La guía de uso está en [docs/frontend.md](docs/frontend.md).

## Comandos útiles

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

Las credenciales de desarrollo están en `.env`. `.env.example` es la plantilla.

## Railway

La imagen de producción usa Gunicorn en `0.0.0.0:$PORT`. Railway inyecta `PORT`; no va en `.env`. El `Dockerfile` corre `collectstatic` en el build y [entrypoint.sh](entrypoint.sh) aplica las migraciones al arrancar. Docker Compose sigue usando `runserver` en local.

No configures un start command en el servicio: en una imagen Docker ese comando reemplaza el `ENTRYPOINT`.

1. Subí el repo a GitHub y creá un proyecto en Railway con **Deploy from GitHub**. Railway construye el `Dockerfile` de la raíz.
2. En el mismo proyecto, agregá **PostgreSQL** y dejalo privado. No actives el TCP Proxy ni uses `DATABASE_PUBLIC_URL`.
3. En el servicio web, definí estas variables. `Postgres` es el nombre del servicio de base:

```text
POSTGRES_HOST=${{Postgres.PGHOST}}
POSTGRES_PORT=${{Postgres.PGPORT}}
POSTGRES_USER=${{Postgres.PGUSER}}
POSTGRES_PASSWORD=${{Postgres.PGPASSWORD}}
POSTGRES_DB=${{Postgres.PGDATABASE}}
DJANGO_SECRET_KEY=<clave generada>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}},healthcheck.railway.app
DJANGO_CSRF_TRUSTED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}}
```

Generá la clave con:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

4. En **Settings → Networking**, generá el dominio público. En **Deploy**, poné el healthcheck en `/health`. Si el primer deploy corre antes de que exista el dominio, volvé a desplegar: `RAILWAY_PUBLIC_DOMAIN` tiene que estar definido.
5. Revisá los logs: conexión a Postgres, migraciones y Gunicorn escuchando en `$PORT`.
6. Creá el usuario admin una sola vez:

```bash
railway run python manage.py createsuperuser
```

7. Comprobá `https://<dominio>/health` (200), el login de `/admin/`, una pantalla con CSS y HTMX, y un POST de formulario.
