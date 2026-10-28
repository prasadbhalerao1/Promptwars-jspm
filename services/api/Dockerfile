FROM python:3.12-slim

WORKDIR /app

# Install system dependencies needed for PyTorch, WeasyPrint, and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    tesseract-ocr \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Install the locked dependencies, but with CPU-only torch: the default PyPI wheel pulls
# several GB of CUDA libraries that a CPU container never uses.
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
    && grep -viE '^(torch|nvidia-|triton|cuda-)' /tmp/req.txt > /tmp/req-cpu.txt \
    && uv pip install --system --index-url https://download.pytorch.org/whl/cpu torch==2.13.0 \
    && uv pip install --system -r /tmp/req-cpu.txt

# Bake the embedding model into the image so a cold start doesn't download ~1.3GB.
ARG EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# Copy the rest of the application
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Cloud Run injects PORT; local compose uses the 8000 default above.
CMD ["sh", "-c", "uvicorn services.api.main:app --host 0.0.0.0 --port ${PORT}"]
