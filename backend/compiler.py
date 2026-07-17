import re
import os
import random
import json
from typing import Dict, List, Any, Tuple

# Attempt to import LLM libraries
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Fallback presets for known configurations
PRESETS = {
    "warehouse": {
        "title": "Automated Fulfillment Center",
        "description": "A distribution center simulation featuring autonomous mobile robots (AMRs), zone picking shelves, picking workers, and inbound/outbound docks.",
        "nodes": [
            # Docks
            {"id": "dock_inbound", "label": "Inbound Dock", "type": "dock", "state": {"status": "active", "queue_size": 2, "capacity": 50, "load": 0.1, "failure_prob": 0.02, "zone": "Zone A"}, "metrics": {"utilization": 0.65, "processed_items": 120, "avg_delay": 4.2, "failures": 0}},
            {"id": "dock_outbound", "label": "Outbound Dock", "type": "dock", "state": {"status": "active", "queue_size": 4, "capacity": 50, "load": 0.3, "failure_prob": 0.05, "zone": "Zone C"}, "metrics": {"utilization": 0.85, "processed_items": 145, "avg_delay": 8.5, "failures": 0}},
            # Workers
            {"id": "worker_1", "label": "Worker 1 (Picking)", "type": "worker", "state": {"status": "active", "queue_size": 1, "capacity": 10, "load": 0.2, "failure_prob": 0.01, "zone": "Zone B"}, "metrics": {"utilization": 0.70, "processed_items": 80, "avg_delay": 1.5, "failures": 0}},
            {"id": "worker_2", "label": "Worker 2 (Packing)", "type": "worker", "state": {"status": "active", "queue_size": 2, "capacity": 10, "load": 0.4, "failure_prob": 0.01, "zone": "Zone B"}, "metrics": {"utilization": 0.75, "processed_items": 95, "avg_delay": 2.1, "failures": 0}},
        ],
        "edges": []
    },
    "factory": {
        "title": "Smart Assembly Line",
        "description": "A modern manufacturing line with automated welding stations, conveyor systems, quality control booths, and warehousing.",
        "nodes": [
            {"id": "inflow", "label": "Raw Materials Inflow", "type": "dock", "state": {"status": "active", "queue_size": 10, "capacity": 100, "load": 0.2, "failure_prob": 0.01, "zone": "Supply"}, "metrics": {"utilization": 0.40, "processed_items": 300, "avg_delay": 0.5, "failures": 0}},
            {"id": "welding", "label": "Welding Station", "type": "station", "state": {"status": "active", "queue_size": 5, "capacity": 15, "load": 0.55, "failure_prob": 0.08, "zone": "Assembly A"}, "metrics": {"utilization": 0.80, "processed_items": 180, "avg_delay": 12.0, "failures": 2}},
            {"id": "painting", "label": "Painting Booth", "type": "station", "state": {"status": "active", "queue_size": 3, "capacity": 10, "load": 0.35, "failure_prob": 0.04, "zone": "Assembly B"}, "metrics": {"utilization": 0.60, "processed_items": 175, "avg_delay": 7.2, "failures": 0}},
            {"id": "assembly", "label": "Final Assembly", "type": "station", "state": {"status": "active", "queue_size": 6, "capacity": 20, "load": 0.70, "failure_prob": 0.03, "zone": "Assembly C"}, "metrics": {"utilization": 0.90, "processed_items": 160, "avg_delay": 15.4, "failures": 1}},
            {"id": "qc", "label": "Quality Control Booth", "type": "worker", "state": {"status": "active", "queue_size": 1, "capacity": 8, "load": 0.15, "failure_prob": 0.02, "zone": "Inspection"}, "metrics": {"utilization": 0.55, "processed_items": 155, "avg_delay": 3.0, "failures": 0}},
            {"id": "storage", "label": "Finished Goods Storage", "type": "shelf", "state": {"status": "active", "queue_size": 0, "capacity": 500, "load": 0.45, "failure_prob": 0.0, "zone": "Warehouse"}, "metrics": {"utilization": 0.45, "processed_items": 150, "avg_delay": 0.1, "failures": 0}}
        ],
        "edges": [
            {"source": "inflow", "target": "welding", "label": "conveyor_belt"},
            {"source": "welding", "target": "painting", "label": "conveyor_belt"},
            {"source": "painting", "target": "assembly", "label": "conveyor_belt"},
            {"source": "assembly", "target": "qc", "label": "transfer"},
            {"source": "qc", "target": "storage", "label": "store_goods"}
        ]
    },
    "drones": {
        "title": "Metropolitan Drone Delivery Network",
        "description": "An aerial delivery service using quadcopters flying routes between charging bases, merchant hubs, and customer dropzones.",
        "nodes": [
            {"id": "hub_central", "label": "Central Distribution Hub", "type": "dock", "state": {"status": "active", "queue_size": 12, "capacity": 200, "load": 0.35, "failure_prob": 0.01, "zone": "Downtown"}, "metrics": {"utilization": 0.60, "processed_items": 520, "avg_delay": 1.2, "failures": 0}},
            {"id": "zone_north", "label": "Delivery Zone North", "type": "shelf", "state": {"status": "active", "queue_size": 0, "capacity": 50, "load": 0.15, "failure_prob": 0.0, "zone": "North Heights"}, "metrics": {"utilization": 0.30, "processed_items": 160, "avg_delay": 15.0, "failures": 0}},
            {"id": "zone_south", "label": "Delivery Zone South", "type": "shelf", "state": {"status": "active", "queue_size": 0, "capacity": 50, "load": 0.25, "failure_prob": 0.0, "zone": "South Plaza"}, "metrics": {"utilization": 0.50, "processed_items": 220, "avg_delay": 18.5, "failures": 1}},
            {"id": "charge_station_1", "label": "Battery Recharge Station A", "type": "station", "state": {"status": "active", "queue_size": 3, "capacity": 10, "load": 0.60, "failure_prob": 0.03, "zone": "Midtown Hub"}, "metrics": {"utilization": 0.78, "processed_items": 140, "avg_delay": 25.0, "failures": 0}},
            {"id": "charge_station_2", "label": "Battery Recharge Station B", "type": "station", "state": {"status": "active", "queue_size": 1, "capacity": 10, "load": 0.20, "failure_prob": 0.03, "zone": "Plaza Hub"}, "metrics": {"utilization": 0.35, "processed_items": 85, "avg_delay": 22.0, "failures": 0}}
        ],
        "edges": [
            {"source": "hub_central", "target": "charge_station_1", "label": "flight_corridor"},
            {"source": "charge_station_1", "target": "zone_north", "label": "flight_corridor"},
            {"source": "hub_central", "target": "charge_station_2", "label": "flight_corridor"},
            {"source": "charge_station_2", "target": "zone_south", "label": "flight_corridor"},
            {"source": "zone_north", "target": "hub_central", "label": "return_route"},
            {"source": "zone_south", "target": "hub_central", "label": "return_route"}
        ]
    },
    "traffic": {
        "title": "Smart Traffic Intersection",
        "description": "A signalized arterial crossroad with vehicle flow detectors, adaptive timing loops, and transit priority queues.",
        "nodes": [
            {"id": "lane_north", "label": "Northbound Approaching Lane", "type": "dock", "state": {"status": "active", "queue_size": 18, "capacity": 40, "load": 0.65, "failure_prob": 0.0, "zone": "Intersection North"}, "metrics": {"utilization": 0.82, "processed_items": 640, "avg_delay": 45.0, "failures": 0}},
            {"id": "lane_south", "label": "Southbound Approaching Lane", "type": "dock", "state": {"status": "active", "queue_size": 22, "capacity": 40, "load": 0.75, "failure_prob": 0.0, "zone": "Intersection South"}, "metrics": {"utilization": 0.88, "processed_items": 720, "avg_delay": 55.2, "failures": 0}},
            {"id": "lane_east", "label": "Eastbound Approaching Lane", "type": "dock", "state": {"status": "active", "queue_size": 8, "capacity": 40, "load": 0.30, "failure_prob": 0.0, "zone": "Intersection East"}, "metrics": {"utilization": 0.45, "processed_items": 310, "avg_delay": 18.0, "failures": 0}},
            {"id": "lane_west", "label": "Westbound Approaching Lane", "type": "dock", "state": {"status": "active", "queue_size": 12, "capacity": 40, "load": 0.45, "failure_prob": 0.0, "zone": "Intersection West"}, "metrics": {"utilization": 0.58, "processed_items": 420, "avg_delay": 26.5, "failures": 0}},
            {"id": "signal_controller", "label": "Adaptive Signal Controller", "type": "worker", "state": {"status": "active", "queue_size": 0, "capacity": 1, "load": 1.0, "failure_prob": 0.005, "zone": "Core"}, "metrics": {"utilization": 1.0, "processed_items": 2090, "avg_delay": 0.1, "failures": 0}},
            {"id": "exit_junction", "label": "Junction Discharge Exit", "type": "shelf", "state": {"status": "active", "queue_size": 2, "capacity": 160, "load": 0.15, "failure_prob": 0.0, "zone": "Discharge"}, "metrics": {"utilization": 0.25, "processed_items": 2085, "avg_delay": 1.2, "failures": 0}}
        ],
        "edges": [
            {"source": "lane_north", "target": "signal_controller", "label": "flow_detector"},
            {"source": "lane_south", "target": "signal_controller", "label": "flow_detector"},
            {"source": "lane_east", "target": "signal_controller", "label": "flow_detector"},
            {"source": "lane_west", "target": "signal_controller", "label": "flow_detector"},
            {"source": "signal_controller", "target": "exit_junction", "label": "discharge_signal"}
        ]
    },
    "hospital": {
        "title": "Emergency Department Workflow",
        "description": "An emergency department patient pathway from initial triage to clinical exam rooms, pathology lab, and holding beds.",
        "nodes": [
            {"id": "triage", "label": "Triage Assessment Desk", "type": "dock", "state": {"status": "active", "queue_size": 6, "capacity": 20, "load": 0.45, "failure_prob": 0.01, "zone": "Admissions"}, "metrics": {"utilization": 0.88, "processed_items": 110, "avg_delay": 14.5, "failures": 0}},
            {"id": "waiting_room", "label": "Waiting Area", "type": "shelf", "state": {"status": "active", "queue_size": 18, "capacity": 50, "load": 0.55, "failure_prob": 0.0, "zone": "Admissions"}, "metrics": {"utilization": 0.55, "processed_items": 104, "avg_delay": 42.0, "failures": 0}},
            {"id": "exam_bay", "label": "Clinical Examination Bays", "type": "station", "state": {"status": "active", "queue_size": 4, "capacity": 8, "load": 0.85, "failure_prob": 0.02, "zone": "Treatment A"}, "metrics": {"utilization": 0.94, "processed_items": 78, "avg_delay": 65.0, "failures": 1}},
            {"id": "lab", "label": "Pathology Diagnostics Lab", "type": "worker", "state": {"status": "active", "queue_size": 3, "capacity": 15, "load": 0.30, "failure_prob": 0.03, "zone": "Diagnostics"}, "metrics": {"utilization": 0.58, "processed_items": 45, "avg_delay": 28.0, "failures": 0}},
            {"id": "ward", "label": "Observation Beds Ward", "type": "shelf", "state": {"status": "active", "queue_size": 1, "capacity": 20, "load": 0.70, "failure_prob": 0.0, "zone": "Inpatient"}, "metrics": {"utilization": 0.70, "processed_items": 32, "avg_delay": 12.0, "failures": 0}}
        ],
        "edges": [
            {"source": "triage", "target": "waiting_room", "label": "waitlist"},
            {"source": "waiting_room", "target": "exam_bay", "label": "admit"},
            {"source": "exam_bay", "target": "lab", "label": "lab_referral"},
            {"source": "lab", "target": "exam_bay", "label": "results_return"},
            {"source": "exam_bay", "target": "ward", "label": "observe"}
        ]
    }
}


