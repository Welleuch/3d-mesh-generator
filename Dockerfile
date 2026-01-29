FROM runpod/worker-comfyui:5.7.1-base

# Copy repository files
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY workflow_api.json /comfyui/workflow_api.json
COPY handler.py /handler.py
COPY requirements.txt /requirements.txt

# Install 3D and Cloud dependencies
RUN pip install --upgrade pip && pip install -r /requirements.txt

ENV COMFYUI_PATH_CONFIG=/comfyui/extra_model_paths.yaml

# Create output subfolder for meshes and start services
CMD sh -c "mkdir -p /comfyui/output/mesh && ln -s /runpod-volume/custom_nodes/* /comfyui/custom_nodes/ && python /comfyui/main.py --listen 127.0.0.1 --port 8188 & python -u /handler.py"