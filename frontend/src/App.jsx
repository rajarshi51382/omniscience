import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactFlow, { 
  MiniMap, 
  Controls, 
  Background, 
  Handle, 
  Position,
  useNodesState,
  useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import { 
  Play, 
  Pause, 
  SkipForward, 
  RotateCcw, 
  HelpCircle, 
  Cpu, 
  Database, 
  Activity, 
  AlertTriangle, 
  RefreshCw, 
  ArrowLeft, 
  Send,
  Zap,
  TrendingDown,
  TrendingUp,
  LineChart
} from 'lucide-react';

// Custom React Flow node components to render agent stats
const CustomNode = ({ data }) => {
  const { label, type, state, metrics } = data;
  const status = state?.status || 'active';
  const isBroken = status === 'broken';
  const isCharging = status === 'charging';
  const isBusy = status === 'busy' || status === 'moving' || status === 'unloading' || status === 'loading';
  
  // Assign border/glow styling based on status and node types
  let cardClass = "border-cyan-500/20 text-cyan-400 bg-dark-900/90 shadow-glow";
  
  if (isBroken) {
    cardClass = "border-red-500/60 text-red-400 bg-red-950/20 shadow-glow-magenta animate-pulse";
  } else if (isCharging) {
    cardClass = "border-yellow-500/40 text-yellow-400 bg-yellow-950/10 shadow-glow-purple";
  } else if (type === 'robot') {
    cardClass = isBusy 
      ? "border-purple-500/40 text-purple-400 bg-purple-950/10 shadow-glow-purple" 
      : "border-purple-500/20 text-purple-300 bg-dark-900/90";
  } else if (type === 'worker') {
    cardClass = isBusy 
      ? "border-green-500/40 text-green-400 bg-green-950/10 shadow-glow-green" 
      : "border-green-500/20 text-green-300 bg-dark-900/90";
  } else if (type === 'dock') {
    cardClass = "border-yellow-500/30 text-yellow-400 bg-dark-900/90 shadow-glow-magenta";
  }

  return (
    <div className={`px-4 py-3 rounded-xl border glass-panel transition-all duration-300 w-56 ${cardClass}`}>
      <Handle type="target" position={Position.Top} className="opacity-0 group-hover:opacity-100" />
      
      <div className="flex items-center justify-between mb-1 text-[10px] font-mono tracking-wider opacity-60 uppercase">
        <span>{type}</span>
        <div className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${isBroken ? 'bg-red-500' : isCharging ? 'bg-yellow-500' : 'bg-cyber-cyan'}`} />
          <span>{status}</span>
        </div>
      </div>
      
      <div className="font-bold text-xs text-gray-100 truncate">{label}</div>
      
      <div className="mt-2 pt-1.5 border-t border-white/5 text-[10px] space-y-1 font-mono text-gray-400">
        {state?.battery !== undefined && (
          <div className="flex justify-between">
            <span>Battery:</span> 
            <span className={state.battery < 30 ? "text-red-400 font-bold" : "text-gray-200"}>
              {Math.round(state.battery)}%
            </span>
          </div>
        )}
        {state?.queue_size !== undefined && (
          <div className="flex justify-between">
            <span>Queue:</span> 
            <span className="text-gray-200">{state.queue_size}</span>
          </div>
        )}
        {state?.load !== undefined && (
          <div className="flex justify-between">
            <span>Load Factor:</span> 
            <span className="text-gray-200">{Math.round(state.load * 100)}%</span>
          </div>
        )}
        {metrics?.processed_items !== undefined && (
          <div className="flex justify-between text-[9px] opacity-70 mt-1">
            <span>Processed:</span> 
            <span>{metrics.processed_items}</span>
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="opacity-0 group-hover:opacity-100" />
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

const EXAMPLES = [
  "Warehouse with 15 robots, 300 shelves, 2 docks, and holiday demand.",
  "Smart factory assembly line with welding, painting, assembly stations, and QC booth.",
  "Drone delivery network in downtown with 8 quadcopters, 2 launch pads, and battery recharge bases.",
  "Traffic intersection with 4 adaptive lanes and transit priority sensor loops.",
  "Hospital emergency room triage workflow with 1 triage desk, 5 ICU beds, and lab testing."
];

export default function App() {
  const [screen, setScreen] = useState('landing'); // 'landing' | 'compiling' | 'dashboard'
  const [prompt, setPrompt] = useState('');
  const [compileStatus, setCompileStatus] = useState([]);
  const [activeStep, setActiveStep] = useState(0);
  
  // Simulation states
  const [simulationData, setSimulationData] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1); // 1 = normal, 2 = fast, 3 = super fast
  const [logs, setLogs] = useState([]);
  
  // Prediction / Chat states
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [isQuerying, setIsQuerying] = useState(false);
  const [selectedReport, setSelectedReport] = useState(null);
  
  const simInterval = useRef(null);
  const prevNodesRef = useRef({});

  // Layout engine: arranges nodes in horizontal process layers
  const layoutGraph = useCallback((backendNodes, backendEdges) => {
    const colGroups = [[], [], [], [], []]; // 5 columns
    
    const getColIndex = (type, label) => {
      const lbl = label.toLowerCase();
      if (lbl.includes('inbound') || lbl.includes('inflow') || lbl.includes('triage') || lbl.includes('lane_north') || lbl.includes('lane_south') || lbl.includes('lane_east') || lbl.includes('lane_west')) return 0;
      if (type === 'robot' || type === 'drone' || type === 'vehicle' || lbl.includes('waiting')) return 1;
      if (type === 'shelf' || type === 'storage' || type === 'rack' || type === 'exam_bay') return 2;
      if (type === 'worker' || type === 'station' || type === 'lab') return 3;
      if (lbl.includes('outbound') || lbl.includes('exit') || type === 'dock' || lbl.includes('discharge') || lbl.includes('ward')) return 4;
      return 2; // default
    };

    backendNodes.forEach(node => {
      const col = getColIndex(node.type, node.label);
      colGroups[col].push(node);
    });

    const newNodes = [];
    const colSpacing = 280;
    const rowSpacing = 130;

    colGroups.forEach((group, colIdx) => {
      const totalHeight = (group.length - 1) * rowSpacing;
      group.forEach((node, rowIdx) => {
        const x = 40 + colIdx * colSpacing;
        const y = 280 + (rowIdx * rowSpacing) - (totalHeight / 2);
        newNodes.push({
          id: node.id,
          type: 'custom',
          data: node,
          position: { x, y }
        });
      });
    });

    const newEdges = backendEdges.map((e, idx) => ({
      id: `edge_${idx}`,
      source: e.source,
      target: e.target,
      label: e.label?.replace(/_/g, ' '),
      animated: isPlaying,
      className: isPlaying ? 'active' : '',
      style: { stroke: '#28283a', strokeWidth: 1.5 }
    }));

    setNodes(newNodes);
    setEdges(newEdges);
  }, [isPlaying, setNodes, setEdges]);

  // Handle world generation
  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    
    // Set screen to compiling and run stage animations
    setScreen('compiling');
    setCompileStatus([]);
    
    const stages = [
      "Compiling System Description...",
      "Creating Component Models...",
      "Building Interaction Graph...",
      "Synthesizing Agent Behaviors...",
      "Instantiating Time Step Engine..."
    ];

    for (let i = 0; i < stages.length; i++) {
      setCompileStatus(prev => [...prev, stages[i]]);
      await new Promise(r => setTimeout(r, 600));
    }

    try {
      const response = await fetch('/api/compile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      
      if (!response.ok) throw new Error('Compilation failed');
      const data = await response.json();
      
      setSimulationData(data);
      layoutGraph(data.nodes, data.edges);
      
      // Clear previous logs
      setLogs([`System compiled: "${data.title}" successfully instantiated.`]);
      setChatHistory([]);
      setSelectedReport(null);
      
      setScreen('dashboard');
    } catch (err) {
      console.error(err);
      setScreen('landing');
      alert('Error compiling world. Please check your backend connection.');
    }
  };

  // Run single simulation tick
  const stepSimulation = async (ticksCount = 1) => {
    try {
      const response = await fetch('/api/simulate/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps: ticksCount })
      });
      if (!response.ok) throw new Error('Stepping failed');
      const data = await response.json();
      
      setSimulationData(data);
      layoutGraph(data.nodes, data.edges);
      
      // Generate live event logs by observing differences
      const newLogs = [];
      data.nodes.forEach(node => {
        const prev = prevNodesRef.current[node.id];
        if (prev) {
          if (node.state.status === 'broken' && prev.state.status !== 'broken') {
            newLogs.push(`⚠️ ALERT: ${node.label} breakdown! Systems halting.`);
          }
          if (node.state.status === 'charging' && prev.state.status !== 'charging') {
            newLogs.push(`⚡ Battery low: ${node.label} entering charging dock.`);
          }
          if (node.state.status === 'idle' && prev.state.status === 'charging') {
            newLogs.push(`✅ ${node.label} fully charged. Re-entering queue.`);
          }
          if (node.metrics.processed_items > prev.metrics.processed_items) {
            const diff = node.metrics.processed_items - prev.metrics.processed_items;
            newLogs.push(`⚙️ ${node.label} completed ${diff} load cycles.`);
          }
        }
        // Save current for next compare
        prevNodesRef.current[node.id] = JSON.parse(JSON.stringify(node));
      });
      
      if (newLogs.length > 0) {
        setLogs(prev => [...newLogs.reverse(), ...prev].slice(0, 100));
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Autoplay logic
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = speed === 3 ? 200 : speed === 2 ? 500 : 1000;
      simInterval.current = setInterval(() => {
        stepSimulation(1);
      }, intervalMs);
    } else {
      if (simInterval.current) clearInterval(simInterval.current);
    }
    return () => {
      if (simInterval.current) clearInterval(simInterval.current);
    };
  }, [isPlaying, speed]);

  // Reset Simulation
  const handleReset = async () => {
    try {
      const response = await fetch('/api/simulate/reset', { method: 'POST' });
      if (!response.ok) throw new Error('Reset failed');
      const data = await response.json();
      setSimulationData(data);
      layoutGraph(data.nodes, data.edges);
      setLogs([`Simulation reset to initial step.`]);
      setSelectedReport(null);
      prevNodesRef.current = {};
    } catch (err) {
      console.error(err);
    }
  };

  // Submit NL Chat query (What-if / prediction)
  const handleChatSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!chatInput.trim()) return;
    
    const userQuery = chatInput;
    setChatInput('');
    setChatHistory(prev => [...prev, { sender: 'user', text: userQuery }]);
    setIsQuerying(true);
    
    try {
      const response = await fetch('/api/simulate/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userQuery })
      });
      if (!response.ok) throw new Error('Query prediction failed');
      const report = await response.json();
      
      setChatHistory(prev => [...prev, { 
        sender: 'ai', 
        text: report.explanation,
        report: report
      }]);
      setSelectedReport(report);
    } catch (err) {
      console.error(err);
      setChatHistory(prev => [...prev, { 
        sender: 'ai', 
        text: "Error compiling prediction branches. Make sure the system is loaded correctly." 
      }]);
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="min-h-screen text-gray-100 flex flex-col relative overflow-hidden bg-grid-cyber bg-dark-950">
      
      {/* BACKGROUND SHADOW BLURS */}
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-cyber-cyan/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-cyber-magenta/5 rounded-full blur-[100px] pointer-events-none" />

      {/* HEADER BAR */}
      <header className="px-6 py-4 border-b border-white/5 glass-panel flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-cyan-950/50 border border-cyber-cyan/30 text-cyber-cyan shadow-glow">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-wider flex items-center gap-1.5">
              OMNISCIENCE <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded font-mono text-gray-400 uppercase">v0.1</span>
            </h1>
            <p className="text-[10px] text-gray-400">Executable Agentic World Models</p>
          </div>
        </div>

        {screen === 'dashboard' && simulationData && (
          <div className="flex items-center gap-4 bg-dark-900/60 px-4 py-2 rounded-xl border border-white/5">
            <span className="text-xs text-gray-400 font-mono">World:</span>
            <span className="text-xs font-semibold text-cyber-cyan truncate max-w-[200px]">{simulationData.title}</span>
            <span className="h-4 w-px bg-white/10" />
            <span className="text-xs text-gray-400 font-mono">Time:</span>
            <span className="text-xs font-semibold text-gray-200">T = {simulationData.timestep}</span>
          </div>
        )}

        {screen === 'dashboard' && (
          <button 
            onClick={() => { setIsPlaying(false); setScreen('landing'); }}
            className="flex items-center gap-2 text-xs text-gray-400 hover:text-white transition bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg border border-white/5"
          >
            <ArrowLeft className="w-4 h-4" /> Change Model
          </button>
        )}
      </header>

      {/* MAIN CONTAINER */}
      <main className="flex-1 flex overflow-hidden">
        
        {/* SCREEN 1: LANDING */}
        {screen === 'landing' && (
          <div className="max-w-3xl mx-auto flex flex-col justify-center items-center px-6 py-20 text-center z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-gray-400 mb-6">
              <Zap className="w-3.5 h-3.5 text-cyber-cyan shadow-glow" /> Predict system futures automatically
            </div>
            
            <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4">
              Build a world model.<br/>
              <span className="bg-gradient-to-r from-cyber-cyan via-cyber-purple to-cyber-magenta bg-clip-text text-transparent">
                Predict the future.
              </span>
            </h2>
            
            <p className="text-gray-400 text-sm max-w-lg mb-10 leading-relaxed">
              Describe any physical system, machinery layout, or workflow. 
              Omniscience compiles it into a network of cooperating agent models to forecast metrics and analyze failures.
            </p>

            {/* Prompt form */}
            <div className="w-full glass-panel p-6 rounded-2xl border border-white/10 shadow-lg text-left mb-8">
              <label className="block text-xs font-mono tracking-wider opacity-60 uppercase mb-2">System Description</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="E.g., A warehouse with 15 robots, 300 shelves, and 2 docks. Orders increase by 40%..."
                className="w-full h-32 bg-dark-950/80 border border-white/10 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-cyber-cyan/50 text-gray-200 resize-none font-sans"
              />
              <div className="flex justify-between items-center mt-4">
                <span className="text-[10px] text-gray-500 font-mono">MVP Compiler v0.1</span>
                <button
                  onClick={handleGenerate}
                  disabled={!prompt.trim()}
                  className="px-5 py-2.5 rounded-xl bg-cyber-cyan text-dark-950 font-bold text-sm hover:brightness-110 active:scale-95 transition disabled:opacity-50 disabled:pointer-events-none flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4 animate-spin-slow" /> Generate World
                </button>
              </div>
            </div>

            {/* Examples list */}
            <div className="w-full text-left">
              <h3 className="text-xs font-mono tracking-wider opacity-60 uppercase mb-3">Quick Reference Presets</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {EXAMPLES.map((ex, idx) => (
                  <button
                    key={idx}
                    onClick={() => setPrompt(ex)}
                    className="p-3 text-left rounded-xl bg-white/5 border border-white/5 text-xs text-gray-400 hover:text-white hover:bg-white/10 hover:border-white/10 transition-all truncate"
                  >
                    💡 {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SCREEN 2: COMPILING */}
        {screen === 'compiling' && (
          <div className="flex-1 flex flex-col justify-center items-center z-10">
            <div className="relative mb-8">
              <div className="w-20 h-20 rounded-full border-2 border-cyber-cyan/20 border-t-cyber-cyan animate-spin" />
              <Cpu className="w-8 h-8 text-cyber-cyan absolute top-6 left-6 animate-pulse" />
            </div>
            <h3 className="font-bold text-lg mb-4 tracking-wider">OMNISCIENCE COMPILING WORLD</h3>
            <div className="w-80 space-y-2.5 font-mono text-xs text-gray-400">
              {compileStatus.map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 text-cyber-cyan">
                  <span className="text-cyber-green">✔</span> {step}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SCREEN 3: DASHBOARD */}
        {screen === 'dashboard' && simulationData && (
          <div className="flex-1 flex overflow-hidden">
            
            {/* SIDEBAR LEFT: METRICS & EVENT STREAM */}
            <aside className="w-80 border-r border-white/5 glass-panel flex flex-col z-10">
              
              {/* TIMESTEP CONTROLLER PANEL */}
              <div className="p-4 border-b border-white/5 bg-dark-900/40">
                <div className="flex items-center justify-between mb-3.5">
                  <span className="text-xs font-mono tracking-wider opacity-60 uppercase">Simulation Engine</span>
                  <span className="text-[10px] bg-cyber-green/10 text-cyber-green px-2 py-0.5 rounded font-mono">RUNNING</span>
                </div>
                <div className="flex gap-2">
                  <button 
                    onClick={() => setIsPlaying(!isPlaying)}
                    className={`flex-1 py-2 px-3 rounded-lg border font-bold text-xs flex items-center justify-center gap-2 transition ${
                      isPlaying 
                        ? 'border-yellow-500/30 text-yellow-400 bg-yellow-950/10' 
                        : 'border-cyber-cyan/30 text-cyber-cyan bg-cyan-950/10'
                    }`}
                  >
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    {isPlaying ? 'Pause' : 'Play'}
                  </button>
                  <button 
                    onClick={() => stepSimulation(1)}
                    disabled={isPlaying}
                    className="p-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 disabled:opacity-50 text-gray-300"
                    title="Step Forward"
                  >
                    <SkipForward className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={handleReset}
                    className="p-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-gray-300"
                    title="Reset simulation"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                </div>
                
                {/* Speed Controls */}
                <div className="flex justify-between items-center mt-3 text-[10px] font-mono text-gray-400">
                  <span>Playback Speed:</span>
                  <div className="flex gap-1.5">
                    {[1, 2, 3].map((s) => (
                      <button
                        key={s}
                        onClick={() => setSpeed(s)}
                        className={`px-2 py-0.5 rounded ${speed === s ? 'bg-cyber-cyan text-dark-950 font-bold' : 'bg-white/5'}`}
                      >
                        {s}x
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* CORE METRICS */}
              <div className="p-4 border-b border-white/5 space-y-4">
                <h3 className="text-xs font-mono tracking-wider opacity-60 uppercase mb-1">Live Metrics</h3>
                
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-dark-900/50 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-gray-400 font-mono mb-1">Throughput</div>
                    <div className="text-lg font-bold text-gray-100 flex items-baseline gap-1">
                      {simulationData.metrics.throughput}
                      <span className="text-[9px] font-normal opacity-50">items/t</span>
                    </div>
                  </div>
                  <div className="bg-dark-900/50 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-gray-400 font-mono mb-1">Avg Utilization</div>
                    <div className="text-lg font-bold text-gray-100">
                      {Math.round(simulationData.metrics.avg_utilization * 100)}%
                    </div>
                  </div>
                  <div className="bg-dark-900/50 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-gray-400 font-mono mb-1">Queue Delay</div>
                    <div className="text-lg font-bold text-gray-100 flex items-baseline gap-1">
                      {simulationData.metrics.avg_delay}
                      <span className="text-[9px] font-normal opacity-50">ticks</span>
                    </div>
                  </div>
                  <div className="bg-dark-900/50 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-gray-400 font-mono mb-1">Fail Prob</div>
                    <div className="text-lg font-bold text-red-400">
                      {simulationData.metrics.failure_probability}
                    </div>
                  </div>
                </div>

                {/* Bottleneck Alerts */}
                {simulationData.analysis.bottleneck !== 'None' && (
                  <div className="p-3 rounded-xl bg-red-950/10 border border-red-500/20 text-xs flex gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
                    <div>
                      <div className="font-bold text-red-400">Bottleneck: {simulationData.analysis.bottleneck}</div>
                      <div className="text-[10px] text-gray-400">{simulationData.analysis.bottleneck_reason}</div>
                    </div>
                  </div>
                )}
              </div>

              {/* LIVE AGENT ACTIVITY LOG STREAM */}
              <div className="flex-1 flex flex-col min-h-0">
                <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between shrink-0">
                  <span className="text-xs font-mono tracking-wider opacity-60 uppercase">Live Event Stream</span>
                  <Activity className="w-3.5 h-3.5 text-cyber-cyan animate-pulse" />
                </div>
                <div className="flex-1 overflow-y-auto px-4 py-2 font-mono text-[10px] space-y-2 text-gray-400">
                  {logs.map((log, index) => (
                    <div key={index} className="border-l-2 border-white/5 pl-2 py-0.5 hover:bg-white/5 transition-colors">
                      {log}
                    </div>
                  ))}
                  {logs.length === 0 && (
                    <div className="text-gray-600 italic text-center mt-10">Waiting for simulation events...</div>
                  )}
                </div>
              </div>
            </aside>

            {/* CENTER PANEL: NETWORK CANVAS (REACT FLOW) */}
            <section className="flex-1 flex flex-col relative bg-dark-950/40">
              <div className="absolute top-4 left-4 z-10 bg-dark-900/80 px-3 py-1.5 rounded-lg border border-white/5 text-[10px] font-mono text-gray-400 flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-cyber-cyan" /> Drag nodes to adjust spatial model layout.
              </div>
              
              <div className="flex-1 min-h-0">
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  nodeTypes={nodeTypes}
                  fitView
                >
                  <Background color="#00f0ff" gap={20} size={0.7} opacity={0.1} />
                  <Controls className="bg-dark-900 border border-white/10 text-white fill-current" />
                  <MiniMap 
                    nodeColor={() => 'rgba(0, 240, 255, 0.1)'} 
                    maskColor="rgba(5, 5, 8, 0.7)" 
                    className="bg-dark-900/80 border border-white/10" 
                  />
                </ReactFlow>
              </div>
            </section>

            {/* SIDEBAR RIGHT: NLP WHAT-IF TERMINAL & FORECAST COMPACT REPORTS */}
            <aside className="w-96 border-l border-white/5 glass-panel flex flex-col z-10">
              
              {/* CHAT INPUT TERMINAL */}
              <div className="p-4 border-b border-white/5">
                <h3 className="text-xs font-mono tracking-wider opacity-60 uppercase mb-3">Ask Omniscience</h3>
                <form onSubmit={handleChatSubmit} className="flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="E.g., What if robot 7 breaks?"
                    className="flex-1 bg-dark-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-cyber-cyan/50 text-gray-200"
                  />
                  <button
                    type="submit"
                    disabled={isQuerying || !chatInput.trim()}
                    className="p-2 rounded-xl bg-cyber-cyan text-dark-950 font-bold hover:brightness-110 transition disabled:opacity-50"
                  >
                    {isQuerying ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </button>
                </form>
                
                {/* Suggestions */}
                <div className="flex flex-wrap gap-1.5 mt-3">
                  <button 
                    onClick={() => { setChatInput("What if robot 2 breaks?"); }}
                    className="text-[9px] font-mono bg-white/5 hover:bg-white/10 text-gray-400 px-2 py-0.5 rounded border border-white/5 transition"
                  >
                    ⚡ Robot 2 Breaks
                  </button>
                  <button 
                    onClick={() => { setChatInput("What if demand doubles?"); }}
                    className="text-[9px] font-mono bg-white/5 hover:bg-white/10 text-gray-400 px-2 py-0.5 rounded border border-white/5 transition"
                  >
                    📈 Demand Doubles
                  </button>
                  <button 
                    onClick={() => { setChatInput("What's the bottleneck?"); }}
                    className="text-[9px] font-mono bg-white/5 hover:bg-white/10 text-gray-400 px-2 py-0.5 rounded border border-white/5 transition"
                  >
                    🔍 Bottleneck
                  </button>
                </div>
              </div>

              {/* LIVE CHAT INTERFACE STREAM */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {chatHistory.map((chat, idx) => (
                  <div key={idx} className={`flex flex-col ${chat.sender === 'user' ? 'items-end' : 'items-start'}`}>
                    <span className="text-[9px] font-mono text-gray-500 mb-1">
                      {chat.sender === 'user' ? 'You' : 'Omniscience AI'}
                    </span>
                    <div className={`p-3 rounded-2xl max-w-[90%] text-xs leading-relaxed ${
                      chat.sender === 'user' 
                        ? 'bg-cyber-cyan/15 text-cyber-cyan border border-cyber-cyan/20 rounded-tr-none' 
                        : 'bg-dark-900 border border-white/5 rounded-tl-none text-gray-300'
                    }`}>
                      {chat.text}
                      
                      {/* Interactive click to view report */}
                      {chat.report && (
                        <button
                          onClick={() => setSelectedReport(chat.report)}
                          className="mt-2 text-[10px] font-semibold text-cyber-magenta hover:underline flex items-center gap-1"
                        >
                          <LineChart className="w-3.5 h-3.5" /> View Branch Report
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                
                {chatHistory.length === 0 && (
                  <div className="text-gray-600 italic text-center mt-10 text-xs">
                    Interrogate the simulation model. Ask what-if questions or run optimization inquiries.
                  </div>
                )}
                
                {isQuerying && (
                  <div className="flex items-center gap-2 text-xs text-cyber-cyan font-mono">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Compiling predictive branches...
                  </div>
                )}
              </div>

              {/* REPORT DISPLAY MODAL / COMPONENT AT BOTTOM OF SIDEBAR */}
              {selectedReport && (
                <div className="p-4 border-t border-white/5 bg-dark-900/70 glass-panel animate-in fade-in slide-in-from-bottom duration-300">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-cyber-magenta font-mono uppercase tracking-wider">Branch Forecast Summary</span>
                    <button 
                      onClick={() => setSelectedReport(null)}
                      className="text-[10px] text-gray-500 hover:text-gray-300"
                    >
                      Dismiss
                    </button>
                  </div>
                  
                  {/* METRIC DIFFERENCES COMPARE TABLE */}
                  <div className="space-y-2 mb-3">
                    <div className="grid grid-cols-3 text-[9px] font-mono text-gray-500 pb-1 border-b border-white/5">
                      <span>METRIC</span>
                      <span className="text-right">BASELINE</span>
                      <span className="text-right">PREDICTED</span>
                    </div>
                    
                    <div className="grid grid-cols-3 text-xs font-mono">
                      <span className="text-gray-400">Throughput</span>
                      <span className="text-right text-gray-300">{selectedReport.metrics_comparison.baseline.throughput}</span>
                      <span className={`text-right font-bold ${
                        parseFloat(selectedReport.metrics_comparison.differences.throughput_pct) < 0 ? 'text-red-400' : 'text-green-400'
                      }`}>
                        {selectedReport.metrics_comparison.predicted.throughput} ({selectedReport.metrics_comparison.differences.throughput_pct})
                      </span>
                    </div>

                    <div className="grid grid-cols-3 text-xs font-mono">
                      <span className="text-gray-400">Queue Delay</span>
                      <span className="text-right text-gray-300">{selectedReport.metrics_comparison.baseline.avg_delay}t</span>
                      <span className={`text-right font-bold ${
                        parseFloat(selectedReport.metrics_comparison.differences.delay_pct) > 0 ? 'text-red-400' : 'text-green-400'
                      }`}>
                        {selectedReport.metrics_comparison.predicted.avg_delay}t ({selectedReport.metrics_comparison.differences.delay_pct})
                      </span>
                    </div>

                    <div className="grid grid-cols-3 text-xs font-mono">
                      <span className="text-gray-400">Fail Prob</span>
                      <span className="text-right text-gray-300">{selectedReport.metrics_comparison.baseline.failures > 0 ? 'Elevated' : '0%'}</span>
                      <span className="text-right font-bold text-red-400">
                        {selectedReport.failure_probability}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-white/5 text-[11px] space-y-1.5">
                    <div>
                      <span className="font-bold text-gray-300">Bottleneck:</span>{' '}
                      <span className="text-yellow-400 font-mono">{selectedReport.predicted_bottleneck}</span>{' '}
                      <span className="text-gray-500 font-mono">({selectedReport.predicted_bottleneck_reason})</span>
                    </div>
                    <div className="bg-white/5 p-2 rounded-lg border border-white/5 text-gray-300 text-[10.5px]">
                      <span className="font-bold text-cyber-cyan block mb-0.5">Recommendation:</span>
                      {selectedReport.recommendation}
                    </div>
                  </div>
                </div>
              )}
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
