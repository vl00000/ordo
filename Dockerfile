# ORDO server konteyneri. Versiya sabitdir ki, hər build eyni mühiti versin.
FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ORDO_DB=/data/ordo.db

# Root olmayan istifadəçi: konteyner sındırılsa belə, sistemdə root hüququ olmasın
RUN groupadd --system --gid 10001 ordo \
 && useradd --system --uid 10001 --gid ordo --no-create-home --shell /usr/sbin/nologin ordo

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ordo/ ordo/
# Baza qovluğuna yalnız ordo istifadəçisi girə bilər
RUN mkdir /data && chown ordo:ordo /data && chmod 700 /data

USER ordo
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# Konteynerin içində 0.0.0.0; kənardan yalnız 127.0.0.1 açıqdır (bax: docker-compose.yml)
CMD ["uvicorn", "ordo.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