def compile_world(prompt: str) -> Dict[str, Any]:
    """
    Main entry point for compiler.
    Parses prompt and outputs world simulation graph.
    """
    prompt_lower = prompt.lower()
    
    # 1. Match presets first
    preset_key = None
    if "warehouse" in prompt_lower or "shelf" in prompt_lower or "shelves" in prompt_lower:
        preset_key = "warehouse"
    elif "factory" in prompt_lower or "manufacturing" in prompt_lower or "assembly line" in prompt_lower:
        preset_key = "factory"
    elif "drone" in prompt_lower or "aerial" in prompt_lower or "quadcopter" in prompt_lower:
        preset_key = "drones"
    elif "traffic" in prompt_lower or "intersection" in prompt_lower or "crossroad" in prompt_lower:
        preset_key = "traffic"
    elif "hospital" in prompt_lower or "emergency" in prompt_lower or "triage" in prompt_lower or "clinic" in prompt_lower:
        preset_key = "hospital"
        
    if preset_key:
        return generate_preset_graph(preset_key, prompt)

    # 2. Try LLM Compile if Key is set
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if openai_key and HAS_OPENAI:
        try:
            return compile_with_openai(prompt, openai_key)
        except Exception as e:
            print(f"OpenAI compilation failed: {e}. Falling back to heuristics.")
            
    if gemini_key and HAS_GEMINI:
        try:
            return compile_with_gemini(prompt, gemini_key)
        except Exception as e:
            print(f"Gemini compilation failed: {e}. Falling back to heuristics.")

    # 3. Fallback: Robust Heuristic Parser
    return compile_with_heuristics(prompt)


