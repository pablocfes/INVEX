#!/usr/bin/env bash
set -e

cd /app

# 0) Esperar a Postgres
echo "Esperando a Postgres en $DB_HOST:$DB_PORT..."
python - <<'PYCODE'
import os, time, psycopg2
host = os.environ.get("DB_HOST","postgres")
port = int(os.environ.get("DB_PORT","5432"))
user = os.environ.get("DB_USER","postgres")
password = os.environ.get("DB_PASSWORD","postgres")
dbname = os.environ.get("DB_NAME","app")
for _ in range(60):
    try:
        psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname).close()
        print("Postgres OK"); break
    except Exception as e:
        print("Postgres no listo:", e)
        time.sleep(2)
else:
    raise SystemExit("Postgres no respondió a tiempo")
PYCODE

# 1) Generar migraciones si hay cambios (opcional, sólo en dev)
# if [ "${AUTO_MAKEMIGRATIONS:-1}" = "1" ]; then
  
# fi
echo "== makemigrations =="
python manage.py makemigrations --noinput || true

python manage.py migrate --noinput || true

# 2) Migrar esquema PUBLIC (apps compartidas)
echo "== migrate_schemas --shared =="
python manage.py migrate_schemas --shared --noinput

echo "== create tenant via shell =="
python manage.py shell -c "
from os import environ as e
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db import connection
from core.models import Cliente, Dominio

# Asegurar PUBLIC
if connection.schema_name != getattr(settings, 'PUBLIC_SCHEMA_NAME', 'public'):
    connection.set_schema(getattr(settings, 'PUBLIC_SCHEMA_NAME', 'public'))

schema = e.get('TENANT_SCHEMA','demo')
name = e.get('TENANT_NAME','Demo Company')
domain = e.get('TENANT_DOMAIN','demo.localhost')
trial_days = int(e.get('TENANT_TRIAL_DAYS','30'))

cliente, created = Cliente.objects.get_or_create(
    schema_name=schema,
    defaults={'nombre_compania': name, 'trial_ends_at': timezone.now()+timedelta(days=trial_days)}
)
Dominio.objects.get_or_create(domain=domain, defaults={'tenant': cliente, 'is_primary': True})
print('Tenant listo:', schema, 'Dominio:', domain)
"

# 4) (Opcional) Forzar migraciones de TENANTS existentes (útil si auto_create_schema=False)
echo "== migrate_schemas --tenant =="
python manage.py migrate_schemas --tenant --noinput

# 5) Staticfiles (si aplica)
if [ "${COLLECTSTATIC:-1}" = "1" ]; then
  echo "== collectstatic =="
  python manage.py collectstatic --noinput
fi

# 6) Arrancar servidor (gunicorn/daphne/uvicorn)
echo "== start server =="
exec python manage.py runserver 0.0.0.0:8000
