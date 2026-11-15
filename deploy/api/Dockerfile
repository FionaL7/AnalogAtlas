# AnalogAtlas API on Cloud Run (#21). Built by deploy/api/cloudbuild.yaml from
# the repo root:  docker build -f deploy/api/Dockerfile .
FROM python:3.12-slim

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface
WORKDIR /app

# torch and torchvision together from the CPU index, or open_clip pulls a
# mismatched torchvision from PyPI ("operator torchvision::nms does not exist").
COPY deploy/api/requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# Bake the CLIP weights in, so no request ever downloads them.
USER user
RUN python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')"
ENV HF_HUB_OFFLINE=1

# Data from the public GitHub Release `data` (see scripts/data.py).
# .build-stamp changes on every build, so data is re-fetched each time.
USER root
COPY .build-stamp /app/.build-stamp
COPY deploy/api/fetch_data.py /tmp/fetch_data.py
ARG REPO=FionaL7/AnalogAtlas
RUN python /tmp/fetch_data.py "$REPO" && chown -R user:user /app

COPY --chown=user:user analogatlas ./analogatlas
COPY --chown=user:user api ./api

USER user
# Cloud Run sets $PORT (8080). --proxy-headers: HTTPS ends at Google's front
# end; without it, tile_url comes back as http:// and browsers block it.
CMD exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers --forwarded-allow-ips "*"
