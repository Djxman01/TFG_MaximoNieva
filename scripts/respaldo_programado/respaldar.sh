#!/bin/sh
# Respaldo automático (lo ejecuta el servicio "respaldo" de docker-compose.yml).
#
# Corre dentro de su propio contenedor, todos los días a las 02:00 (hora de
# Argentina). Genera en /respaldos, que es la carpeta respaldos/ del proyecto:
#     base_AAAAMMDD_HHMM.dump          copia de PostgreSQL (pg_dump)
#     evidencia_AAAAMMDD_HHMM.tar.gz   copia del volumen de evidencia
# y borra los respaldos con más de 7 días. Los archivos tienen el mismo formato
# que los de scripts/respaldo.sh, así que se restauran con scripts/restaurar.sh.

set -eu

MARCA=$(date +%Y%m%d_%H%M)
DESTINO=/respaldos
DIAS_DE_RETENCION=7

# El archivo se escribe con un nombre temporal y se renombra al terminar: así
# nunca queda a la vista un respaldo a medio hacer.
pg_dump -h db -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$DESTINO/.base_$MARCA.dump"
mv "$DESTINO/.base_$MARCA.dump" "$DESTINO/base_$MARCA.dump"

tar -czf "$DESTINO/.evidencia_$MARCA.tar.gz" -C /datos/evidencia .
mv "$DESTINO/.evidencia_$MARCA.tar.gz" "$DESTINO/evidencia_$MARCA.tar.gz"

# Retención: se borran los respaldos de más de 7 días.
find "$DESTINO" -maxdepth 1 \( -name 'base_*.dump' -o -name 'evidencia_*.tar.gz' \) \
    -mtime +$((DIAS_DE_RETENCION - 1)) -delete

echo "$(date '+%d/%m/%Y %H:%M') respaldo generado: base_$MARCA.dump y evidencia_$MARCA.tar.gz"
