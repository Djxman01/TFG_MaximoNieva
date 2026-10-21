FROM python:3.14-slim

WORKDIR /codigo

# Primero las dependencias: Docker las reutiliza mientras no cambie el archivo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# La aplicación corre con un usuario sin privilegios, no como root.
RUN useradd --create-home aplicacion \
    && mkdir -p /datos/evidencia \
    && chown -R aplicacion /datos/evidencia
USER aplicacion

EXPOSE 8000

# Al iniciar se aplican las migraciones pendientes y después arranca el servidor.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
