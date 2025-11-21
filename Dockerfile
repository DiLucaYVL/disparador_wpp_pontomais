FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

WORKDIR /app

# Instala apenas as dependências necessárias do Python
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Garante que pastas usadas em runtime existam
RUN mkdir -p /app/uploads /app/log /app/task_status /app/secrets

EXPOSE 8000

# Usa Gunicorn com a configuração existente
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:app"]
