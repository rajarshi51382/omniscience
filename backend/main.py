import os
import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.compiler import compile_world
from backend.runtime import TimeStepEngine
from backend.prediction import run_prediction_query

app = FastAPI(title="Omniscience v0.1 API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "/Users/rajarshighosh/Downloads/omniscience/omniscience.db"

# Global runtime state
class ActiveSession:
    def __init__(self):
        self.engine: Optional[TimeStepEngine] = None
        self.world_id: Optional[str] = None
        self.original_graph: Optional[Dict[str, Any]] = None

session = ActiveSession()

def init_db():
    """Initializes SQLite database tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS worlds (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            graph_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simulations (
            id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            step INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(world_id) REFERENCES worlds(id)
        )
    """)
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

# Pydantic models for request validation
class CompileRequest(BaseModel):
    prompt: str

class StepRequest(BaseModel):
    steps: int = 1

class QueryRequest(BaseModel):
    query: str

@app.post("/api/compile")
def api_compile(req: CompileRequest):
    """Compiles a physical system description into a simulation model."""
    try:
        # Compile world system
        graph = compile_world(req.prompt)
        world_id = str(uuid.uuid4())
        
        # Save to SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO worlds (id, title, description, graph_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (world_id, graph["title"], graph.get("description", ""), json.dumps(graph), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        
        # Load into active runtime
        session.engine = TimeStepEngine(graph)
        session.world_id = world_id
        session.original_graph = graph
        
        summary = session.engine.get_summary()
        summary["world_id"] = world_id
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compilation error: {str(e)}")

@app.post("/api/simulate/step")
def api_simulate_step(req: StepRequest):
    """Advances the simulation by N timesteps."""
    if not session.engine:
        raise HTTPException(status_code=400, detail="No active simulation. Compile a world first.")
    
    try:
        # Advance simulation
        summary = session.engine.step(req.steps)
        summary["world_id"] = session.world_id
        
        # Log step to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO simulations (id, world_id, step, state_json, timestamp) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), session.world_id, session.engine.timestep, json.dumps(summary), datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation stepping error: {str(e)}")

@app.post("/api/simulate/query")
def api_simulate_query(req: QueryRequest):
    """Runs a 'What if?' prediction query using simulation branching."""
    if not session.engine:
        raise HTTPException(status_code=400, detail="No active simulation. Compile a world first.")
    
    try:
        report = run_prediction_query(session.engine, req.query)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction query error: {str(e)}")

@app.post("/api/simulate/reset")
def api_simulate_reset():
    """Resets the simulation to the initial compiled state."""
    if not session.original_graph:
        raise HTTPException(status_code=400, detail="No active simulation to reset.")
    
    try:
        # Re-initialize engine
        session.engine = TimeStepEngine(session.original_graph)
        summary = session.engine.get_summary()
        summary["world_id"] = session.world_id
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset error: {str(e)}")

@app.get("/api/simulate/status")
def api_simulate_status():
    """Gets the current status of the active simulation."""
    if not session.engine:
        return {"status": "inactive", "message": "No world compiled yet."}
    
    summary = session.engine.get_summary()
    summary["world_id"] = session.world_id
    summary["status"] = "active"
    return summary

@app.get("/api/worlds")
def api_list_worlds():
    """Lists all compiled worlds in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, created_at FROM worlds ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    worlds = []
    for r in rows:
        worlds.append({
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "created_at": r[3]
        })
    return worlds
