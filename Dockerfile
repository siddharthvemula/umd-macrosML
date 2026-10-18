# Packs the whole app into one image any host can run: the FastAPI server, CPU-only
# torch, the CLIP model, and the built React frontend (served by FastAPI at "/").
# The database and saved photos are NOT in the image: they live in /data, a folder
# mounted from outside, so they survive rebuilds and redeploys.
#
#   docker build -t macros .
#   docker run -p 8080:8080 -v "$PWD/docker-data:/data" macros
#
# Two stages: stage 1 builds the frontend with Node, stage 2 copies only the finished
# files (frontend/dist), so Node and node_modules never end up in the final image.

# ---- Stage 1: build the React app ----
FROM node:24-slim AS frontend
WORKDIR /frontend
# Copy the package files first and install, then the source. Docker caches each step,
# so editing a .jsx file reuses the cached `npm ci` instead of reinstalling everything.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the Python server ----
FROM python:3.12-slim

# PYTHONUNBUFFERED: print logs right away instead of buffering them (so `docker logs`
# is live). HF_HOME: where the CLIP download is stored inside the image.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/hf-cache

WORKDIR /app

# CPU-only torch from PyTorch's own index. The normal x86 torch from PyPI includes
# ~3 GB of NVIDIA GPU libraries our CPU-only server would never use. Installed before
# requirements.txt, so pip sees torch==2.14.1 is already there and doesn't fetch it again.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download CLIP now, while building, so the image already has it: the server starts
# fast and never depends on Hugging Face being reachable. The name must match
# ml/recognizer.py's MODEL_NAME.
RUN python -c "from transformers import CLIPModel, CLIPProcessor; \
name = 'openai/clip-vit-base-patch32'; \
CLIPModel.from_pretrained(name); CLIPProcessor.from_pretrained(name)"
# From here on, transformers only reads the local copy and never goes online.
ENV HF_HUB_OFFLINE=1

# App code last: it changes most often, so the slow steps above stay cached.
COPY config.py ./
COPY api/ api/
COPY db/ db/
COPY ml/ ml/
COPY scraper/ scraper/
COPY --from=frontend /frontend/dist frontend/dist

# Point config.py at the mounted folder. connect() and photo_store create the DB file
# and photo folder on first use, so an empty /data works too.
ENV MACROS_DB_PATH=/data/macros.db \
    MACROS_PHOTO_DIR=/data/photos
VOLUME /data

EXPOSE 8080

# Docker (and most hosts) mark the container unhealthy if this fails. Uses Python's
# urllib because the slim image has no curl. start-period gives uvicorn time to boot.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health', timeout=4)"

CMD ["uvicorn", "api.server:create_server", "--factory", "--host", "0.0.0.0", "--port", "8080"]
