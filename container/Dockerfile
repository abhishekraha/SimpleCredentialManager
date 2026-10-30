# Hardened Multi-Arch Container for Simple Credential Manager Server Mode
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SCM_HOST=0.0.0.0 \
    SCM_PORT=8080 \
    SCM_PREFIX=""

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt uvicorn

COPY dev/ dev/
COPY SimpleCredentialManagerCli.py .
COPY SimpleCredentialManagerUi.py .

# Create 'scm' executable script in /usr/local/bin
RUN printf '#!/bin/sh\nexec python /app/SimpleCredentialManagerCli.py "$@"\n' > /usr/local/bin/scm && \
    chmod +x /usr/local/bin/scm

# Create non-root user and persistent volume mount directories
RUN groupadd -g 10001 scm && \
    useradd -u 10001 -g scm -m -s /bin/bash scm && \
    echo 'alias scm="/usr/local/bin/scm"' >> /home/scm/.bashrc && \
    mkdir -p /home/scm/.simpleCredentialManager /home/scm/.config/.simpleCredentialManager && \
    chown -R scm:scm /app /home/scm

USER scm:scm

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

ENTRYPOINT ["scm", "server", "start"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
