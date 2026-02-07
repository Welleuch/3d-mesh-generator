import os, requests, json, time, runpod, shutil, boto3, uuid, traceback
from botocore.config import Config

def get_r2_client():
    """Initialize R2 client from environment variables"""
    try:
        return boto3.client(
            's3',
            endpoint_url=os.environ.get('R2_ENDPOINT'),
            aws_access_key_id=os.environ.get('R2_ACCESS_KEY'),
            aws_secret_access_key=os.environ.get('R2_SECRET_KEY'),
            config=Config(signature_version='s3v4')
        )
    except Exception as e:
        print(f"Error creating R2 client: {str(e)}")
        return None

def upload_to_r2(file_path, bucket_name, key):
    """Upload file to Cloudflare R2"""
    s3_client = get_r2_client()
    if not s3_client:
        raise Exception("R2 client not available")
    
    print(f"Uploading {file_path} to R2 bucket {bucket_name} as {key}")
    s3_client.upload_file(file_path, bucket_name, key)
    print(f"Upload successful: {key}")
    return key

def handler(job):
    try:
        print(f"Starting job: {job}")
        image_url = job['input'].get('image_url')
        
        if not image_url:
            return {"status": "failed", "error": "No image_url provided"}
        
        with open("/workflow_api.json", 'r') as f:
            workflow = json.load(f)

        # 1. Download Image
        image_name = f"input_{int(time.time())}.png"
        print(f"Downloading image from: {image_url}")
        img_data = requests.get(image_url).content
        with open(f"/comfyui/input/{image_name}", "wb") as f:
            f.write(img_data)
        print(f"Image saved as: {image_name}")

        # 2. Inject Image Path into workflow - NODE 56
        workflow["56"]["inputs"]["image"] = image_name
        
        # 3. Wait for ComfyUI
        print("Connecting to local ComfyUI...")
        for i in range(30):
            try:
                response = requests.get("http://127.0.0.1:8188/history/1", timeout=2)
                if response.status_code == 200:
                    print(f"ComfyUI ready after {i*2} seconds")
                    break
            except requests.exceptions.ConnectionError:
                if i == 29:
                    return {"status": "failed", "error": "ComfyUI failed to start"}
                time.sleep(2)

        # 4. Submit Job
        print("Submitting job to ComfyUI...")
        response = requests.post("http://127.0.0.1:8188/prompt", json={"prompt": workflow})
        response_data = response.json()
        
        if 'prompt_id' not in response_data:
            return {"status": "failed", "error": f"Submission failed: {response_data}"}
        
        prompt_id = response_data['prompt_id']
        print(f"Workflow submitted with ID: {prompt_id}")

        # 5. Poll for Result - INCREASED TIMEOUT
        print(f"Polling for results...")
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > 600:  # 10 minute timeout
                return {"status": "failed", "error": f"Timed out after {elapsed:.1f}s waiting for mesh generation."}

            time.sleep(5)
            
            try:
                history = requests.get("http://127.0.0.1:8188/history").json()
            except Exception as e:
                print(f"Error fetching history: {str(e)}")
                continue

            if prompt_id not in history:
                print(f"Prompt {prompt_id} not in history yet...")
                continue

            outputs = history[prompt_id].get("outputs", {})
            print(f"Found outputs: {list(outputs.keys())}")
            
            # Check all nodes for 3D output
            for node_id, node_output in outputs.items():
                # CHANGE: Look for "3d" key as verified in your logs
                if "3d" in node_output and node_output["3d"]:
                    mesh_info = node_output["3d"][0]
                    mesh_name = mesh_info["filename"]
                    
                    # Construct full path for Linux RunPod environment
                    source_path = f"/comfyui/output/{mesh_name}"
                    
                    print(f"Found mesh: {source_path}")
                    
                    # Check if file exists
                    if not os.path.exists(source_path):
                        return {"status": "failed", "error": f"Mesh file not found at {source_path}"}
                    
                    # Get file size
                    file_size = os.path.getsize(source_path)
                    print(f"Mesh file size: {file_size} bytes")
                    
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
                        
                        print(f"Upload successful! URL: {public_url}")
                        
                        return {
                            "status": "success",
                            "mesh_url": public_url,
                            "local_filename": mesh_name,
                            "execution_time": f"{elapsed:.1f}s",
                            "file_size": file_size
                        }
                        
                    except Exception as upload_error:
                        print(f"R2 upload error: {str(upload_error)}")
                        # Return local path if upload fails
                        return {
                            "status": "partial_success",
                            "local_path": source_path,
                            "error": f"R2 upload failed: {str(upload_error)}"
                        }
            
            # If we get here, no mesh found yet
            print(f"No mesh found in outputs yet, checking again in 5s...")
            
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Handler error: {error_trace}")
        return {"status": "failed", "error": str(e), "traceback": error_trace}

runpod.serverless.start({"handler": handler})