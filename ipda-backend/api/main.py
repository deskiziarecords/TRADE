import asyncio
import json
import time
from datetime import datetime
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import our heavy lifters
import sys
sys.path.append(str(Path(__file__).parent.parent))
from core.engine import IPDAEngine

# Import Rust Core (Assuming built with maturin develop)
try:
    import ipda_core
    RUST_AVAILABLE = True
except ImportError:
    print("Warning: Rust core not compiled. Running in Python-only mode.")
    RUST_AVAILABLE = False

app = FastAPI(title="IPDA 3D Viewer Backend")

# Initialize the Engine
engine = IPDAEngine()

# Simulation State
sim_state = {
    "price": 1.0800,
    "volatility": 0.2,
    "phase": 0.0,
    "severity": 0.1
}

@app.get("/")
async def get():
    # Serve the self-contained HTML file
    html_file = Path("../templates/index.html")
    if not html_file.exists():
        return {"error": "Frontend not found at templates/index.html"}
    return HTMLResponse(content=html_file.read_text())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to IPDA Data Stream")
    
    try:
        while True:
            start_time = time.time()
            
            # 1. Update Market Simulation (Mock Data)
            # In production, this fetches from Redis/Postgres
            sim_state["phase"] += 0.1
            sim_state["price"] += (np.random.random() - 0.5) * 0.0005
            
            # Random volatility spikes (simulating News events)
            if np.random.random() > 0.95:
                sim_state["volatility"] = min(1.0, sim_state["volatility"] + 0.3)
            else:
                sim_state["volatility"] = max(0.1, sim_state["volatility"] - 0.05)

            # 2. Compute Heavy Math in JAX
            manifold_z = engine.compute_manifold(sim_state["volatility"])
            point_cloud = engine.generate_state_vector(sim_state["price"], sim_state["phase"])
            
            # 3. Calculate System Health
            # Detect TDA holes (heuristic: high volatility = fractures)
            holes = 1 if sim_state["volatility"] > 0.7 else 0
            obnfe_score = engine.calculate_obnfe_score(sim_state["price"], holes)
            sim_state["severity"] = obnfe_score

            # 4. Check Rust Safety Layer (The Kill Switch)
            system_safe = True
            if RUST_AVAILABLE:
                # Call Rust function
                system_safe = ipda_core.check_safety_obnfe(obnfe_score)
            
            # 5. Prepare Payload for 3D Frontend
            # We flatten arrays for JSON transmission
            payload = {
                "type": "UPDATE",
                "timestamp": datetime.utcnow().isoformat(),
                "manifold": manifold_z.flatten().tolist(), # Flattened Z-grid
                "pointCloud": point_cloud.tolist(),       # N x 3 array
                "metrics": {
                    "obnfe": obnfe_score,
                    "price": sim_state["price"],
                    "volatility": sim_state["volatility"],
                    "killzone": 1 if 7 <= datetime.utcnow().hour < 16 else 0 # Mock UTC Killzone
                },
                "system": {
                    "safe": system_safe,
                    "status": "COHERENT" if system_safe else "KERNEL PANIC"
                }
            }

            # 6. Send to Frontend
            await websocket.send_json(payload)
            
            # Maintain ~30-60 FPS update rate
            elapsed = time.time() - start_time
            await asyncio.sleep(max(0, 0.033 - elapsed))

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    # To run: uvicorn api.main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
