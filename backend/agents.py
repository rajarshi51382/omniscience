import random
from typing import Dict, List, Any, Optional

class WorldAgent:
    def __init__(self, node_data: Dict[str, Any]):
        self.id = node_data["id"]
        self.label = node_data["label"]
        self.type = node_data.get("type", "agent")
        
        # Current state
        self.state = dict(node_data.get("state", {}))
        
        # Ensure default state variables exist
        self.state.setdefault("status", "active")
        self.state.setdefault("queue_size", 0)
        self.state.setdefault("capacity", 10)
        self.state.setdefault("load", 0.0)
        self.state.setdefault("failure_prob", 0.02)
        self.state.setdefault("zone", "Central")
        if self.type == "robot":
            self.state.setdefault("battery", 100)
            self.state.setdefault("current_target", None)
            self.state.setdefault("progress", 0)
            
        # Memory
        self.memory: List[Dict[str, Any]] = []
        
        # Message Queue (messages from other agents)
        self.message_queue: List[Dict[str, Any]] = []
        
        # Neighbors
        self.neighbors: List[str] = []
        
        # Metrics
        self.metrics = dict(node_data.get("metrics", {
            "utilization": 0.0,
            "processed_items": 0,
            "avg_delay": 0.0,
            "failures": 0
        }))
        self.active_ticks = 0
        self.total_ticks = 0

    def receive_message(self, message: Dict[str, Any]):
        self.message_queue.append(message)

    def link_neighbor(self, neighbor_id: str):
        if neighbor_id not in self.neighbors:
            self.neighbors.append(neighbor_id)

    def save_memory(self):
        """Saves current state to history memory (capped at 50 steps)."""
        snapshot = {
            "state": dict(self.state),
            "metrics": dict(self.metrics)
        }
        self.memory.append(snapshot)
        if len(self.memory) > 50:
            self.memory.pop(0)

    def step(self, neighbors_by_id: Dict[str, 'WorldAgent']) -> List[Dict[str, Any]]:
        """
        Executes one timestep of the local transition model.
        Returns a list of outbound messages to be delivered.
        """
        self.total_ticks += 1
        self.save_memory()
        
        outbound_messages = []
        
        # 1. Random breakdown check based on failure probability
        if self.state["status"] != "broken":
            if random.random() < self.state.get("failure_prob", 0.01):
                self.state["status"] = "broken"
                self.metrics["failures"] += 1
                
        # 2. Recovery check if broken
        if self.state["status"] == "broken":
            # 15% chance of self-repair per step
            if random.random() < 0.15:
                self.state["status"] = "active" if self.type != "robot" else "idle"
            else:
                # If broken, increase average delay and do not process anything
                self.metrics["avg_delay"] += 1.0
                return []

        # 3. Process type-specific behaviors (local models)
        if self.type == "robot":
            outbound_messages = self._step_robot(neighbors_by_id)
        elif self.type == "worker":
            outbound_messages = self._step_worker(neighbors_by_id)
        elif self.type == "dock":
            outbound_messages = self._step_dock(neighbors_by_id)
        elif self.type == "shelf":
            outbound_messages = self._step_shelf(neighbors_by_id)
        else:
            # Generic node behavior
            outbound_messages = self._step_generic(neighbors_by_id)

        # 4. Calculate Utilization
        if self.state["status"] in ["busy", "moving", "loading", "unloading"]:
            self.active_ticks += 1
        self.metrics["utilization"] = round(self.active_ticks / self.total_ticks, 2)
        
        # 5. Clear read messages
        self.message_queue.clear()
        
        return outbound_messages

    def _step_robot(self, neighbors_by_id: Dict[str, 'WorldAgent']) -> List[Dict[str, Any]]:
        outbound = []
        status = self.state["status"]
        battery = self.state.get("battery", 100)
        
        # Battery depletion
        if status in ["moving", "loading", "unloading"]:
            battery = max(0, battery - 2)
        else:
            battery = max(0, battery - 0.5)
        self.state["battery"] = battery

        # Low battery overrides behavior
        if battery < 15 and status not in ["charging", "broken"]:
            self.state["status"] = "charging"
            self.state["current_target"] = None
            self.state["progress"] = 0
            
        if self.state["status"] == "charging":
            # Charge up
            battery = min(100, battery + 15)
            self.state["battery"] = battery
            if battery == 100:
                self.state["status"] = "idle"
            return []

        # Read orders / incoming work requests
        inbound_orders = [msg for msg in self.message_queue if msg.get("type") == "order_assignment"]

        if status == "idle":
            if inbound_orders:
                # Accept first assignment
                order = inbound_orders[0]
                self.state["status"] = "moving"
                self.state["current_target"] = order["target_node"]
                self.state["progress"] = 0
                self.state["load"] = 1.0 # Carrying work
            elif battery < 40:
                # Proactively go charge if idle and medium battery
                self.state["status"] = "charging"
                
        elif status == "moving":
            # Advance progress towards target
            progress = self.state.get("progress", 0) + 20 # 5 steps to reach target
            self.state["progress"] = progress
            
            if progress >= 100:
                target_id = self.state["current_target"]
                self.state["progress"] = 0
                
                # Check if target is a shelf or a dock
                target_agent = neighbors_by_id.get(target_id)
                if target_agent:
                    if target_agent.type == "shelf":
                        # Deliver/pick from shelf
                        self.state["status"] = "unloading"
                        outbound.append({
                            "type": "deposit_item",
                            "source": self.id,
                            "target": target_id,
                            "count": 1
                        })
                    elif target_agent.type == "dock":
                        # Deliver to outbound dock
                        self.state["status"] = "unloading"
                        outbound.append({
                            "type": "ship_item",
                            "source": self.id,
                            "target": target_id,
                            "count": 1
                        })
                else:
                    # Target missing, return to idle
                    self.state["status"] = "idle"
                    self.state["load"] = 0.0
                    self.state["current_target"] = None
                    
        elif status == "unloading":
            # Action completes, return to idle
            self.state["status"] = "idle"
            self.state["load"] = 0.0
            self.state["current_target"] = None
            self.metrics["processed_items"] += 1
            
        return outbound

    def _step_worker(self, neighbors_by_id: Dict[str, 'WorldAgent']) -> List[Dict[str, Any]]:
        outbound = []
        
        # Check messages for materials to process
        materials = [msg for msg in self.message_queue if msg.get("type") in ["deposit_item", "material_transfer"]]
        
        # Increment queue by materials received
        for m in materials:
            self.state["queue_size"] = min(self.state["capacity"], self.state["queue_size"] + m.get("count", 1))
            
        if self.state["status"] == "active" and self.state["queue_size"] > 0:
            # Transition to busy processing
            self.state["status"] = "busy"
            self.state["load"] = 0.5
            
        elif self.state["status"] == "busy":
            # Complete processing of one item
            self.state["queue_size"] = max(0, self.state["queue_size"] - 1)
            self.metrics["processed_items"] += 1
            
            # Send processed items downstream
            downstream = [n for n in self.neighbors if neighbors_by_id.get(n) and neighbors_by_id[n].type in ["dock", "shelf", "station"]]
            if downstream:
                target_id = random.choice(downstream)
                outbound.append({
                    "type": "deposit_item" if neighbors_by_id[target_id].type == "shelf" else "ship_item",
                    "source": self.id,
                    "target": target_id,
                    "count": 1
                })
                
            self.state["status"] = "active"
            self.state["load"] = 0.0
            
        return outbound

    def _step_dock(self, neighbors_by_id: Dict[str, 'WorldAgent']) -> List[Dict[str, Any]]:
        outbound = []
        
        # Inbound docks periodically spawn loads and assign them to robots
        # Outbound docks collect items and ship them
        if self.id == "dock_inbound" or "inflow" in self.id or "inbound" in self.id:
            # Spawn incoming shipments periodically
            if random.random() < 0.6:
                self.state["queue_size"] = min(self.state["capacity"], self.state["queue_size"] + random.randint(1, 3))
                
            # Assign load to robots
            idle_robots = [n for n in self.neighbors if neighbors_by_id.get(n) and neighbors_by_id[n].type == "robot" and neighbors_by_id[n].state["status"] == "idle"]
            shelves = [n.id for n in neighbors_by_id.values() if n.type == "shelf"]
            
            while self.state["queue_size"] > 0 and idle_robots and shelves:
                robot_id = idle_robots.pop(0)
                shelf_id = random.choice(shelves)
                self.state["queue_size"] -= 1
                self.metrics["processed_items"] += 1
                
                outbound.append({
                    "type": "order_assignment",
                    "source": self.id,
                    "target": robot_id,
                    "target_node": shelf_id
                })
        else:
            # Outbound dock collects items and clears them
            shipments = [msg for msg in self.message_queue if msg.get("type") in ["ship_item", "deposit_item"]]
            self.state["queue_size"] = min(self.state["capacity"], self.state["queue_size"] + len(shipments))
            
            # Shipping processing
            if self.state["queue_size"] > 0:
                ship_count = min(self.state["queue_size"], 2) # can ship 2 items per tick
                self.state["queue_size"] -= ship_count
                self.metrics["processed_items"] += ship_count
                
        # Calculate load ratio
        self.state["load"] = round(self.state["queue_size"] / max(1, self.state["capacity"]), 2)
        return outbound

    def _step_shelf(self, neighbors_by_id: Dict[str, 'WorldAgent']) -> List[Dict[str, Any]]:
        outbound = []
        
        # Shelf receives packages from robots, stores them, and feeds picking workers
        deposits = [msg for msg in self.message_queue if msg.get("type") == "deposit_item"]
        self.state["queue_size"] = min(self.state["capacity"], self.state["queue_size"] + sum(d.get("count", 1) for d in deposits))
        
        # Feed workers if shelf has inventory
        if self.state["queue_size"] > 0:
            workers = [n for n in self.neighbors if neighbors_by_id.get(n) and neighbors_by_id[n].type == "worker" and neighbors_by_id[n].state["status"] == "active"]
            if workers:
                worker_id = random.choice(workers)
                self.state["queue_size"] -= 1
                self.metrics["processed_items"] += 1
                outbound.append({
                    "type": "material_transfer",
                    "source": self.id,
                    "target": worker_id,
                    "count": 1
                })
                
        self.state["load"] = round(self.state["queue_size"] / max(1, self.state["capacity"]), 2)
        return outbound

    def _step_generic(self, neighbors_by_id: Dict[str, 'WorldAgent']) -> List[Dict[str, Any]]:
        # For non-specific custom types, simple transfer logic
        outbound = []
        deposits = [msg for msg in self.message_queue if msg.get("type") in ["deposit_item", "material_transfer"]]
        self.state["queue_size"] = min(self.state["capacity"], self.state["queue_size"] + len(deposits))
        
        if self.state["queue_size"] > 0 and random.random() < 0.5:
            # Route downstream
            downstream = [n for n in self.neighbors if neighbors_by_id.get(n)]
            if downstream:
                target_id = random.choice(downstream)
                self.state["queue_size"] -= 1
                self.metrics["processed_items"] += 1
                outbound.append({
                    "type": "material_transfer",
                    "source": self.id,
                    "target": target_id,
                    "count": 1
                })
        
        self.state["load"] = round(self.state["queue_size"] / max(1, self.state["capacity"]), 2)
        return outbound
