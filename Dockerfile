FROM runpod/worker-comfyui:5.7.1-base

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 git && rm -rf /var/lib/apt/lists/*

COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY workflow_api.json /comfyui/workflow_api.json
COPY handler.py /handler.py

# Added wheel/setuptools to prevent the build-failure shown in your logs
RUN /opt/venv/bin/python -m pip install --upgrade pip wheel setuptools
RUN /opt/venv/bin/python -m pip install --no-cache-dir onnxruntime-gpu opencv-python-headless gguf timm hydra-core iopath segment-anything-fast decord pycocotools

ENV COMFYUI_PATH_CONFIG=/comfyui/extra_model_paths.yaml

# Only links exactly what you manually uploaded
CMD ["sh", "-c", "mkdir -p /comfyui/output/mesh && ln -snf /runpod-volume/custom_nodes/comfyui-rmbg /comfyui/custom_nodes/ && ln -snf /runpod-volume/custom_nodes/ComfyUI-GGUF /comfyui/custom_nodes/ && python /comfyui/main.py --listen 127.0.0.1 --port 8188 & python -u /handler.py"]