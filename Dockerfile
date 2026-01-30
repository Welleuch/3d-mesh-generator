FROM runpod/worker-comfyui:5.7.1-base

# 1. Install System-level dependencies (CRITICAL for OpenCV/BiRefNet)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy repository files
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY workflow_api.json /comfyui/workflow_api.json
COPY handler.py /handler.py
COPY requirements.txt /requirements.txt

# 3. Install Python dependencies
RUN pip install --upgrade pip && pip install -r /requirements.txt
RUN /opt/venv/bin/python -m pip install timm einops opencv-python-headless

ENV COMFYUI_PATH_CONFIG=/comfyui/extra_model_paths.yaml

# 4. Link nodes and start
CMD sh -c "mkdir -p /comfyui/output/mesh && ln -snf /runpod-volume/custom_nodes/* /comfyui/custom_nodes/ && python /comfyui/main.py --listen 127.0.0.1 --port 8188 & python -u /handler.py"