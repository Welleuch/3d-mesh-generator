FROM runpod/worker-comfyui:5.7.1-base

# Force PyTorch to allow older model formats
ENV TORCH_FORCE_WEIGHTS_ONLY_LOAD=0
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 git wget && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install additional Python packages for background removal
RUN pip install --no-cache-dir rembg[gpu] onnxruntime-gpu

# Setup directories
RUN mkdir -p /comfyui/input /export

# Install custom nodes
RUN cd /comfyui/custom_nodes && \
    # Hunyuan3D nodes
    git clone https://github.com/Tencent/Hunyuan3D-ComfyUI-Nodes.git || echo "Hunyuan3D nodes exist" && \
    # Background removal nodes
    git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git || echo "Impact Pack exists" && \
    cd ComfyUI-Impact-Pack && git submodule update --init --recursive && cd .. && \
    git clone https://github.com/cubiq/ComfyUI_essentials.git || echo "Essentials exists"

# Copy workflow and handler
COPY workflow_api.json /workflow_api.json
COPY handler.py /handler.py
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Create symlink structure
RUN mkdir -p /comfyui/models/checkpoints

# Start services
CMD ["sh", "-c", "\
  # Wait for volume mount
  echo 'Waiting for volume mount...'; \
  sleep 5; \
  \
  # Create checkpoint directory
  mkdir -p /runpod-volume/checkpoints/; \
  \
  # Check if model exists
  if [ -f /runpod-volume/checkpoints/hunyuan3d-dit-v2_fp16.safetensors ]; then \
    echo 'Found Hunyuan3D model, creating symlink...'; \
    ln -sf /runpod-volume/checkpoints/hunyuan3d-dit-v2_fp16.safetensors /comfyui/models/checkpoints/hunyuan3d-dit-v2_fp16.safetensors; \
  else \
    echo 'ERROR: Model not found at /runpod-volume/checkpoints/hunyuan3d-dit-v2_fp16.safetensors'; \
    exit 1; \
  fi; \
  \
  # Start ComfyUI
  echo 'Starting ComfyUI...'; \
  python /comfyui/main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --extra-model-paths-config /comfyui/extra_model_paths.yaml & \
  \
  # Wait for ComfyUI to start
  echo 'Waiting for ComfyUI to start...'; \
  sleep 10; \
  \
  # Start handler
  echo 'Starting handler...'; \
  python -u /handler.py \
"]