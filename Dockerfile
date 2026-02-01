FROM runpod/worker-comfyui:5.7.1-base

# Force PyTorch to allow older model formats
ENV TORCH_FORCE_WEIGHTS_ONLY_LOAD=0
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 git wget && rm -rf /var/lib/apt/lists/*
RUN pip install requests

# REMOVED BRIA-RMBG NODES TO PREVENT CONFLICTS
RUN mkdir -p /comfyui/input
COPY workflow_api.json /workflow_api.json
COPY handler.py /handler.py

# Symlink checkpoints from the network volume and start both services
CMD ["sh", "-c", "\
  mkdir -p /comfyui/models/checkpoints && \
  ln -snf /runpod-volume/checkpoints/hunyuan3d-dit-v2_fp16.safetensors /comfyui/models/checkpoints/ && \
  python /comfyui/main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --extra-model-paths-config /comfyui/extra_model_paths.yaml & \
  python -u /handler.py \
"]