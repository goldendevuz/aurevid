# SPDX-License-Identifier: AGPL-3.0-or-later
# Aurevid GPU worker: Wan 2.2 TI2V-5B on an NVIDIA GPU with >= 24 GB VRAM.
# Build: docker build -t aurevid-gpu-worker deploy/gpu-worker
FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/cache
RUN pip install "diffusers>=0.35" "transformers>=4.51" accelerate sentencepiece ftfy \
        imageio imageio-ffmpeg "huggingface_hub>=0.30" "httpx>=0.27" \
    && useradd --create-home --uid 1000 worker \
    && mkdir /cache && chown worker /cache
USER worker
WORKDIR /app
COPY worker.py .
VOLUME /cache
CMD ["python", "worker.py"]
