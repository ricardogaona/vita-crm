#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."

python << 'PY'
import os
import sys
import time

import psycopg

host = os.environ["POSTGRES_HOST"]
port = os.environ["POSTGRES_PORT"]
user = os.environ["POSTGRES_USER"]
password = os.environ["POSTGRES_PASSWORD"]
dbname = os.environ["POSTGRES_DB"]

for _ in range(30):
    try:
        with psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
        ):
            pass
        print("PostgreSQL is ready.")
        break
    except psycopg.OperationalError as exc:
        print(f"PostgreSQL unavailable ({exc}); retrying...")
        time.sleep(1)
else:
    sys.exit("Could not connect to PostgreSQL.")
PY

python manage.py migrate --noinput

exec "$@"
