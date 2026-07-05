FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download the local ONNX embedding model so first run works offline and fast.
# Best-effort: if the build host is offline, the model downloads on first use instead.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])" || true
COPY app.py .
COPY static ./static
ENV HEARTH_DATA_DIR=/data
EXPOSE 8010
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
