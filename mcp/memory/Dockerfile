FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download the local ONNX embedding model so first run works offline and fast.
# Best-effort: if the build host is offline, the model downloads on first use instead.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])" || true
ARG HEARTH_MEMORY_VERSION=0.7.0-phase1
ARG HEARTH_MEMORY_BUILD_COMMIT=unknown
LABEL org.opencontainers.image.version=$HEARTH_MEMORY_VERSION \
      org.opencontainers.image.revision=$HEARTH_MEMORY_BUILD_COMMIT
COPY app.py work.py dashboard.py coordination.py inbox_ack.py .
COPY app.py work.py dashboard.py coordination.py reviewers.py .
COPY commons_files.py .
COPY glossary.py .
COPY journal.py .
COPY dashboard-watchers.json .
COPY hearth2 ./hearth2
COPY static ./static
ENV HEARTH_DATA_DIR=/data
ENV HEARTH_MEMORY_VERSION=$HEARTH_MEMORY_VERSION
ENV HEARTH_MEMORY_BUILD_COMMIT=$HEARTH_MEMORY_BUILD_COMMIT
EXPOSE 8010
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
