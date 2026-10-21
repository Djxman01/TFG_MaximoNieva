# Sistema de Rondas de Inspección — prototipo

Prototipo web de apoyo a la planificación de rondas de inspección en instalaciones
hidrocarburíferas. El sistema **calcula** la criticidad de cada activo con factores explícitos,
**propone** un orden de recorrido con una regla propia y el responsable **revisa, ajusta y
confirma**. Durante la ronda se registran verificaciones, evidencia y hallazgos, y al final se
calcula la cobertura ponderada por criticidad.

Trabajo Final de Grado, Ingeniería en Software. **Todos los datos son ficticios**: los activos,
las personas y las coordenadas no corresponden a ninguna operación real.

## Qué incluye

| Historia | Funcionalidad | Estado |
|---|---|---|
| HU-001 | Ingreso al sistema, contraseñas NIST, perfiles Líder de Operaciones y Operador | Implementada |
| HU-002, HU-003 | Activos y criterios de criticidad | Por datos semilla, sin pantallas de alta |
| HU-004 | Evaluación de criticidad con recálculo en vivo e historial | Implementada |
| HU-005, HU-006 | Creación de la ronda y selección de activos | Implementadas |
| HU-007 | Propuesta de orden con la regla propia, y mapa | Implementada |
| HU-008 | Revisión, ajuste con motivo obligatorio y confirmación | Implementada |
| HU-014 | Condiciones de salida: un "No apto" impide confirmar | Implementada |
| HU-009, HU-010 | Registro en campo con evidencia fotográfica y hallazgos | Implementadas |
| HU-011, HU-012, HU-013 | Estado de atención, cobertura operativa y ponderada, trazabilidad | Implementadas |

## Puesta en marcha

Requiere **Docker** (con Docker Compose) y conexión a internet la primera vez, para descargar
las imágenes. El fondo del mapa también se descarga de internet (OpenStreetMap).

1. Crear el archivo de configuración a partir del ejemplo:

   ```bash
   cp .env.example .env
   ```

   Para la demo alcanza con copiarlo. En un servidor real hay que reemplazar las dos claves.

2. Levantar los servicios (la primera vez tarda unos minutos):

   ```bash
   docker compose up -d --build
   ```

3. Cargar los datos de ejemplo (usuarios de prueba, criterios de criticidad y activos):

   ```bash
   docker compose exec app python -m scripts.datos_semilla
   ```

   Se puede repetir sin duplicar nada.

4. Abrir <http://localhost:8000> e ingresar con un usuario de prueba.

Para detener los servicios sin perder los datos: `docker compose stop`. Para volver a
empezar desde cero (borra la base y la evidencia): `docker compose down -v`.

### Usuarios de prueba

Solo para la demo.

| Perfil | Correo | Contraseña |
|---|---|---|
| Líder de Operaciones | `lider@rondas.demo` | `laura planifica las rondas` |
| Operador | `operador@rondas.demo` | `pablo recorre los pozos` |

### Crear otros usuarios

```bash
docker compose exec app python -m scripts.crear_usuario --nombre "Nombre Apellido" --email correo@ejemplo.com --rol lider
```

La contraseña se pide por teclado. Los roles posibles son `lider` (Líder de Operaciones) y
`operador`.

## Recorrido de la demo

Reproduce la Ronda #024 de las pantallas del documento. Con estos datos, los resultados son
los mismos que muestran las figuras.

**Como Líder de Operaciones**

1. **Activos → Evaluar** en "Pozo A-21" (sin evaluar). Marcar dos factores de probabilidad y
   el ambiental: el resultado pasa a **ALTA** mientras se marcan. Guardar.
2. **Rondas → Nueva ronda**: Vehículo terrestre, Base Norte, 240 min, 40 km/h, 30 min.
3. Elegir Pozo A-14, Pozo A-08, Pozo B-03, Batería 2 y Pozo C-07 y **Guardar selección**.
4. **Generar propuesta**: A-14, A-08, B-03, Batería 2 en **215 min**; C-07 queda **fuera por
   tiempo** aunque está a 5 km de la base, porque la criticidad prevalece sobre la distancia.
5. **Revisar y confirmar**: subir Batería 2 dos lugares (225 min, +10 min). Confirmar sin
   motivo: el sistema lo exige. Escribir "Camino de acceso al Pozo A-08 temporalmente
   restringido por obra" y confirmar.
