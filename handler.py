import os, requests, json, time, runpod, shutil, boto3, uuid
from botocore.config import Config

def get_r2_client():
    """Initialize R2 client from environment variables"""
    return boto3.client(
        's3',
        endpoint_url=os.environ.get('R2_ENDPOINT'),
        aws_access_key_id=os.environ.get('R2_ACCESS_KEY'),
        aws_secret_access_key=os.environ.get('R2_SECRET_KEY'),
        config=Config(signature_version='s3v4')
    )

def upload_to_r2(file_path, bucket_name, key):
    """Upload file to Cloudflare R2"""
    s3_client = get_r2_client()
    s3_client.upload_file(file_path, bucket_name, key)
    return key

def handler(job):
    image_url = job['input'].get('image_url')
    
    with open("/workflow_api.json", 'r') as f:
        workflow = json.load(f)

    # 1. Download Image
    image_name = f"input_{int(time.time())}.png"
    img_data = requests.get(image_url).content
    with open(f"/comfyui/input/{image_name}", "wb") as f:
        f.write(img_data)

    # 2. Inject Image Path
    workflow["1"]["inputs"]["image"] = image_name

    # 3. Wait for ComfyUI
    print("Connecting to local ComfyUI...")
    for i in range(60):
        try:
            requests.get("http://127.0.0.1:8188/history/1", timeout=2)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(2)

    # 4. Submit Job
    print("Submitting job...")
    response = requests.post("http://127.0.0.1:8188/prompt", json={"prompt": workflow}).json()
    
    if 'prompt_id' not in response:
        return {"status": "failed", "error": f"Submission failed: {response}"}
    
    prompt_id = response['prompt_id']

    # 5. Poll for Result
    print(f"Workflow running (ID: {prompt_id})...")
    start_time = time.time()
    while True:
        if time.time() - start_time > 300:
            return {"status": "failed", "error": "Timed out waiting for mesh generation."}

        time.sleep(3)
        history = requests.get("http://127.0.0.1:8188/history").json()

        if prompt_id not in history:
            continue

        outputs = history[prompt_id].get("outputs", {})
        
        # Check for 3D mesh output
        for node_id, node_output in outputs.items():
            if "3d" in node_output and node_output["3d"]:
                mesh_info = node_output["3d"][0]
                mesh_name = mesh_info["filename"]
                subfolder = mesh_info.get("subfolder", "")
                
                # Construct full path
                if subfolder:
                    source_path = f"/comfyui/output/{subfolder}/{mesh_name}"
                else:
                    source_path = f"/comfyui/output/{mesh_name}"
                
                print(f"Generated mesh: {source_path}")
                
                # 6. Upload to R2
                try:
                    # Get R2 config from environment
                    bucket_name = os.environ.get('R2_BUCKET', 'ai-gift-assets')
                    public_url_base = os.environ.get('R2_PUBLIC_URL', 'https://pub-518bf750a6194bb7b92bf803e180ed88.r2.dev')
                    
                    # Generate unique key
                    unique_key = f"models/{uuid.uuid4()}_{mesh_name}"
                    
                    # Upload to R2
                    upload_to_r2(source_path, bucket_name, unique_key)
                    
                    # Generate public URL
                    public_url = f"{public_url_base}/{unique_key}"
                    
                    return {
                        "status": "success",
                        "mesh_url": public_url,
                        "local_filename": mesh_name
                    }
                    
                except Exception as e:
                    return {"status": "failed", "error": f"R2 upload failed: {str(e)}"}
        
        return {"status": "failed", "error": "No mesh file found in outputs"}

runpod.serverless.start({"handler": handler})