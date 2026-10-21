# Sistema de Rondas de Inspección — prototipo

Prototipo web de apoyo a la planificación de rondas de inspección. Todos los datos son
ficticios.

## Estado

| Parte | Estado |
|---|---|
| Motor de criticidad: probabilidad, consecuencia y matriz (HU-004) | Reglas implementadas y probadas; falta la pantalla y el guardado |
| Ingreso al sistema y roles (HU-001) | Implementado y probado |
| Despliegue con Docker Compose | Implementado |
| Respaldo de la base y de la evidencia | Implementado |
| Activos, rondas, ordenamiento, registro y cobertura | Pendiente |

## Puesta en marcha

Requiere Docker.

1. Copiar `.env.example` como `.env` y reemplazar las claves.
2. Levantar los servicios:

   ```bash
   docker compose up -d --build
   ```

3. Crear los usuarios (la contraseña se pide por teclado):

   ```bash
   docker compose exec app python -m scripts.crear_usuario --nombre "Nombre Apellido" --email correo@ejemplo.com --rol supervisor
   ```

   Los roles posibles son `supervisor` y `operador`.

4. Abrir <http://localhost:8000>.

Para detener los servicios sin perder los datos: `docker compose stop`.

## Seguridad de acceso

- **Identificación.** Correo electrónico (único) y contraseña.
- **Almacenamiento de la contraseña.** Se guarda solo el hash de bcrypt (costo 12, con sal
  aleatoria por usuario). La contraseña en claro no se almacena ni se registra.
- **Política de contraseñas.** Mínimo 8 caracteres, con al menos una mayúscula, una minúscula
  y un número. Se valida al dar de alta el usuario.
- **Sesión.** Cookie firmada con una clave secreta, no accesible desde JavaScript, con una
  duración de 8 horas. Si la cookie se modifica, la firma deja de coincidir y se descarta.
- **Mensaje de error.** Ante un ingreso fallido se informa "Correo o contraseña incorrectos",
  sin indicar cuál de los dos datos falló.
- **Roles.** `supervisor` (supervisor de campo: define criterios, evalúa criticidad, planifica
  y confirma rondas, consulta cobertura y trazabilidad) y `operador` (consulta activos y
  registra verificaciones, evidencia y hallazgos). Cada ruta declara qué roles la pueden usar;
  un rol no habilitado recibe un rechazo (código 403) y quien no inició sesión es enviado a
  la pantalla de ingreso.
- **Alta de usuarios.** La hace quien administra el servidor, desde la terminal. No hay
  registro público ni pantalla de gestión de usuarios.
- **Base de datos.** No publica ningún puerto: solo la aplicación puede conectarse. Las
  claves de la base y de la sesión están en el archivo `.env`, fuera del repositorio.

No implementado: bloqueo por intentos fallidos, vencimiento de contraseñas, recuperación de
contraseña y HTTPS.

## Respaldo

```bash
sh scripts/respaldo.sh
```

Genera en `respaldos/` dos archivos con fecha y hora:

- `base_AAAAMMDD_HHMM.dump`: copia de PostgreSQL hecha con `pg_dump`.
- `evidencia_AAAAMMDD_HHMM.tar.gz`: copia del volumen de evidencia.

El script se ejecuta a mano. Para programarlo, se agrega al `cron` del servidor; por ejemplo,
todos los días a las 02:00:

```
0 2 * * * cd /ruta/al/proyecto && sh scripts/respaldo.sh
```

La carpeta `respaldos/` queda en el mismo equipo: copiarla a otro soporte es un paso aparte.

Para restaurar (reemplaza los datos actuales):

```bash
sh scripts/restaurar.sh respaldos/base_AAAAMMDD_HHMM.dump respaldos/evidencia_AAAAMMDD_HHMM.tar.gz
```

## Pruebas

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Las pruebas usan una base SQLite en memoria; no necesitan Docker.

## Estructura

```
app/
  criticidad.py    reglas de criticidad (funciones puras)
  seguridad.py     contraseñas, autenticación y roles
  models.py        tablas de la base
  database.py      conexión a la base
  config.py        lectura de variables de entorno
  main.py          rutas web
  templates/       plantillas Jinja2
  static/          hojas de estilo
alembic/           migraciones del esquema de la base
scripts/           alta de usuarios, respaldo y restauración
tests/             pruebas con pytest
```
