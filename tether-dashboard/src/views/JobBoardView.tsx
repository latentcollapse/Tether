import React, { useState, useEffect } from 'react';
import { ReactFlow, Background, Controls, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { 
  ClipboardList, Plus, Play, Check, CheckCircle2, AlertTriangle, 
  HelpCircle, Filter, Activity, User, Shield, BookOpen, Layers,
  ChevronDown, ChevronUp, Trash2, Sparkles
} from 'lucide-react';
import { api } from '../api/client';
import { useAuthStore } from '../store/authStore';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

type Category = 'B' | 'F' | 'D' | 'G' | 'M' | 'R' | 'S';
type Tier = 'blue' | 'yellow' | 'orange' | 'red' | 'purple';
type Status = 'open' | 'active' | 'ready' | 'done' | 'proposed' | 'dormant';

interface Ticket {
  id: string;
  category: Category;
  tier: Tier;
  title: string;
  description: string;
  status: Status;
  owner: string;
  batch: string;
  principle: string[];
  bible_ref: string[];
  gate: string;
  blocks: string[];
  blocked_by: string[];
  work_done: string;
  implementers: string[];
}

export function JobBoardView() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'grid' | 'dag'>('grid');
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => ({ ...prev, [id]: !prev[id] }));
  };
  
  // Actor context
  const [actor, setActor] = useState<string>('matt');
  
  // Filters
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [filterTier, setFilterTier] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterOwner, setFilterOwner] = useState<string>('');
  
  // Dialogs
  const [showPropose, setShowPropose] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showFlagModal, setShowFlagModal] = useState<Ticket | null>(null);
  
  // Form States
  const [proposeForm, setProposeForm] = useState({ category: 'D', tier: 'blue', title: '', description: '' });
  const [createForm, setCreateForm] = useState({
    category: 'B', tier: 'blue', title: '', description: '', status: 'open', batch: '',
    principle: '', bible_ref: '', gate: '', blocks: '', blocked_by: ''
  });
  const [workDoneText, setWorkDoneText] = useState('');

  // Whiteboard / Scratchpad States
  const [whiteboardText, setWhiteboardText] = useState('');
  const [whiteboardSaving, setWhiteboardSaving] = useState(false);
  const [debounceTimer, setDebounceTimer] = useState<any>(null);

  useEffect(() => {
    api.getWhiteboard()
      .then(res => setWhiteboardText(res.content || ''))
      .catch(err => console.error("Failed to load whiteboard:", err));
  }, []);

  const saveWhiteboard = (newText: string) => {
    setWhiteboardSaving(true);
    api.updateWhiteboard(newText)
      .then(() => setWhiteboardSaving(false))
      .catch(err => {
        console.error("Failed to save whiteboard:", err);
        setWhiteboardSaving(false);
      });
  };

  const handleWhiteboardChange = (val: string) => {
    setWhiteboardText(val);
    if (debounceTimer) clearTimeout(debounceTimer);
    const timer = setTimeout(() => {
      saveWhiteboard(val);
    }, 1000);
    setDebounceTimer(timer);
  };

  const handleSynthesize = () => {
    const textarea = document.getElementById('whiteboard-textarea') as HTMLTextAreaElement;
    let selectedText = '';
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      if (start !== end) {
        selectedText = textarea.value.substring(start, end);
      }
    }
    if (!selectedText) {
      selectedText = whiteboardText;
    }
    
    setProposeForm({
      category: 'D',
      tier: 'blue',
      title: selectedText.split('\n')[0]?.substring(0, 50) || 'Synthesized Ticket',
      description: selectedText
    });
    setShowPropose(true);
  };

  // Fetch Tickets
  const fetchTickets = () => {
    setLoading(true);
    api.getTickets({
      category: filterCategory,
      tier: filterTier,
      status: filterStatus,
      owner: filterOwner,
    })
      .then(res => {
        setTickets(res.tickets as Ticket[]);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchTickets();
  }, [filterCategory, filterTier, filterStatus, filterOwner]);

  const handleClaim = async (id: string) => {
    try {
      await api.claimTicket(id, actor);
      fetchTickets();
    } catch (err) {
      alert("Claim failed: " + err);
    }
  };

  const handleFlag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showFlagModal || !workDoneText.trim()) return;
    try {
      await api.flagTicket(showFlagModal.id, actor, workDoneText);
      setShowFlagModal(null);
      setWorkDoneText('');
      fetchTickets();
    } catch (err) {
      alert("Flag failed: " + err);
    }
  };

  const handlePropose = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.proposeTicket(
        proposeForm.category,
        proposeForm.tier,
        proposeForm.title,
        proposeForm.description,
        actor
      );
      setShowPropose(false);
      setProposeForm({ category: 'D', tier: 'blue', title: '', description: '' });
      fetchTickets();
    } catch (err) {
      alert("Proposal failed: " + err);
    }
  };

  const handleAccept = async (id: string, tier?: string) => {
    try {
      await api.acceptTicket(id, actor, tier);
      fetchTickets();
    } catch (err) {
      alert("Accept failed: " + err);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const splitList = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean);
      await api.authorTicket({
        category: createForm.category,
        tier: createForm.tier,
        title: createForm.title,
        description: createForm.description,
        from_agent: actor,
        batch: createForm.batch || undefined,
        principle: splitList(createForm.principle),
        bible_ref: splitList(createForm.bible_ref),
        gate: createForm.gate || undefined,
        blocks: splitList(createForm.blocks),
        blocked_by: splitList(createForm.blocked_by)
      });
      setShowCreate(false);
      setCreateForm({
        category: 'B', tier: 'blue', title: '', description: '', status: 'open', batch: '',
        principle: '', bible_ref: '', gate: '', blocks: '', blocked_by: ''
      });
      fetchTickets();
    } catch (err) {
      alert("Authoring failed: " + err);
    }
  };

  const handleFinalize = async (id: string) => {
    try {
      const res = await api.finalizeTicket(id, actor);
      alert(`Ticket ${id} finalized!\nChangelog Handle: ${res.changelog_handle}`);
      fetchTickets();
    } catch (err) {
      alert("Finalize failed: " + err);
    }
  };

  const handleViewChangelog = async (id: string) => {
    try {
      const res = await api.getChangelog(id);
      if (res.changelog && res.changelog.length > 0) {
        const entry = res.changelog.find((c: any) => c.id === id);
        if (entry) {
          alert(`Changelog Entry for ${id}:\n` +
                `Title: ${entry.title}\n` +
                `Handle: ${entry.handle}\n` +
                `Completed By: @${entry.completed_by}\n` +
                `Completed At: ${new Date(entry.completed_at).toLocaleString()}\n\n` +
                `Proof of Work / Details:\n${entry.work_done}`);
        } else {
          alert(`Changelog entry not found for ticket ${id}`);
        }
      } else {
        alert(`Changelog entry not found for ticket ${id}`);
      }
    } catch (err) {
      alert(`Failed to fetch changelog: ${err}`);
    }
  };

  const handleDormant = async (id: string) => {
    try {
      await api.dormantTicket(id, actor);
      fetchTickets();
    } catch (err) {
      alert("Failed to make ticket dormant: " + err);
    }
  };

  const handleRevive = async (id: string) => {
    try {
      await api.reviveTicket(id, actor);
      fetchTickets();
    } catch (err) {
      alert("Failed to revive ticket: " + err);
    }
  };

  // Recharts Gate Status Data
  const gateTickets = tickets.filter(t => t.category === 'G' || t.gate);
  const gatesTotal = gateTickets.length;
  const gatesDone = gateTickets.filter(t => t.status === 'done').length;
  const gateProgressData = [
    { name: 'Gates Done', value: gatesDone },
    { name: 'Gates Remaining', value: Math.max(0, gatesTotal - gatesDone) }
  ];

  // DAG Layout Calculation
  const layers: Record<string, number> = {};
  const getLayer = (id: string, visited = new Set<string>()): number => {
    if (layers[id] !== undefined) return layers[id];
    if (visited.has(id)) return 0;
    visited.add(id);
    const t = tickets.find(x => x.id === id);
    if (!t || !t.blocked_by || t.blocked_by.length === 0) {
      layers[id] = 0;
      return 0;
    }
    const parentLayers = t.blocked_by.map(pid => getLayer(pid, new Set(visited)));
    const maxParentLayer = Math.max(...parentLayers, -1);
    layers[id] = maxParentLayer + 1;
    return maxParentLayer + 1;
  };
  tickets.forEach(t => getLayer(t.id));

  const nodesByLayer: Record<number, string[]> = {};
  tickets.forEach(t => {
    const l = layers[t.id] || 0;
    if (!nodesByLayer[l]) nodesByLayer[l] = [];
    nodesByLayer[l].push(t.id);
  });

  const getTierColor = (tier: Tier) => {
    const colors = {
      blue: '#3b82f6',
      yellow: '#eab308',
      orange: '#f97316',
      red: '#ef4444',
      purple: '#a855f7'
    };
    return colors[tier] || '#3b82f6';
  };

  const dagNodes = tickets.map(t => {
    const layer = layers[t.id] || 0;
    const index = nodesByLayer[layer].indexOf(t.id);
    const x = 50 + layer * 240;
    const y = 50 + index * 130;
    
    const tierColor = getTierColor(t.tier);
    const isDormant = t.status === 'dormant';
    const isDone = t.status === 'done';
    const isReady = t.status === 'ready';

    return {
      id: t.id,
      position: { x, y },
      data: { 
        label: (
          <div className="flex flex-col text-left gap-1" style={{ opacity: isDormant ? 0.55 : 1 }}>
            <div className="flex justify-between items-center text-[10px]">
              <span className="font-mono font-bold text-[#00f2ff]">{t.id}</span>
              <span className="text-xxs px-1 rounded uppercase bg-[#ffffff10]" style={{ color: tierColor }}>{t.tier}</span>
            </div>
            <div className="text-[11px] font-semibold text-white truncate max-w-[140px]">{t.title}</div>
            <div className="text-[9px] flex justify-between items-center">
              <span className={`uppercase font-bold tracking-wider text-[8px] ${
                isDormant ? 'text-slate-500' : isDone ? 'text-slate-400' : 'text-[#10b981]'
              }`}>
                {t.status}
              </span>
              {t.owner && <span className="font-mono text-[8px] text-[#8892b0]">@{t.owner}</span>}
            </div>
          </div>
        )
      },
      style: {
        background: isDormant ? '#090a0f' : isDone ? `${tierColor}0d` : `${tierColor}20`,
        color: isDormant ? '#6b7280' : '#e0e6ed',
        border: `2px solid ${isDormant ? '#374151' : isDone ? '#6b7280' : isReady ? '#10b981' : tierColor}`,
        borderRadius: '12px',
        padding: '10px',
        width: 170,
        boxShadow: isReady ? '0 0 10px rgba(16, 185, 129, 0.2)' : 'none',
        opacity: isDormant ? 0.45 : isDone ? 0.75 : 1,
        filter: isDormant ? 'grayscale(80%)' : 'none'
      }
    };
  });

  const dagEdges: any[] = [];
  tickets.forEach(t => {
    if (t.blocked_by) {
      t.blocked_by.forEach(blockerId => {
        const blockerObj = tickets.find(x => x.id === blockerId);
        dagEdges.push({
          id: `e-${blockerId}-${t.id}`,
          source: blockerId,
          target: t.id,
          animated: t.status !== 'done' && blockerObj?.status !== 'done',
          type: 'smoothstep',
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
            color: t.status === 'done' ? '#10b981' : '#38bdf8'
          },
          style: {
            stroke: t.status === 'done' ? '#10b981' : '#38bdf8',
            strokeWidth: 2,
            opacity: t.status === 'done' ? 0.6 : 1
          }
        });
      });
    }
  });

  const isActorAdmin = actor === 'matt' || actor === 'claude';

  return (
    <div className="w-full max-w-6xl mx-auto p-6 pb-12 flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ClipboardList className="w-6 h-6 text-[#00f2ff]" />
            Job Board
          </h1>
          <p className="text-[#8892b0] text-sm">Event-sourced task board backing TetherLite and HLX-v2.</p>
        </div>
        
        {/* Context Switching & Action buttons */}
        <div className="flex items-center gap-3 self-end md:self-auto">
          <div className="flex items-center gap-2 bg-[#0f111a] border border-[#ffffff14] rounded-lg px-3 py-1.5 text-sm">
            <User className="w-4 h-4 text-[#8892b0]" />
            <span className="text-xs text-[#8892b0]">Actor:</span>
            <select 
              value={actor} 
              onChange={e => setActor(e.target.value)}
              className="bg-transparent text-[#00f2ff] font-semibold border-none outline-none text-xs cursor-pointer"
            >
              <option value="matt">matt (Admin)</option>
              <option value="claude">claude (Admin)</option>
              <option value="codex">codex (Team)</option>
              <option value="gemini">gemini (Team)</option>
            </select>
          </div>
          
          <button 
            onClick={() => setShowPropose(true)}
            className="border border-[#ffffff20] hover:border-[#00f2ff] hover:text-[#00f2ff] text-white text-xs px-3 py-1.5 rounded-lg transition-colors font-medium cursor-pointer"
          >
            Propose Debt
          </button>
          
          {isActorAdmin && (
            <button 
              onClick={() => setShowCreate(true)}
              className="bg-[#00f2ff] hover:bg-[#00d1d1] text-[#05060a] text-xs px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Create Ticket
            </button>
          )}
        </div>
      </div>

      {/* Progress & Stats Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Gate Progress */}
        <div className="md:col-span-2 bg-[#0f111a] border border-[#ffffff14] rounded-xl p-5 flex flex-col gap-3 justify-between">
          <div>
            <div className="flex justify-between items-center mb-1">
              <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-[#00f2ff]" />
                v2 Release Gates
              </h3>
              <span className="text-xs text-[#8892b0]">{gatesDone} of {gatesTotal} Gates Closed</span>
            </div>
            <div className="w-full bg-[#05060a] h-2.5 rounded-full overflow-hidden border border-[#ffffff08]">
              <div 
                className="bg-gradient-to-r from-[#00f2ff] to-[#00ff88] h-full rounded-full transition-all duration-500 shadow-[0_0_10px_rgba(0,242,255,0.4)]"
                style={{ width: `${gatesTotal > 0 ? (gatesDone / gatesTotal) * 100 : 0}%` }}
              />
            </div>
          </div>
          {/* Horizontal Gate Chips */}
          <div className="flex flex-wrap gap-2 pt-2">
            {gateTickets.map(t => (
              <div 
                key={t.id}
                className={`text-xxs px-2 py-1 rounded border font-mono flex items-center gap-1 ${
                  t.status === 'done'
                    ? 'bg-[#042010] text-[#00ff88] border-[#10b981]/30'
                    : 'bg-[#150f0c] text-[#ffd700] border-[#eab308]/20'
                }`}
              >
                <span>{t.id}</span>
                {t.status === 'done' ? <Check className="w-3 h-3" /> : <span className="w-1 h-1 rounded-full bg-[#ffd700] animate-pulse" />}
              </div>
            ))}
            {gateTickets.length === 0 && <span className="text-xs text-[#8892b0]">No gate tickets currently on the board.</span>}
          </div>
        </div>

        {/* Stats Summary */}
        <div className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-5 flex flex-col gap-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
            <Activity className="w-4 h-4 text-[#00f2ff]" />
            Board Summary
          </h3>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-[#05060a] border border-[#ffffff08] p-2 rounded-lg">
              <div className="text-lg font-bold text-white">{tickets.filter(t => t.status === 'open').length}</div>
              <div className="text-[10px] text-[#8892b0] uppercase">Open</div>
            </div>
            <div className="bg-[#05060a] border border-[#ffffff08] p-2 rounded-lg">
              <div className="text-lg font-bold text-[#00f2ff]">{tickets.filter(t => t.status === 'active').length}</div>
              <div className="text-[10px] text-[#8892b0] uppercase">Active</div>
            </div>
            <div className="bg-[#05060a] border border-[#ffffff08] p-2 rounded-lg">
              <div className="text-lg font-bold text-[#ffd700]">{tickets.filter(t => t.status === 'ready').length}</div>
              <div className="text-[10px] text-[#8892b0] uppercase">Ready</div>
            </div>
          </div>
        </div>
      </div>

      {/* Filter panel */}
      <div className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-4 flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap gap-3 items-center">
          <Filter className="w-4 h-4 text-[#8892b0]" />
          
          <select 
            value={filterCategory} 
            onChange={e => setFilterCategory(e.target.value)}
            className="bg-[#05060a] border border-[#ffffff14] text-xs px-3 py-1.5 rounded-lg outline-none text-white cursor-pointer focus:border-[#00f2ff]"
          >
            <option value="">All Categories</option>
            <option value="B">B - Build</option>
            <option value="F">F - Fix</option>
            <option value="D">D - Debt</option>
            <option value="G">G - Gate</option>
            <option value="M">M - Migration</option>
            <option value="R">R - Research</option>
            <option value="S">S - Standing Order</option>
          </select>

          <select 
            value={filterTier} 
            onChange={e => setFilterTier(e.target.value)}
            className="bg-[#05060a] border border-[#ffffff14] text-xs px-3 py-1.5 rounded-lg outline-none text-white cursor-pointer focus:border-[#00f2ff]"
          >
            <option value="">All Tiers</option>
            <option value="blue">Blue (Trivial)</option>
            <option value="yellow">Yellow (Easy)</option>
            <option value="orange">Orange (Hard)</option>
            <option value="red">Red (Very Hard)</option>
            <option value="purple">Purple (Special Grade)</option>
          </select>

          <select 
            value={filterStatus} 
            onChange={e => setFilterStatus(e.target.value)}
            className="bg-[#05060a] border border-[#ffffff14] text-xs px-3 py-1.5 rounded-lg outline-none text-white cursor-pointer focus:border-[#00f2ff]"
          >
            <option value="">All Statuses</option>
            <option value="open">Open [ ]</option>
            <option value="active">Active [~]</option>
            <option value="ready">Ready [/]</option>
            <option value="done">Done [X]</option>
            <option value="dormant">Dormant [zZ]</option>
            <option value="proposed">Proposed</option>
          </select>
        </div>

        {/* Difficulty Legend */}
        <div className="flex flex-wrap gap-3 items-center text-[10px] text-[#8892b0] border-t border-[#ffffff0c] pt-3 w-full mt-1">
          <span className="font-semibold uppercase tracking-wider text-[#e0e6ed]">Difficulty Legend:</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#3b82f6] shadow-[0_0_4px_#3b82f6]" /> Trivial</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#eab308] shadow-[0_0_4px_#eab308]" /> Easy</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#f97316] shadow-[0_0_4px_#f97316]" /> Hard</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#ef4444] shadow-[0_0_4px_#ef4444]" /> Very Hard</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#a855f7] shadow-[0_0_4px_#a855f7]" /> Special Grade</span>
        </div>

        {/* View Switcher */}
        <div className="flex bg-[#05060a] border border-[#ffffff14] rounded-lg p-0.5">
          <button 
            onClick={() => setActiveTab('grid')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer ${activeTab === 'grid' ? 'bg-[#00f2ff] text-[#05060a]' : 'text-[#8892b0]'}`}
          >
            Card Grid
          </button>
          <button 
            onClick={() => setActiveTab('dag')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer ${activeTab === 'dag' ? 'bg-[#00f2ff] text-[#05060a]' : 'text-[#8892b0]'}`}
          >
            Dependency DAG
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="h-64 flex items-center justify-center bg-[#0f111a] border border-[#ffffff14] rounded-xl">
          <span className="text-[#8892b0] text-sm animate-pulse">Loading board states...</span>
        </div>
      ) : activeTab === 'grid' ? (
        <div className="flex flex-col lg:flex-row gap-6 items-start w-full">
          {/* Left Column: Tickets */}
          <div className="flex-1 flex flex-col gap-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 items-start">
              {tickets.map(t => {
                const tierColor = getTierColor(t.tier);
                const isOwner = t.owner === actor;
                const isImplementer = t.implementers.includes(actor);
                const isDormant = t.status === 'dormant';
                const isDone = t.status === 'done';
                const isReady = t.status === 'ready';
                const isExpanded = !!expandedIds[t.id];

                const barStyle = {
                  backgroundColor: isDormant ? 'rgba(5, 6, 10, 0.4)' : isDone ? `${tierColor}05` : `${tierColor}0d`,
                  borderColor: isDormant ? 'rgba(255, 255, 255, 0.05)' : isDone ? 'rgba(107, 114, 128, 0.2)' : isReady ? '#10b98150' : `${tierColor}20`,
                  borderLeft: `4px solid ${tierColor}`,
                  opacity: isDormant ? 0.6 : 1,
                  boxShadow: isReady ? '0 0 10px rgba(16, 185, 129, 0.03)' : 'none',
                };

                return (
                  <div 
                    key={t.id} 
                    style={barStyle}
                    className="border rounded-lg transition-all"
                  >
                    {/* Collapsed Top Bar Row */}
                    <div 
                      onClick={() => toggleExpand(t.id)}
                      className="flex items-center justify-between gap-2 py-2 px-3 cursor-pointer hover:bg-[#ffffff03]"
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-[#8892b0] flex-shrink-0" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-[#8892b0] flex-shrink-0" />
                        )}
                        
                        <span 
                          className="font-mono text-xs px-2 py-0.5 rounded font-bold uppercase flex-shrink-0"
                          style={{ color: tierColor, border: `1px solid ${tierColor}30`, background: `${tierColor}08` }}
                        >
                          {t.id.startsWith('proposed_') ? 'PROP' : t.id}
                        </span>
                        
                        <span className="text-[10px] uppercase tracking-wider text-[#8892b0]/70 font-semibold flex-shrink-0">{t.category}</span>
                        
                        <span className={`font-semibold text-sm truncate ${isDormant ? 'text-[#8892b0]/70' : 'text-white'}`}>
                          {t.title}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        {/* Owner badge */}
                        {t.owner ? (
                          <span className="text-[#8892b0] flex items-center gap-1 font-mono text-[10px] bg-[#ffffff05] px-2 py-0.5 rounded">
                            <User className="w-2.5 h-2.5 text-[#00f2ff]" />
                            @{t.owner}
                          </span>
                        ) : (
                          <span className="text-[#8892b0]/40 text-[10px] italic">unclaimed</span>
                        )}

                        {/* Status Badge */}
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                          isDone ? 'bg-slate-800/30 text-slate-500 border border-slate-700/20' :
                          isDormant ? 'bg-[#0f111a] text-slate-500 border border-slate-800/30' :
                          'bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/20'
                        }`}>
                          {t.status === 'open' ? '[ ] open' :
                           t.status === 'active' ? '[~] active' :
                           t.status === 'ready' ? '[/] ready' :
                           t.status === 'dormant' ? 'dormant' :
                           t.status === 'proposed' ? 'proposed' : '[X] done'}
                        </span>

                        {/* Tier badge (difficulty dot) */}
                        <span 
                          className="w-2.5 h-2.5 rounded-full"
                          style={{ backgroundColor: tierColor, boxShadow: `0 0 6px ${tierColor}` }}
                          title={`Difficulty: ${t.tier}`}
                        />
                      </div>
                    </div>

                    {/* Expanded Details Section */}
                    {isExpanded && (
                      <div className="border-t border-[#ffffff08] bg-[#00000010] p-4 flex flex-col gap-3">
                        <div className="text-xs text-[#8892b0] leading-relaxed whitespace-pre-wrap">
                          {t.description}
                        </div>

                        {/* Details and proofs if done */}
                        {t.work_done && (
                          <div className="bg-[#ffffff03] border border-[#ffffff08] rounded p-2.5 text-xxs">
                            <span className="text-[#00f2ff] font-bold block mb-1">PROOF OF WORK:</span>
                            <div className="text-[#e2e8f0] font-mono whitespace-pre-wrap">{t.work_done}</div>
                          </div>
                        )}

                        <div className="flex flex-wrap gap-3 items-center justify-between text-xxs text-[#8892b0]/80">
                          <div className="flex flex-wrap gap-2">
                            {t.batch && <span className="bg-[#ffffff05] px-1.5 py-0.5 rounded font-mono">batch: {t.batch}</span>}
                            {t.gate && <span className="bg-[#ffffff05] px-1.5 py-0.5 rounded font-mono">gate: {t.gate}</span>}
                            {t.blocked_by && t.blocked_by.length > 0 && (
                              <span className="bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded font-mono">blocked_by: {t.blocked_by.join(',')}</span>
                            )}
                            {t.implementers && t.implementers.length > 0 && (
                              <span className="bg-[#ffffff05] px-1.5 py-0.5 rounded font-mono">implementers: {t.implementers.map(i => `@${i}`).join(', ')}</span>
                            )}
                          </div>

                          {/* Done / Changelog actions */}
                          <div className="flex gap-2">
                            {isDone && (
                              <button
                                onClick={() => handleViewChangelog(t.id)}
                                className="bg-[#00f2ff]/10 hover:bg-[#00f2ff]/20 text-[#00f2ff] border border-[#00f2ff]/30 px-3 py-1 rounded font-semibold cursor-pointer transition-all flex items-center gap-1.5 text-xxs"
                              >
                                <ClipboardList className="w-3 h-3" />
                                View Changelog
                              </button>
                            )}
                          </div>
                        </div>

                        {/* State Transition Actions */}
                        <div className="border-t border-[#ffffff05] pt-3 flex items-center justify-end gap-2 text-xxs">
                          <div className="flex gap-2">
                            {t.status === 'open' && (
                              <button 
                                onClick={() => handleClaim(t.id)}
                                className="bg-[#00f2ff]/10 hover:bg-[#00f2ff]/20 text-[#00f2ff] px-2.5 py-1 rounded font-semibold cursor-pointer transition-colors"
                              >
                                Claim [~]
                              </button>
                            )}

                            {t.status === 'active' && isOwner && (
                              <button 
                                onClick={() => setShowFlagModal(t)}
                                className="bg-[#ffd700]/10 hover:bg-[#ffd700]/20 text-[#ffd700] px-2.5 py-1 rounded font-semibold cursor-pointer transition-colors"
                              >
                                Flag Ready [/]
                              </button>
                            )}

                            {t.status === 'ready' && isActorAdmin && (
                              <button 
                                onClick={() => handleFinalize(t.id)}
                                disabled={isImplementer}
                                title={isImplementer ? "Separation of duties: you cannot finalize your own work" : ""}
                                className="bg-[#10b981] hover:bg-[#10b981]/90 text-[#05060a] disabled:opacity-30 disabled:cursor-not-allowed px-3 py-1 rounded font-bold cursor-pointer transition-all flex items-center gap-1 text-xxs"
                              >
                                <Check className="w-3 h-3" />
                                Send to Changelog (Finalize)
                              </button>
                            )}

                            {t.status === 'proposed' && isActorAdmin && (
                              <button 
                                onClick={() => handleAccept(t.id)}
                                className="bg-[#00f2ff] hover:bg-[#00d1d1] text-[#05060a] px-2.5 py-1 rounded font-bold cursor-pointer transition-colors"
                              >
                                Accept
                              </button>
                            )}

                            {!isDone && t.status !== 'proposed' && !isDormant && isActorAdmin && (
                              <button 
                                onClick={() => handleDormant(t.id)}
                                className="border border-slate-700 hover:border-slate-500 text-slate-400 hover:text-slate-300 px-2 py-1 rounded cursor-pointer"
                              >
                                Pause
                              </button>
                            )}
                            
                            {isDormant && isActorAdmin && (
                              <button 
                                onClick={() => handleRevive(t.id)}
                                className="bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 px-2.5 py-1 rounded font-semibold cursor-pointer transition-colors"
                              >
                                Revive
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {tickets.length === 0 && (
                <div className="col-span-full h-32 flex items-center justify-center bg-[#0f111a] border border-[#ffffff14] rounded-xl">
                  <span className="text-[#8892b0] text-xs">No tickets match the selected filters.</span>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Whiteboard / Scratchpad */}
          <div className="w-full lg:w-80 flex-shrink-0 bg-[#ffffff] text-slate-800 border border-slate-200 shadow-2xl rounded-xl p-5 flex flex-col gap-3 font-sans relative">
            <div className="flex justify-between items-center border-b border-slate-100 pb-2">
              <h3 className="font-bold text-sm text-slate-800 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-indigo-600" />
                Whiteboard / Scratchpad
              </h3>
              <div className="text-[10px] font-semibold flex items-center gap-1">
                {whiteboardSaving ? (
                  <span className="text-amber-500 animate-pulse font-medium">Saving...</span>
                ) : (
                  <span className="text-emerald-600 font-medium">Saved</span>
                )}
              </div>
            </div>
            
            <textarea
              id="whiteboard-textarea"
              value={whiteboardText}
              onChange={(e) => handleWhiteboardChange(e.target.value)}
              placeholder="Jot down notes or draft tickets... (Auto-saves. Highlight text and click Synthesize to propose a ticket!)"
              className="w-full bg-transparent border-none focus:outline-none text-slate-800 text-xs resize-none leading-relaxed h-80 font-mono focus:ring-0"
            />
            
            <div className="flex justify-between items-center border-t border-slate-100 pt-2 text-xxs">
              <button
                onClick={handleSynthesize}
                className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-2.5 py-1.5 rounded flex items-center gap-1 transition-colors cursor-pointer"
                title="Propose ticket from highlighted text or full scratchpad"
              >
                <Sparkles className="w-3 h-3" />
                Synthesize Ticket
              </button>
              
              <button
                onClick={() => {
                  if (confirm("Clear the whiteboard?")) {
                    handleWhiteboardChange("");
                  }
                }}
                className="text-slate-400 hover:text-red-500 p-1.5 rounded transition-colors cursor-pointer"
                title="Clear whiteboard"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* React Flow DAG view */
        <div className="h-[650px] w-full bg-[#05060a] border border-[#ffffff14] rounded-xl overflow-hidden relative">
          <ReactFlow 
            nodes={dagNodes} 
            edges={dagEdges}
            fitView
          >
            <Background color="#1f2937" gap={16} />
            <Controls style={{ background: '#0f111a', border: '1px solid #ffffff14', color: '#e0e6ed' }} />
          </ReactFlow>
          <div className="absolute bottom-3 left-3 bg-[#0f111a]/95 border border-[#ffffff14] rounded-lg px-3.5 py-2.5 text-xxs flex flex-col gap-1.5 z-10 pointer-events-none w-48">
            <span className="font-semibold text-white mb-0.5 border-b border-[#ffffff10] pb-1 uppercase tracking-wider text-[9px]">DAG Legend</span>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded bg-[#6b7280]" /> Closed / Done (Grey)</div>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded bg-[#10b981] shadow-[0_0_4px_#10b981]" /> Active / Ready (Green)</div>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded bg-[#374151] opacity-50" /> Dormant (Muted)</div>
            
            <span className="font-semibold text-white mt-1.5 mb-0.5 border-b border-[#ffffff10] pb-1 uppercase tracking-wider text-[9px]">Difficulty Tiers</span>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded-full bg-[#3b82f6]" /> Trivial</div>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded-full bg-[#eab308]" /> Easy</div>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded-full bg-[#f97316]" /> Hard</div>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded-full bg-[#ef4444]" /> Very Hard</div>
            <div className="flex items-center gap-1.5 text-[#8892b0]"><span className="w-2 h-2 rounded-full bg-[#a855f7]" /> Special Grade</div>
          </div>
        </div>
      )}

      {/* Flag / Ready Modal */}
      {showFlagModal && (
        <div className="fixed inset-0 bg-[#00000080] flex items-center justify-center p-4 z-50 animate-fade-in">
          <form 
            onSubmit={handleFlag}
            className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-6 w-full max-w-md flex flex-col gap-4 shadow-2xl"
          >
            <h3 className="font-semibold text-lg text-white">Flag inspection-ready</h3>
            <p className="text-xs text-[#8892b0]">Provide a summary of the implementation details or artifact path (e.g. file path or handle) as proof of work.</p>
            <div>
              <label className="block text-xxs text-[#8892b0] uppercase tracking-wider font-bold mb-1.5">Work Done / Completion Proof</label>
              <textarea 
                value={workDoneText}
                onChange={e => setWorkDoneText(e.target.value)}
                placeholder="Describe your implementation..."
                required
                className="w-full bg-[#05060a] border border-[#ffffff14] focus:border-[#ffd700] rounded-lg px-3 py-2 text-xs outline-none text-white h-24 resize-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 text-xs">
              <button 
                type="button" 
                onClick={() => { setShowFlagModal(null); setWorkDoneText(''); }}
                className="border border-[#ffffff20] hover:bg-[#ffffff05] px-4 py-2 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <button 
                type="submit"
                disabled={!workDoneText.trim()}
                className="bg-[#ffd700] hover:bg-[#ffd700]/90 text-[#05060a] font-bold px-4 py-2 rounded-lg cursor-pointer disabled:opacity-50"
              >
                Flag Ready [/]
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Propose Modal */}
      {showPropose && (
        <div className="fixed inset-0 bg-[#00000080] flex items-center justify-center p-4 z-50">
          <form 
            onSubmit={handlePropose}
            className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-6 w-full max-w-md flex flex-col gap-4 shadow-2xl"
          >
            <h3 className="font-semibold text-lg text-white">Propose Debt / Ticket</h3>
            <p className="text-xs text-[#8892b0]">Propose a work item found mid-task. It will go into a holding proposed state for admin approval.</p>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Category</label>
                <select 
                  value={proposeForm.category}
                  onChange={e => setProposeForm({ ...proposeForm, category: e.target.value })}
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                >
                  <option value="D">D - Debt</option>
                  <option value="F">F - Fix</option>
                  <option value="B">B - Build</option>
                  <option value="R">R - Research</option>
                </select>
              </div>
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Tier</label>
                <select 
                  value={proposeForm.tier}
                  onChange={e => setProposeForm({ ...proposeForm, tier: e.target.value })}
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                >
                  <option value="blue">Blue</option>
                  <option value="yellow">Yellow</option>
                  <option value="orange">Orange</option>
                  <option value="red">Red</option>
                  <option value="purple">Purple</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Title</label>
              <input 
                type="text" 
                value={proposeForm.title}
                onChange={e => setProposeForm({ ...proposeForm, title: e.target.value })}
                required
                className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Description</label>
              <textarea 
                value={proposeForm.description}
                onChange={e => setProposeForm({ ...proposeForm, description: e.target.value })}
                required
                className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white h-20 resize-none"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 text-xs">
              <button type="button" onClick={() => setShowPropose(false)} className="border border-[#ffffff20] px-4 py-2 rounded-lg cursor-pointer">Cancel</button>
              <button type="submit" className="bg-[#00f2ff] hover:bg-[#00d1d1] text-[#05060a] font-bold px-4 py-2 rounded-lg cursor-pointer">Propose</button>
            </div>
          </form>
        </div>
      )}

      {/* Author / Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-[#00000080] flex items-center justify-center p-4 z-50">
          <form 
            onSubmit={handleCreate}
            className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-6 w-full max-w-lg flex flex-col gap-4 shadow-2xl h-[90vh] overflow-y-auto"
          >
            <h3 className="font-semibold text-lg text-white">Create Board Ticket</h3>
            
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Category</label>
                <select 
                  value={createForm.category}
                  onChange={e => setCreateForm({ ...createForm, category: e.target.value })}
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                >
                  <option value="B">B - Build</option>
                  <option value="F">F - Fix</option>
                  <option value="D">D - Debt</option>
                  <option value="G">G - Gate</option>
                  <option value="M">M - Migration</option>
                  <option value="R">R - Research</option>
                  <option value="S">S - Standing Order</option>
                </select>
              </div>
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Tier</label>
                <select 
                  value={createForm.tier}
                  onChange={e => setCreateForm({ ...createForm, tier: e.target.value })}
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                >
                  <option value="blue">Blue</option>
                  <option value="yellow">Yellow</option>
                  <option value="orange">Orange</option>
                  <option value="red">Red</option>
                  <option value="purple">Purple</option>
                </select>
              </div>
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Initial Status</label>
                <select 
                  value={createForm.status}
                  onChange={e => setCreateForm({ ...createForm, status: e.target.value })}
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                >
                  <option value="open">Open</option>
                  <option value="dormant">Dormant</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Title</label>
              <input 
                type="text" 
                value={createForm.title}
                onChange={e => setCreateForm({ ...createForm, title: e.target.value })}
                required
                className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
              />
            </div>

            <div>
              <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Description</label>
              <textarea 
                value={createForm.description}
                onChange={e => setCreateForm({ ...createForm, description: e.target.value })}
                required
                className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white h-20 resize-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Batch</label>
                <input 
                  type="text" 
                  value={createForm.batch}
                  onChange={e => setCreateForm({ ...createForm, batch: e.target.value })}
                  placeholder="e.g. B1"
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Gate Code</label>
                <input 
                  type="text" 
                  value={createForm.gate}
                  onChange={e => setCreateForm({ ...createForm, gate: e.target.value })}
                  placeholder="e.g. 12a"
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xxs">
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Blocks (comma separated)</label>
                <input 
                  type="text" 
                  value={createForm.blocks}
                  onChange={e => setCreateForm({ ...createForm, blocks: e.target.value })}
                  placeholder="e.g. M-3"
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Blocked By (comma separated)</label>
                <input 
                  type="text" 
                  value={createForm.blocked_by}
                  onChange={e => setCreateForm({ ...createForm, blocked_by: e.target.value })}
                  placeholder="e.g. B-1"
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xxs">
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Principles Served (comma separated)</label>
                <input 
                  type="text" 
                  value={createForm.principle}
                  onChange={e => setCreateForm({ ...createForm, principle: e.target.value })}
                  placeholder="e.g. P1"
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                />
              </div>
              <div>
                <label className="block text-xxs text-[#8892b0] uppercase font-bold mb-1.5">Bible References (comma separated)</label>
                <input 
                  type="text" 
                  value={createForm.bible_ref}
                  onChange={e => setCreateForm({ ...createForm, bible_ref: e.target.value })}
                  placeholder="e.g. §2"
                  className="w-full bg-[#05060a] border border-[#ffffff14] rounded-lg px-3 py-2 text-xs text-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 text-xs">
              <button type="button" onClick={() => setShowCreate(false)} className="border border-[#ffffff20] px-4 py-2 rounded-lg cursor-pointer">Cancel</button>
              <button type="submit" className="bg-[#00f2ff] hover:bg-[#00d1d1] text-[#05060a] font-bold px-4 py-2 rounded-lg cursor-pointer">Create</button>
            </div>
          </form>
        </div>
      )}

    </div>
  );
}
