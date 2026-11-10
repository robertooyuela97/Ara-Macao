# Usa una imagen base de Python ligera
FROM python:3.9-slim-buster

# Evita que Python escriba archivos .pyc y bufferiza stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instala dependencias del sistema necesarias para psycopg2 y Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia el archivo de requisitos e instala las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia todo el código del proyecto al contenedor
COPY . .

# Recopila archivos estáticos para producción
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Expone el puerto de la aplicación (Render usa el puerto asignado, por defecto 8000)
EXPOSE 8000

# Ejecuta la aplicación con Gunicorn (servidor WSGI para producción)
CMD ["gunicorn", "memory_game_main.wsgi:application", "--bind", "0.0.0.0:8000"]