6. Condiciones de salida: Clima **No apto** → el sistema no deja confirmar y dice por qué.
   Cambiarlo a Condicionado y **Confirmar y programar**.

**Como Operador** (salir e ingresar con el otro usuario)

7. **Rondas a ejecutar** → la ronda → **Registrar** en Pozo A-14: Con hallazgos, adjuntar una
   foto, cargar el hallazgo y marcar **Requiere atención inmediata**. Guardar.
8. En Batería 2: **No accesible**, con su motivo.

**Como Líder de Operaciones**

9. **Rondas → Ver**: cobertura operativa 20 % y ponderada 27 %, estado de cada activo, mapa
   con el recorrido confirmado, trazabilidad del orden (propuesto, confirmado y ejecutado) y la
   verificación con su foto y su hallazgo. **Cerrar la ronda**.

## Seguridad de acceso

- **Identificación.** Correo electrónico (único) y contraseña.
- **Almacenamiento de la contraseña.** Se guarda solo el hash de bcrypt (costo 12, con sal
  aleatoria por usuario). La contraseña en claro no se almacena ni se registra.
- **Política de contraseñas** (NIST SP 800-63B-4, sección 3.1.1.2). Entre 15 y 64
  caracteres, sin reglas de composición: se aceptan espacios, acentos y cualquier carácter,
  así que sirven las frases. Se rechazan las contraseñas de una lista de bloqueo
  (`app/datos/claves_bloqueadas.txt`) y las que superan los 72 bytes que admite bcrypt. La
  contraseña se normaliza a Unicode NFC antes de calcular el hash. No vence. Se valida al dar
  de alta el usuario.
- **Sesión.** Cookie firmada con una clave secreta, no accesible desde JavaScript, con una
  duración de 8 horas. Si la cookie se modifica, la firma deja de coincidir y se descarta.
- **Mensaje de error.** Ante un ingreso fallido se informa "Correo o contraseña incorrectos",
  sin indicar cuál de los dos datos falló.
- **Roles.** `lider` (Líder de Operaciones: evalúa criticidad, planifica y confirma rondas,
  consulta cobertura y trazabilidad) y `operador` (consulta activos y
  registra verificaciones, evidencia y hallazgos). Cada ruta declara qué roles la pueden usar;
  un rol no habilitado recibe un rechazo (código 403) y quien no inició sesión es enviado a
  la pantalla de ingreso.
- **Alta de usuarios.** La hace quien administra el servidor, desde la terminal. No hay
  registro público ni pantalla de gestión de usuarios.
- **Base de datos.** No publica ningún puerto: solo la aplicación puede conectarse. Las
  claves de la base y de la sesión están en el archivo `.env`, fuera del repositorio.

No implementado (se declara como política del proyecto): bloqueo por intentos fallidos,
cambio obligatorio en el primer ingreso, pantalla de administración de usuarios, recuperación
de contraseña y HTTPS.

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

Las pruebas usan una base SQLite en memoria y una carpeta temporal para la evidencia; no
necesitan Docker.

## Estructura

```
app/
  criticidad.py      reglas de criticidad: probabilidad, consecuencia y matriz
  ordenamiento.py    regla de ordenamiento de la ronda (HU-007)
  cobertura.py       cobertura operativa y ponderada (HU-012)
  coordenadas.py     conversión Gauss-Krüger (EPSG:5344) ↔ latitud y longitud con pyproj
  seguridad.py       contraseñas (NIST), autenticación y perfiles
  models.py          tablas de la base (SQLAlchemy)
  semilla.py         datos de ejemplo de la demo
  rutas/             pantallas: activos y criticidad, rondas, registro en campo
  templates/         plantillas Jinja2 (basadas en los prototipos de la tesis)
  static/            estilos, htmx, Leaflet y el script del mapa
alembic/             migraciones del esquema de la base
scripts/             datos semilla, alta de usuarios, respaldo y restauración
tests/               pruebas con pytest
```

Las tres reglas del núcleo (`criticidad.py`, `ordenamiento.py` y `cobertura.py`) son funciones
de Python sin base de datos ni web, y cada una tiene sus propias pruebas.

## Tecnologías

Python 3.14, FastAPI, SQLAlchemy y Alembic, PostgreSQL 17, Jinja2 con htmx 2.0.11 (sin
framework de JavaScript), Leaflet 1.9.4 con teselas de OpenStreetMap, pyproj, bcrypt, pytest,
Docker y Docker Compose.
