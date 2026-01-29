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
OUTPUT_DIR = "/comfyui/output/mesh"

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
    s3.upload_file(file_path, R2_CONF['bucket'], file_name, ExtraArgs={'ContentType': 'model/gltf-binary'})
    return f"{R2_CONF['public_url']}/{file_name}"

def wait_for_server():
    """Wait for ComfyUI to be ready before accepting jobs."""
    print("⏳ Checking if ComfyUI is up...")
    while True:
        try:
            # We check object_info to ensure nodes are loaded
            response = requests.get(f"{COMFY_URL}/object_info")
            if response.status_code == 200:
                print("✅ ComfyUI is ready!")
                break
        except:
            pass
        time.sleep(5)

def handler(job):
    job_input = job['input']
    image_url = job_input.get("image_url")
    
    if not image_url:
        return {"error": "No image_url provided"}

    # 1. Download the image
    local_input_image = os.path.join(INPUT_DIR, "input_for_3d.png")
    img_data = requests.get(image_url).content
    with open(local_input_image, 'wb') as f:
        f.write(img_data)

    # 2. Prepare Workflow
    with open(WORKFLOW_PATH, 'r') as f:
        workflow = json.load(f)

    workflow["1"]["inputs"]["image"] = "input_for_3d.png"
    file_prefix = f"mesh_{int(time.time())}"
    workflow["12"]["inputs"]["filename_prefix"] = f"mesh/{file_prefix}"

    try:
        # 3. Trigger ComfyUI
        response = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow})
        res_json = response.json()
        
        # ADD THIS CHECK: If ComfyUI rejects the prompt, stop immediately
        if "error" in res_json:
            return {"status": "error", "message": "ComfyUI rejected the workflow", "details": res_json["error"]}
        if response.status_code != 200:
            return {"error": f"ComfyUI Error: {response.text}"}
            
        prompt_id = res_json.get("prompt_id")

        # 4. Wait for the .glb file to appear in output
        found_mesh = None
        # Increased timeout to 10 minutes (120 * 5s)
        for _ in range(120): 
            if os.path.exists(OUTPUT_DIR):
                files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(file_prefix) and f.endswith(".glb")]
                if files:
                    found_mesh = os.path.join(OUTPUT_DIR, files[0])
                    break
            time.sleep(5)

        if not found_mesh:
            return {"error": "3D Generation timed out or file not found."}

        # 5. Upload to R2
        r2_url = upload_to_r2(found_mesh, f"{file_prefix}.glb")
        
        return {"status": "success", "mesh_url": r2_url}

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    wait_for_server()
    runpod.serverless.start({"handler": handler})