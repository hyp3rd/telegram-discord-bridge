# The Bridge - Telegram - Discord
FROM docker.io/bitnami/python:3.11

LABEL org.opencontainers.image.authors="F." \
      org.opencontainers.image.description="Telegram - Discord Bridge" \
      org.opencontainers.image.source="https://github.com/hyp3rd/telegram-discord-bridge/" \
      org.opencontainers.image.title="The Bridge"

WORKDIR /app

COPY . /app

RUN apt update && apt upgrade -y \
    && apt install -y libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade -r /app/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "api.api:app", "--host", "0.0.0.0", "--port", "8000"]

# If running behind a proxy like Nginx or Traefik add --proxy-headers
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers"]


# RUN apk update && apk upgrade && \ 
#   addgroup -S cur \
#   && adduser -S -u 10000 -g cur cur

# USER cur

# EXPOSE 8080 8443
# VOLUME ["/pub"]

# HEALTHCHECK --interval=15m --timeout=60s --retries=10 \
#   CMD wget --spider --no-verbose http://localhost:8080/curios/health || exit 1

# CMD ["/curiosity"]