def generate_preset_graph(preset_name: str, raw_prompt: str) -> Dict[str, Any]:
    """
    Spawns preset graphs, scaling the entity count based on numbers parsed in prompt.
    E.g. 'Warehouse with 15 robots' => creates 15 robot nodes.
    """
    preset = json.loads(json.dumps(PRESETS[preset_name])) # deepcopy
    
    # Find any numbers in prompt
    numbers = [int(n) for n in re.findall(r'\b\d+\b', raw_prompt)]
    
    if preset_name == "warehouse":
        robot_count = 15 # default
        shelf_count = 300 # default
        
        if len(numbers) >= 1:
            robot_count = numbers[0]
        if len(numbers) >= 2:
            shelf_count = numbers[1]
            
        # Limit nodes to prevent visual crash in prototype
        robot_count = max(2, min(robot_count, 150))
        shelf_count = max(2, min(shelf_count, 200))
        
        # Add shelf nodes (aggregate zones)
        zones = ["Zone A", "Zone B", "Zone C"]
        shelves_per_zone = max(1, shelf_count // len(zones))
        for i, zone in enumerate(zones):
            preset["nodes"].append({
                "id": f"shelf_zone_{i+1}",
                "label": f"Shelves Group {zone} ({shelves_per_zone} shelves)",
                "type": "shelf",
                "state": {"status": "active", "queue_size": 0, "capacity": shelves_per_zone * 20, "load": 0.4, "failure_prob": 0.0, "zone": zone},
                "metrics": {"utilization": 0.4, "processed_items": 0, "avg_delay": 0.0, "failures": 0}
            })
            
        # Add robots
        for i in range(robot_count):
            robot_id = f"robot_{i+1}"
            zone = zones[i % len(zones)]
            preset["nodes"].append({
                "id": robot_id,
                "label": f"Robot {i+1}",
                "type": "robot",
                "state": {
                    "status": "idle",
                    "queue_size": 0,
                    "capacity": 5,
                    "load": 0.0,
                    "failure_prob": 0.05,
                    "zone": zone,
                    "current_node": f"shelf_zone_{(i%3)+1}",
                    "battery": 100
                },
                "metrics": {
                    "utilization": 0.0,
                    "processed_items": 0,
                    "avg_delay": 0.0,
                    "failures": 0
                }
            })
            
            # Connect robots to their starting shelves and the inbound/outbound docks
            preset["edges"].append({"source": robot_id, "target": f"shelf_zone_{(i%3)+1}", "label": "moves_goods"})
            preset["edges"].append({"source": "dock_inbound", "target": robot_id, "label": "assign_order"})
            preset["edges"].append({"source": robot_id, "target": "dock_outbound", "label": "deposit_order"})
            
        # Also connect shelves to picking workers and workers to outbound dock
        for i, zone in enumerate(zones):
            preset["edges"].append({"source": f"shelf_zone_{i+1}", "target": "worker_1" if i < 2 else "worker_2", "label": "pick_line"})
        
        preset["edges"].append({"source": "worker_1", "target": "dock_outbound", "label": "deposit"})
        preset["edges"].append({"source": "worker_2", "target": "dock_outbound", "label": "deposit"})
        
    return preset


def compile_with_heuristics(prompt: str) -> Dict[str, Any]:
    """
    Fallback parser when no presets match and no LLM is configured.
    Strips out noun subjects and counts, generates nodes and maps links logically.
    """
    # 1. Parse potential nodes
    # Look for patterns like "10 robots", "3 conveyor belts", "hospital with 5 beds"
    nodes = []
    edges = []
    
    # Standard fallback entities
    found_entities = {}
    
    # regex matches e.g. "15 robots", "3 docks", "2 workers"
    matches = re.findall(r'(\d+)\s+([a-zA-Z]+s?)', prompt)
    
    if not matches:
        # Default entities if nothing parseable
        found_entities = {"agent": 5, "controller": 1, "station": 2}
    else:
        for count, name in matches:
            name = name.lower().rstrip('s') # singular
            if name in ["robot", "drone", "vehicle", "truck", "car"]:
                found_entities["robot"] = max(1, min(int(count), 50))
            elif name in ["shelf", "rack", "bin", "storage", "bed", "warehouse"]:
                found_entities["shelf"] = max(1, min(int(count), 50))
            elif name in ["dock", "port", "inflow", "terminal", "station"]:
                found_entities["dock"] = max(1, min(int(count), 10))
            elif name in ["worker", "person", "operator", "staff", "nurse", "doctor"]:
                found_entities["worker"] = max(1, min(int(count), 20))
            else:
                found_entities[name] = max(1, min(int(count), 20))

    # Fill in dependencies to make graph complete
    if not found_entities:
        found_entities = {"robot": 10, "shelf": 5, "dock": 2}
        
    # Generate nodes
    node_ids = []
    for entity_type, count in found_entities.items():
        for i in range(count):
            node_id = f"{entity_type}_{i+1}"
            label = f"{entity_type.capitalize()} {i+1}"
            
            # Assign state based on types
            state = {
                "status": "idle" if entity_type == "robot" else "active",
                "queue_size": 0,
                "capacity": 10 if entity_type in ["dock", "shelf"] else 1,
                "load": 0.0,
                "failure_prob": 0.02,
                "zone": "Central"
            }
            
            nodes.append({
                "id": node_id,
                "label": label,
                "type": entity_type,
                "state": state,
                "metrics": {"utilization": 0.0, "processed_items": 0, "avg_delay": 0.0, "failures": 0}
            })
            node_ids.append((node_id, entity_type))

    # Link nodes together logically (e.g. Robot -> Shelf -> Dock)
    robots = [n for n in node_ids if n[1] == "robot"]
    shelves = [n for n in node_ids if n[1] == "shelf"]
    docks = [n for n in node_ids if n[1] == "dock"]
    workers = [n for n in node_ids if n[1] == "worker"]
    others = [n for n in node_ids if n[1] not in ["robot", "shelf", "dock", "worker"]]

    # Connect robots to shelves
    for r_id, _ in robots:
        if shelves:
            sh_id = random.choice(shelves)[0]
            edges.append({"source": r_id, "target": sh_id, "label": "accesses"})
        if docks:
            dk_id = random.choice(docks)[0]
            edges.append({"source": dk_id, "target": r_id, "label": "tasks"})

    # Connect shelves to workers/docks
    for sh_id, _ in shelves:
        if workers:
            w_id = random.choice(workers)[0]
            edges.append({"source": sh_id, "target": w_id, "label": "transfers"})
        elif docks:
            dk_id = random.choice(docks)[0]
            edges.append({"source": sh_id, "target": dk_id, "label": "feeds"})

    # Connect workers to docks
    for w_id, _ in workers:
        if docks:
            dk_id = random.choice(docks)[0]
            edges.append({"source": w_id, "target": dk_id, "label": "routes"})

    # Catch-all links for others
    for o_id, _ in others:
        if node_ids:
            target_id = random.choice(node_ids)[0]
            if target_id != o_id:
                edges.append({"source": o_id, "target": target_id, "label": "communicates"})

    return {
        "title": "Custom Simulation Model",
        "description": f"Heuristically compiled simulation of: '{prompt}'",
        "nodes": nodes,
        "edges": edges
    }


def compile_with_openai(prompt: str, api_key: str) -> Dict[str, Any]:
    """
    Utilizes OpenAI GPT models to compile a detailed simulation graph.
    """
    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are the Omniscience World Model Compiler. Your job is to convert a physical system description "
        "into a structured simulation network graph JSON. Provide valid JSON strictly. No extra chat. "
        "JSON format:\n"
        "{\n"
        "  \"title\": \"Name of the world\",\n"
        "  \"description\": \"Description of what the world does\",\n"
        "  \"nodes\": [\n"
        "    {\n"
        "      \"id\": \"unique_node_id\",\n"
        "      \"label\": \"Readable name\",\n"
        "      \"type\": \"robot|shelf|dock|worker|station\",\n"
        "      \"state\": { \"status\": \"idle|active|busy\", \"queue_size\": 0, \"capacity\": 10, \"load\": 0.1, \"failure_prob\": 0.02, \"zone\": \"Zone A\" },\n"
        "      \"metrics\": { \"utilization\": 0.0, \"processed_items\": 0, \"avg_delay\": 0.0, \"failures\": 0 }\n"
        "    }\n"
        "  ],\n"
        "  \"edges\": [\n"
        "    { \"source\": \"node_1_id\", \"target\": \"node_2_id\", \"label\": \"interaction_type\" }\n"
        "  ]\n"
        "}"
    )
    
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Compile this world system: {prompt}"}
        ],
        temperature=0.2
    )
    
    return json.loads(response.choices[0].message.content)


