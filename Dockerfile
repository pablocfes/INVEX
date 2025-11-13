# ---------- Base común: runtime ----------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Solo librerías necesarias en runtime (WeasyPrint + Postgres + fuentes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    libharfbuzz0b \
    libfribidi0 \
    libfreetype6 \
    libfontconfig1 \
    libjpeg62-turbo \
    libpng16-16 \
    libxml2 \
    libxslt1.1 \
    libpq5 \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


# ---------- Builder: compila lo que haga falta ----------
FROM base AS builder

# Solo aquí usamos build-essential (no llega a la imagen final)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Instalamos en /install para luego copiar al final
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---------- Imagen final ----------
FROM base

# Copiar dependencias ya instaladas desde el builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copiar código del proyecto
COPY . .

EXPOSE 8000

# Para desarrollo está bien runserver.
ENTRYPOINT ["/app/entrypoint.sh"]
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]