import os, requests, json, time, runpod, shutil

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
                
                # Copy to export directory
                shutil.copy(source_path, f"/export/{mesh_name}")
                return {"status": "success", "mesh_file": mesh_name}
        
        return {"status": "failed", "error": "No mesh file found in outputs"}

runpod.serverless.start({"handler": handler})