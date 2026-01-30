FROM runpod/worker-comfyui:5.7.1-base

# 1. Install basic system support
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy files (Ensure these exist in your GitHub repo!)
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY workflow_api.json /comfyui/workflow_api.json
COPY handler.py /handler.py
COPY requirements.txt /requirements.txt

# 3. Install Python dependencies into the ComfyUI venv
RUN pip install --upgrade pip
RUN /opt/venv/bin/python -m pip install onnxruntime-gpu opencv-python-headless

ENV COMFYUI_PATH_CONFIG=/comfyui/extra_model_paths.yaml

# 4. Use JSON format for CMD for better stability
CMD ["sh", "-c", "mkdir -p /comfyui/output/mesh && ln -snf /runpod-volume/custom_nodes/* /comfyui/custom_nodes/ && python /comfyui/main.py --listen 127.0.0.1 --port 8188 & python -u /handler.py"]