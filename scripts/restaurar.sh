#!/bin/sh
# Restauración de un respaldo generado con scripts/respaldo.sh.
#
# Uso, con los servicios en marcha:
#     sh scripts/restaurar.sh respaldos/base_AAAAMMDD_HHMM.dump respaldos/evidencia_AAAAMMDD_HHMM.tar.gz
#
# ATENCIÓN: reemplaza el contenido actual de la base y de la evidencia.

set -eu

if [ $# -ne 2 ]; then
    echo "Uso: sh scripts/restaurar.sh <archivo .dump> <archivo .tar.gz>"
    exit 1
fi

cd "$(dirname "$0")/.."

# --clean --if-exists borra las tablas actuales antes de recrearlas.
docker compose exec -T db sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
    < "$1"

docker compose exec -T app sh -c \
    'find /datos/evidencia -mindepth 1 -delete && tar -xzf - -C /datos/evidencia' \
    < "$2"

echo "Restauración completa."
