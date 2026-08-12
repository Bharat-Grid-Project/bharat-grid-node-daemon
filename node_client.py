import uuid
import time
import threading
import subprocess
import requests
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import psutil
import argparse
import socket

ORCHESTRATOR_URL = "http://127.0.0.1:8000"
NODE_IP = "127.0.0.1"
NODE_PORT = 9000
API_TOKEN = "BHARAT_GRID_ALPHA_TOKEN"

node_id = str(uuid.uuid4())

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def register_node():
    payload = {
        "node_id": node_id,
        "available_cpu": psutil.cpu_count(logical=True), 
        "available_ram_gb": round(psutil.virtual_memory().total / (1024**3)), 
        "port": NODE_PORT,
        "ip_address": NODE_IP
    }
    headers = {"x-api-token": API_TOKEN}
    try:
        response = requests.post(f"{ORCHESTRATOR_URL}/api/nodes/register", json=payload, headers=headers)
        response.raise_for_status()
        print(f"Registered with orchestrator successfully. Node ID: {node_id}")
    except Exception as e:
        print(f"Failed to register node: {e}")

def heartbeat_loop():
    headers = {"x-api-token": API_TOKEN}
    while True:
        try:
            cpu_usage = psutil.cpu_percent(interval=None)
            payload = {"node_id": node_id, "cpu_usage_percent": cpu_usage}
            requests.post(f"{ORCHESTRATOR_URL}/api/nodes/heartbeat", json=payload, headers=headers)
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
    parser = argparse.ArgumentParser(description="Bharat-Grid Node Daemon")
    parser.add_argument("--orchestrator", type=str, default="http://127.0.0.1:8000", help="URL of the Central Orchestrator")
    parser.add_argument("--port", type=int, default=9000, help="Port to run the Node Client on")
    args = parser.parse_args()

    ORCHESTRATOR_URL = args.orchestrator
    NODE_PORT = args.port
    NODE_IP = get_local_ip()

    print(f"Starting Bharat-Grid Node Client Daemon on {NODE_IP}:{NODE_PORT}...")
    print(f"Connecting to Orchestrator at: {ORCHESTRATOR_URL}")
    
    register_node()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=NODE_PORT)
