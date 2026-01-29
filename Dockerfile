FROM runpod/worker-comfyui:5.7.1-base

# Copy repository files
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY workflow_api.json /comfyui/workflow_api.json
COPY handler.py /handler.py
COPY requirements.txt /requirements.txt

# Install dependencies into the system and the venv
RUN pip install --upgrade pip && pip install -r /requirements.txt
RUN /opt/venv/bin/python -m pip install -r /requirements.txt timm einops

ENV COMFYUI_PATH_CONFIG=/comfyui/extra_model_paths.yaml

# Create output subfolder and ensure custom_nodes link correctly
# We use 'cp -rs' or a specific link to avoid overwriting existing base nodes
CMD sh -c "mkdir -p /comfyui/output/mesh && ln -snf /runpod-volume/custom_nodes/* /comfyui/custom_nodes/ && python /comfyui/main.py --listen 127.0.0.1 --port 8188 & python -u /handler.py"