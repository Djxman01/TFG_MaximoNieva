#!/bin/sh
# Respaldo de la base de datos y de los archivos de evidencia.
#
# Uso, desde la carpeta del proyecto y con los servicios en marcha:
#     sh scripts/respaldo.sh
#
# Genera dos archivos con fecha y hora en la carpeta respaldos/:
#     base_AAAAMMDD_HHMM.dump          copia de PostgreSQL (pg_dump)
#     evidencia_AAAAMMDD_HHMM.tar.gz   copia del volumen de evidencia

set -eu

cd "$(dirname "$0")/.."
mkdir -p respaldos
MARCA=$(date +%Y%m%d_%H%M)

# pg_dump corre dentro del contenedor de la base. El formato "custom" (-Fc)
# está comprimido y se restaura con pg_restore.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
    > "respaldos/base_$MARCA.dump"

# Los archivos de evidencia se empaquetan desde el contenedor de la aplicación.
docker compose exec -T app tar -czf - -C /datos/evidencia . \
    > "respaldos/evidencia_$MARCA.tar.gz"

echo "Respaldo generado:"
ls -lh "respaldos/base_$MARCA.dump" "respaldos/evidencia_$MARCA.tar.gz"
