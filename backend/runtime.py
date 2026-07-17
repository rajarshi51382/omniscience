import networkx as nx
from typing import Dict, List, Any, Tuple
from backend.agents import WorldAgent

class TimeStepEngine:
    def __init__(self, compiled_graph: Dict[str, Any]):
        self.title = compiled_graph.get("title", "Simulation Model")
        self.description = compiled_graph.get("description", "")
        self.raw_nodes = compiled_graph.get("nodes", [])
        self.raw_edges = compiled_graph.get("edges", [])
        self.timestep = 0
        
        # Build agent instances
        self.agents: Dict[str, WorldAgent] = {}
        for nd in self.raw_nodes:
            agent = WorldAgent(nd)
            self.agents[agent.id] = agent
            
        # Register edge neighbor connections
        for ed in self.raw_edges:
            source = ed["source"]
            target = ed["target"]
            if source in self.agents and target in self.agents:
                self.agents[source].link_neighbor(target)
                self.agents[target].link_neighbor(source)

        # NetworkX graph representation (useful for analytics)
        self.G = nx.DiGraph()
        for nd in self.raw_nodes:
            self.G.add_node(nd["id"], label=nd["label"], type=nd.get("type"))
        for ed in self.raw_edges:
            self.G.add_edge(ed["source"], ed["target"], label=ed.get("label", ""))

    def step(self, count: int = 1) -> Dict[str, Any]:
        """Advances the simulation by `count` ticks."""
        for _ in range(count):
            self.timestep += 1
            
            # Step 1: Accumulate outbound messages from all agents
            all_outbound_messages = []
            for agent_id, agent in self.agents.items():
                messages = agent.step(self.agents)
                all_outbound_messages.extend(messages)
                
            # Step 2: Route messages to their corresponding target agents
            for msg in all_outbound_messages:
                target_id = msg.get("target")
                if target_id in self.agents:
                    self.agents[target_id].receive_message(msg)

        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        """Aggregates and compiles the live state and performance metrics."""
        nodes_summary = []
        total_util = 0.0
        total_items = 0
        total_delay = 0.0
        total_failures = 0
        
        highest_queue = -1
        bottleneck_id = None
        bottleneck_reason = "None"
        
        for agent_id, agent in self.agents.items():
            state_data = dict(agent.state)
            metrics_data = dict(agent.metrics)
            
            nodes_summary.append({
                "id": agent.id,
                "label": agent.label,
                "type": agent.type,
                "state": state_data,
                "metrics": metrics_data
            })
            
            total_util += metrics_data.get("utilization", 0.0)
            total_items += metrics_data.get("processed_items", 0)
            total_delay += metrics_data.get("avg_delay", 0.0)
            total_failures += metrics_data.get("failures", 0)
            
            # Check for bottlenecks: highest queue_size or delay
            q_size = state_data.get("queue_size", 0)
            if q_size > highest_queue and agent.type != "shelf": # Shelves are storage, not operational bottlenecks
                highest_queue = q_size
                bottleneck_id = agent.id
                bottleneck_reason = f"Queue Congestion ({q_size} items)"
                
            if state_data.get("status") == "broken":
                bottleneck_id = agent.id
                bottleneck_reason = "Entity Breakdown (Offline)"
                
        num_agents = max(1, len(self.agents))
        avg_utilization = round(total_util / num_agents, 2)
        avg_delay = round(total_delay / num_agents, 2)
        
        # Determine bottleneck label
        bottleneck_label = "None"
        if bottleneck_id and bottleneck_id in self.agents:
            bottleneck_label = self.agents[bottleneck_id].label

        # Recommended action based on bottleneck
        recommendation = "System running optimally."
        if bottleneck_id:
            agent = self.agents[bottleneck_id]
            if agent.type == "robot":
                recommendation = f"Critical: Recharge or service {agent.label} immediately."
            elif agent.type == "dock":
                recommendation = f"Congestion detected at {agent.label}. Re-route AMRs to alternative zones or increase load processing rate."
            elif agent.type == "worker":
                recommendation = f"Worker fatigue or overload at {agent.label}. Allocate dynamic helper agents to Zone B."
            elif agent.state.get("status") == "broken":
                recommendation = f"Deploy maintenance crew to repair {agent.label}."

        # Average throughput (items processed per tick)
        throughput = round(total_items / max(1, self.timestep), 2)
        
        # Calculate failure probability (ratio of failed steps)
        failure_prob_pct = min(100, int((total_failures / max(1, total_items)) * 100)) if total_items > 0 else 0
        if total_failures > 0 and failure_prob_pct == 0:
            failure_prob_pct = 2 # minimum visible percentage if failures exist

        return {
            "title": self.title,
            "description": self.description,
            "timestep": self.timestep,
            "nodes": nodes_summary,
            "edges": self.raw_edges,
            "metrics": {
                "throughput": throughput,
                "avg_utilization": avg_utilization,
                "avg_delay": avg_delay,
                "failure_probability": f"{failure_prob_pct}%",
                "total_failures": total_failures,
                "total_items_processed": total_items
            },
            "analysis": {
                "bottleneck": bottleneck_label,
                "bottleneck_reason": bottleneck_reason,
                "recommendation": recommendation
            }
        }
