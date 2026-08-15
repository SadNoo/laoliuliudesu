FROM python:3.11.12-slim-bookworm@sha256:dbf1de478a55d6763afaa39c2f3d7b54b25230614980276de5cacdde79529d0c

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system --gid 10001 laoliuliu \
    && useradd --system --uid 10001 --gid laoliuliu --home /app laoliuliu

WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY pyproject.toml README.md ./
COPY laoliuliu ./laoliuliu
COPY migrations ./migrations
COPY alembic.ini ./

USER laoliuliu
EXPOSE 8000
CMD ["python", "-m", "laoliuliu.main"]
