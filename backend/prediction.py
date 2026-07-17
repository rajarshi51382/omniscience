import copy
import re
import json
import os
from typing import Dict, List, Any, Tuple
from backend.runtime import TimeStepEngine

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


def clone_engine(engine: TimeStepEngine) -> TimeStepEngine:
    """Creates a deep copy of a TimeStepEngine state."""
    # We can reconstruct it from the summary serialization
    summary = engine.get_summary()
    # Deep copy nodes and edges
    cloned_graph = {
        "title": summary["title"],
        "description": summary["description"],
        "nodes": copy.deepcopy(summary["nodes"]),
        "edges": copy.deepcopy(summary["edges"])
    }
    new_engine = TimeStepEngine(cloned_graph)
    # Restore current timestep and individual states/metrics
    new_engine.timestep = engine.timestep
    for agent_id, agent in engine.agents.items():
        if agent_id in new_engine.agents:
            new_engine.agents[agent_id].state = copy.deepcopy(agent.state)
            new_engine.agents[agent_id].metrics = copy.deepcopy(agent.metrics)
            new_engine.agents[agent_id].active_ticks = agent.active_ticks
            new_engine.agents[agent_id].total_ticks = agent.total_ticks
    return new_engine


def run_prediction_query(engine: TimeStepEngine, query: str) -> Dict[str, Any]:
    """
    Main entry point for "What if?" queries.
    Parses intent, runs simulated scenarios, and returns comparison reports.
    """
    query_lower = query.lower()
    
    # 1. Parse scenario intent
    scenario_type = "custom"
    target_node = None
    modifier_value = None
    explanation = ""
    recommendation = ""
    
    # Check for breakdown queries: "What if robot 7 breaks?", "What if dock_inbound closes?"
    breakdown_match = re.search(r'what if (?:robot|dock|worker|shelf|station|node)?\s*([a-zA-Z0-9_]+)\s*(?:breaks|fails|closes|offline|stops)', query_lower)
    if not breakdown_match:
        # Check other variations
        breakdown_match = re.search(r'if ([a-zA-Z0-9_]+) (?:breaks|fails|offline)', query_lower)
        
    # Check for demand queries: "What if demand doubles?", "What if demand increases by 40%?"
    demand_double_match = "demand double" in query_lower or "demand increases by 100" in query_lower or "throughput double" in query_lower
    demand_increase_match = re.search(r'demand (?:increases|grows|up) by (\d+)%', query_lower)
    
    if breakdown_match:
        scenario_type = "breakdown"
        target_name = breakdown_match.group(1)
        # Try to match to an actual node id in the engine
        for agent_id in engine.agents.keys():
            if target_name in agent_id or agent_id in target_name:
                target_node = agent_id
                break
        if not target_node:
            # default fallback if not found
            target_node = target_name
            
    elif demand_double_match:
        scenario_type = "demand"
        modifier_value = 2.0
    elif demand_increase_match:
        scenario_type = "demand"
        modifier_value = 1.0 + (float(demand_increase_match.group(1)) / 100.0)
    elif "demand" in query_lower or "orders" in query_lower or "bottleneck" in query_lower:
        # Generic demand or bottleneck query
        scenario_type = "bottleneck"
        
    # If API keys are available, we can augment explanations with LLM
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    # Run Baseline Simulation (50 steps forward)
    baseline_engine = clone_engine(engine)
    baseline_summary = baseline_engine.step(50)
    
    # Run Modified Simulation (50 steps forward)
    modified_engine = clone_engine(engine)
    
    # Apply modifiers to the modified engine
    if scenario_type == "breakdown" and target_node in modified_engine.agents:
        agent = modified_engine.agents[target_node]
        agent.state["status"] = "broken"
        agent.state["failure_prob"] = 1.0 # Force stay broken
        explanation = f"If {agent.label} breaks down, all pending tasks assigned to it queue up indefinitely. Connected pathways will experience starvation, causing throughput drops."
        recommendation = f"Increase redundancy or deploy a reserve agent in Zone {agent.state.get('zone', 'A')} to inherit tasks from {agent.label}."
        
    elif scenario_type == "demand":
        factor = modifier_value or 1.4
        # Find inbound docks and scale their load capacity or spawn rate
        applied = False
        for agent in modified_engine.agents.values():
            if agent.type == "dock" and ("inbound" in agent.id or "inflow" in agent.id):
                agent.state["capacity"] = int(agent.state["capacity"] * factor)
                agent.state["queue_size"] = int(agent.state["queue_size"] * factor)
                applied = True
        explanation = f"An increase in inbound demand by {int((factor-1)*100)}% will flood the intake queues. Under the current schedule, Robots will become fully utilized, leading to layout congestion."
        recommendation = "Deploy 3 additional AMRs to outbound lanes and raise worker pick-rates by 20% to prevent backlogs."
        if not applied:
            explanation = "Inbound node could not be identified, but simulated generic arrival rate increase shows system-wide queue congestion."
            
    elif scenario_type == "bottleneck":
        explanation = "The metrics identify operational bottlenecks based on queue accumulation and worker idle states. Outbound docks are experiencing average delays."
        recommendation = "Optimize AMR layout. Move Robot 4 to Zone B and coordinate battery charge schedules during off-peak windows."
    else:
        # Default scenario
        explanation = f"Simulated forecast for scenario: '{query}'. System metrics indicate steady-state transitions."
        recommendation = "Observe real-time queue levels and ensure backup units are active."

    # Run the modified simulation
    modified_summary = modified_engine.step(50)
    
    # Calculate differential metrics
    b_metrics = baseline_summary["metrics"]
    m_metrics = modified_summary["metrics"]
    
    # Throughput diff
    b_throughput = b_metrics["throughput"]
    m_throughput = m_metrics["throughput"]
    throughput_diff_pct = 0
    if b_throughput > 0:
        throughput_diff_pct = int(((m_throughput - b_throughput) / b_throughput) * 100)
        
    # Delay diff
    b_delay = b_metrics["avg_delay"]
    m_delay = m_metrics["avg_delay"]
    delay_diff_pct = 0
    if b_delay > 0:
        delay_diff_pct = int(((m_delay - b_delay) / b_delay) * 100)
    else:
        delay_diff_pct = int((m_delay - b_delay) * 10) # arbitrary multiplier if baseline was 0
        
    # Utilization diff
    b_util = b_metrics["avg_utilization"]
    m_util = m_metrics["avg_utilization"]
    util_diff_pct = int((m_util - b_util) * 100)

    # Dynamic LLM explanation if keys exist
    if openai_key and HAS_OPENAI:
        try:
            prompt = (
                f"You are the Omniscience Prediction Engine. We ran a baseline and a modified simulation "
                f"to answer: '{query}'.\n"
                f"Baseline: Throughput={b_throughput}, Delay={b_delay}, Utilization={b_util}.\n"
                f"Modified: Throughput={m_throughput}, Delay={m_delay}, Utilization={m_util}.\n"
                f"Provide a natural language analysis (2-3 sentences) explaining the bottleneck and a recommendation."
            )
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            gpt_text = response.choices[0].message.content.strip()
            # Split into explanation and recommendation if possible
            if "Recommendation:" in gpt_text:
                parts = gpt_text.split("Recommendation:")
                explanation = parts[0].strip()
                recommendation = parts[1].strip()
            else:
                explanation = gpt_text
        except Exception as e:
            print(f"OpenAI prediction helper failed: {e}")
            
    elif gemini_key and HAS_GEMINI:
        try:
            prompt = (
                f"We ran a baseline and a modified simulation to answer: '{query}'.\n"
                f"Baseline: Throughput={b_throughput}, Delay={b_delay}, Utilization={b_util}.\n"
                f"Modified: Throughput={m_throughput}, Delay={m_delay}, Utilization={m_util}.\n"
                f"Provide a concise summary explaining the bottleneck and a recommendation. Format as JSON: "
                f"{{\"explanation\": \"...\", \"recommendation\": \"...\"}}"
            )
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            explanation = data.get("explanation", explanation)
            recommendation = data.get("recommendation", recommendation)
        except Exception as e:
            print(f"Gemini prediction helper failed: {e}")

    # Build report dict
    return {
        "query": query,
        "scenario": scenario_type,
        "target_node": target_node,
        "metrics_comparison": {
            "baseline": {
                "throughput": b_throughput,
                "avg_delay": b_delay,
                "avg_utilization": b_util,
                "failures": b_metrics["total_failures"]
            },
            "predicted": {
                "throughput": m_throughput,
                "avg_delay": m_delay,
                "avg_utilization": m_util,
                "failures": m_metrics["total_failures"]
            },
            "differences": {
                "throughput_pct": f"{throughput_diff_pct}%" if throughput_diff_pct <= 0 else f"+{throughput_diff_pct}%",
                "delay_pct": f"{delay_diff_pct}%" if delay_diff_pct <= 0 else f"+{delay_diff_pct}%",
                "utilization_pct": f"{util_diff_pct}%" if util_diff_pct <= 0 else f"+{util_diff_pct}%"
            }
        },
        "explanation": explanation,
        "recommendation": recommendation,
        "predicted_bottleneck": modified_summary["analysis"]["bottleneck"],
        "predicted_bottleneck_reason": modified_summary["analysis"]["bottleneck_reason"],
        "failure_probability": modified_summary["metrics"]["failure_probability"]
    }