def compile_with_gemini(prompt: str, api_key: str) -> Dict[str, Any]:
    """
    Utilizes Gemini models to compile a detailed simulation graph.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    instructions = (
        "Convert this physical system description into a structured simulation network graph JSON. "
        "Output ONLY valid JSON matching this schema:\n"
        "{\n"
        "  \"title\": \"Name of the world\",\n"
        "  \"description\": \"Description of what the world does\",\n"
        "  \"nodes\": [\n"
        "    {\n"
        "      \"id\": \"unique_node_id\",\n"
        "      \"label\": \"Readable name\",\n"
        "      \"type\": \"robot|shelf|dock|worker|station\",\n"
        "      \"state\": { \"status\": \"idle|active|busy\", \"queue_size\": 0, \"capacity\": 10, \"load\": 0.1, \"failure_prob\": 0.02, \"zone\": \"Zone A\" },\n"
        "      \"metrics\": { \"utilization\": 0.0, \"processed_items\": 0, \"avg_delay\": 0.0, \"failures\": 0 }\n"
        "    }\n"
        "  ],\n"
        "  \"edges\": [\n"
        "    { \"source\": \"node_1_id\", \"target\": \"node_2_id\", \"label\": \"interaction_type\" }\n"
        "  ]\n"
        "}"
    )
    
    response = model.generate_content(f"{instructions}\n\nInput System: {prompt}")
    
    # Strip markdown block formatting if present
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())
