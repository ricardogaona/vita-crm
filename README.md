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

Con `DJANGO_DEBUG=True`, la pantalla de referencia queda en http://localhost:8000/ui/.

## Comandos útiles

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

Las credenciales de desarrollo están en `.env`. `.env.example` es la plantilla.
