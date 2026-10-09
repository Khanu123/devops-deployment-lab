FROM python:3.14-slim-bookworm
ARG APP_VERSION=local
ENV APP_VERSION=${APP_VERSION} APP_HOST=0.0.0.0 APP_PORT=8080 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# No third-party Python runtime dependencies are used. Remove installer tooling
# and bundled dependencies so they are not shipped in the runtime image.
RUN python -m pip uninstall --yes pip setuptools wheel \
    && rm -rf /usr/local/lib/python3.13/ensurepip \
    && groupadd --gid 10001 lab && useradd --uid 10001 --gid 10001 --no-create-home lab
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 sample_data ./sample_data
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=2)"]
CMD ["python", "-m", "app.server"]
