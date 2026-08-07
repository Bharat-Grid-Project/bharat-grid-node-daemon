import uuid
import time
import threading
import subprocess
import requests
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

ORCHESTRATOR_URL = "http://127.0.0.1:8000"
NODE_IP = "127.0.0.1"
NODE_PORT = 9000

node_id = str(uuid.uuid4())

def register_node():
    payload = {
        "node_id": node_id,
        "available_cpu": 2, 
        "available_ram_gb": 4, 
        "port": NODE_PORT,
        "ip_address": NODE_IP
    }
    try:
        response = requests.post(f"{ORCHESTRATOR_URL}/api/nodes/register", json=payload)
        response.raise_for_status()
        print(f"Registered with orchestrator successfully. Node ID: {node_id}")
    except Exception as e:
        print(f"Failed to register node: {e}")

def heartbeat_loop():
    while True:
        try:
            requests.post(f"{ORCHESTRATOR_URL}/api/nodes/heartbeat", json={"node_id": node_id})
        except Exception as e:
            pass # Suppress heartbeat errors to avoid spamming console if orchestrator is down
        time.sleep(10)

app = FastAPI(title="Bharat-Grid Node Daemon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DeployCommand(BaseModel):
    docker_image: str

@app.post("/deploy")
def handle_deploy(command: DeployCommand):
    try:
        print(f"Received deployment command for image: {command.docker_image}")
        result = subprocess.run(
            ["docker", "run", "-d", "-p", "8080:80", command.docker_image],
            capture_output=True,
            text=True,
            check=True
        )
        container_id = result.stdout.strip()
        print(f"Successfully deployed container {container_id}")
        return {"status": "success", "container_id": container_id, "port": 8080}
    except subprocess.CalledProcessError as e:
        print(f"Deployment failed: {e.stderr}")
        return {"status": "error", "message": str(e.stderr)}

if __name__ == "__main__":
    print("Starting Bharat-Grid Node Client Daemon...")
    register_node()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=NODE_PORT)
