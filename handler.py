import runpod
import requests
import json
import os
import time
import boto3
from botocore.config import Config

# --- CONFIGURATION ---
COMFY_URL = "http://127.0.0.1:8188"
WORKFLOW_PATH = "/comfyui/workflow_api.json"
INPUT_DIR = "/comfyui/input"
OUTPUT_DIR = "/comfyui/output/mesh" # Note the subfolder from your workflow node 12

R2_CONF = {
    'endpoint': "https://d165cffd95013bf358b1f0cac3753628.r2.cloudflarestorage.com",
    'access_key': "a2e07f81a137d0181c024a157367e15f",
    'secret_key': "dca4b1e433bf208a509aea222778e45f666cc2c862f851842c3268c3343bb259",
    'bucket': "ai-gift-assets",
    'public_url': "https://pub-518bf750a6194bb7b92bf803e180ed88.r2.dev"
}

def upload_to_r2(file_path, file_name):
    s3 = boto3.client('s3',
        endpoint_url=R2_CONF['endpoint'],
        aws_access_key_id=R2_CONF['access_key'],
        aws_secret_access_key=R2_CONF['secret_key'],
        config=Config(signature_version='s3v4')
    )
    # ExtraArgs for 3D models
    s3.upload_file(file_path, R2_CONF['bucket'], file_name, ExtraArgs={'ContentType': 'model/gltf-binary'})
    return f"{R2_CONF['public_url']}/{file_name}"

def handler(job):
    job_input = job['input']
    image_url = job_input.get("image_url") # The link from your Image Gen result
    
    if not image_url:
        return {"error": "No image_url provided"}

    # 1. Download the image to ComfyUI input folder
    local_input_image = os.path.join(INPUT_DIR, "input_for_3d.png")
    img_data = requests.get(image_url).content
    with open(local_input_image, 'wb') as handler:
        handler.write(img_data)

    # 2. Prepare Workflow
    with open(WORKFLOW_PATH, 'r') as f:
        workflow = json.load(f)

    # Map inputs correctly based on your JSON nodes
    workflow["1"]["inputs"]["image"] = "input_for_3d.png"
    file_prefix = f"mesh_{int(time.time())}"
    workflow["12"]["inputs"]["filename_prefix"] = f"mesh/{file_prefix}"

    try:
        # 3. Trigger ComfyUI
        response = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow})
        
        # 4. Poll for the .glb file
        found_mesh = None
        for _ in range(300): # 3D generation is slow, 5 min timeout
            if os.path.exists(OUTPUT_DIR):
                files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(file_prefix) and f.endswith(".glb")]
                if files:
                    found_mesh = os.path.join(OUTPUT_DIR, files[0])
                    break
            time.sleep(5)

        if not found_mesh:
            return {"error": "3D Generation timed out."}

        # 5. Upload to R2
        r2_url = upload_to_r2(found_mesh, f"{file_prefix}.glb")
        
        return {"status": "success", "mesh_url": r2_url}

    except Exception as e:
        return {"error": str(e)}

runpod.serverless.start({"handler": handler})