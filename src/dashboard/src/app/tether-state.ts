import {Injectable, computed, effect, signal} from '@angular/core';

export interface ThemeColors {
  '--bg-base': string;
  '--bg-surface': string;
  '--bg-elevated': string;
  '--border': string;
  '--border-strong': string;
  '--text-primary': string;
  '--text-secondary': string;
  '--text-muted': string;
  '--accent': string;
  '--accent-dim': string;
  '--semantic-ok': string;
  '--semantic-warn': string;
  '--semantic-err': string;
  '--semantic-info': string;
}

export interface AgentNode {
  id: string;
  name: string;
  status: 'online' | 'degraded' | 'offline';
  msgsToday: number;
  lastSeen: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
}

export interface NetworkEdge {
  id: string;
  from: string;
  to: string;
  status: 'healthy' | 'degraded' | 'broken';
  error?: string;
  lastSeen?: string;
}

export interface FeedItem {
  id: string;
  timestamp: string;
  route: string;
  handle: string;
  type: 'board' | 'messages' | 'task' | 'whiteboard' | 'channel';
}

export interface MessageItem {
  id: string;
  sender: string;
  subject: string;
  preview: string;
  body: string;
  timestamp: string;
  read: boolean;
  archived: boolean;
  tags: string[];
}

export interface JobTicket {
  id: string;
  title: string;
  handle: string;
  category: 'core' | 'p2p' | 'crypto' | 'ui' | 'agent';
  status: 'open' | 'active' | 'ready' | 'completed';
  difficulty: 'low' | 'medium' | 'high';
  tier: 'local' | 'relay' | 'cloud';
  description: string;
}

export interface ChangelogEntry {
  id: string;
  title: string;
  handle: string;
  problem: string;
  solution: string;
  timestamp: string;
}

export interface ChannelItem {
  id: string;
  name: string;
  description: string;
  members: string[];
  createdAt: string;
}

export interface ChannelMessage {
  id: string;
  channelId: string;
  sender: string;
  body: string;
  timestamp: string;
  threadId?: string;
}

export const THEMES: Record<string, ThemeColors> = {
  void: {
    '--bg-base': '#03000a',
    '--bg-surface': '#0a0418',
    '--bg-elevated': '#14092b',
    '--border': '#26134b',
    '--border-strong': '#8b5cf6',
    '--text-primary': '#fafafc',
    '--text-secondary': '#d8b4fe',
    '--text-muted': '#6d28d9',
    '--accent': '#c084fc',
    '--accent-dim': 'rgba(139, 92, 246, 0.15)',
    '--semantic-ok': '#c084fc',
    '--semantic-warn': '#fbbf24',
    '--semantic-err': '#ef4444',
    '--semantic-info': '#3b82f6',
  },
  cyberpunk: {
    '--bg-base': '#05050a',
    '--bg-surface': '#0d0d18',
    '--bg-elevated': '#18182d',
    '--border': '#2a2b44',
    '--border-strong': '#f5e642',
    '--text-primary': '#f5e642',
    '--text-secondary': '#ff007f',
    '--text-muted': '#6366f1',
    '--accent': '#f5e642',
    '--accent-dim': 'rgba(245, 230, 66, 0.15)',
    '--semantic-ok': '#f5e642',
    '--semantic-warn': '#f5e642',
    '--semantic-err': '#ff007f',
    '--semantic-info': '#00ffff',
  },
  synthwave: {
    '--bg-base': '#0a0512',
    '--bg-surface': '#120921',
    '--bg-elevated': '#1e1135',
    '--border': '#351f5c',
    '--border-strong': '#ff007f',
    '--text-primary': '#ffffff',
    '--text-secondary': '#dca7f5',
    '--text-muted': '#684e94',
    '--accent': '#ff007f',
    '--accent-dim': 'rgba(255, 0, 127, 0.15)',
    '--semantic-ok': '#ff007f',
    '--semantic-warn': '#ffcc00',
    '--semantic-err': '#ff007f',
    '--semantic-info': '#00f0ff',
  },
  classic: {
    '--bg-base': '#f8fafc',
    '--bg-surface': '#ffffff',
    '--bg-elevated': '#f1f5f9',
    '--border': '#3b82f6',
    '--border-strong': '#2563eb',
    '--text-primary': '#0f172a',
    '--text-secondary': '#475569',
    '--text-muted': '#94a3b8',
    '--accent': '#2563eb',
    '--accent-dim': 'rgba(37, 99, 235, 0.1)',
    '--semantic-ok': '#2563eb',
    '--semantic-warn': '#f59e0b',
    '--semantic-err': '#ef4444',
    '--semantic-info': '#3b82f6',
  },
  terminal: {
    '--bg-base': '#f5f2eb',
    '--bg-surface': '#ffffff',
    '--bg-elevated': '#e9e5db',
    '--border': '#7d8c56',
    '--border-strong': '#5b6c34',
    '--text-primary': '#2d351a',
    '--text-secondary': '#556331',
    '--text-muted': '#84935e',
    '--accent': '#5b6c34',
    '--accent-dim': 'rgba(125, 140, 86, 0.15)',
    '--semantic-ok': '#2e7d32',
    '--semantic-warn': '#d97706',
    '--semantic-err': '#dc2626',
    '--semantic-info': '#2563eb',
  },
  arctic: {
    '--bg-base': '#040a14',
    '--bg-surface': '#091322',
    '--bg-elevated': '#122138',
    '--border': '#1d3354',
    '--border-strong': '#93c5fd',
    '--text-primary': '#f8fafc',
    '--text-secondary': '#94a3b8',
    '--text-muted': '#4c6585',
    '--accent': '#38bdf8',
    '--accent-dim': 'rgba(56, 189, 248, 0.15)',
    '--semantic-ok': '#38bdf8',
    '--semantic-warn': '#fbbf24',
    '--semantic-err': '#ef4444',
    '--semantic-info': '#3b82f6',
  },
  ember: {
    '--bg-base': '#1e1e20',
    '--bg-surface': '#28282b',
    '--bg-elevated': '#36363a',
    '--border': '#444449',
    '--border-strong': '#f97316',
    '--text-primary': '#fafafa',
    '--text-secondary': '#e4e4e7',
    '--text-muted': '#71717a',
    '--accent': '#f97316',
    '--accent-dim': 'rgba(249, 115, 22, 0.15)',
    '--semantic-ok': '#f97316',
    '--semantic-warn': '#f59e0b',
    '--semantic-err': '#ef4444',
    '--semantic-info': '#3b82f6',
  },
};

@Injectable({
  providedIn: 'root',
})
export class TetherState {
  // Appearance / Settings State
  activeThemeName = signal<string>('ember');
  customThemeTokens = signal<ThemeColors | null>(null);
  wallpaperUrl = signal<string>('');

  sidebarCollapsed = signal<boolean>(false);
  feedVisible = signal<boolean>(true);
  density = signal<'comfortable' | 'compact'>('comfortable');

  // Language & Regional Settings
  language = signal<string>('en');
  dateFormat = signal<string>('ISO 8601');
  timezone = signal<string>('auto');

  // Behavior Settings
  autonomousMode = signal<boolean>(true);
  staleHours = signal<number>(24);
  desktopNotifications = signal<boolean>(true);
  soundOnNewMessage = signal<boolean>(true);

  // Core Data Stores
  nodes = signal<AgentNode[]>([]);
  edges = signal<NetworkEdge[]>([]);
  feed = signal<FeedItem[]>([]);
  messages = signal<MessageItem[]>([]);
  tickets = signal<JobTicket[]>([]);
  changelog = signal<ChangelogEntry[]>([]);
  whiteboardText = signal<string>('# Shared Scratchpad & Whiteboard\n\nUse this space for collaborative draft thoughts between active network agents.\n\n- **Project Hook**: Sync tasks from SQLite logs\n- **Node Endpoint**: `http://localhost:18083` for code analysis\n- **PAKE Status**: Completed local LAN discovery handshake');
  channels = signal<ChannelItem[]>([]);
  channelMessages = signal<ChannelMessage[]>([]);

  // Multiplexer presence + routes
  presenceMap = signal<Record<string, { status: string; pid?: number; ping_port?: number }>>({});
  routes = signal<Array<{ id: string; from_agent: string; to_agent: string; status: string }>>([]);

  // Konsole (KDE) terminal driver
  konsoleAvailable = signal<boolean>(true);
  konsoleSessions = signal<Array<{
    service: string; session: string; pid: string; proc: string; cmdline: string;
    title: string; ambiguous: boolean; guessedAgent: string | null; boundAgent: string | null;
  }>>([]);
  registryAgents = signal<Array<{ id: string; name: string; cli: string; command: string }>>([]);

  // Active UI States
  activeDiagnosticEdge = signal<NetworkEdge | null>(null);
  selectedMessage = signal<MessageItem | null>(null);
  selectedChannelId = signal<string>('');
  unreadChannels = signal<string[]>([]);

  // Computed Theme Variables
  themeVariables = computed(() => {
    const themeName = this.activeThemeName();
    if (themeName === 'custom' && this.customThemeTokens()) {
      return this.customThemeTokens()!;
    }
    return THEMES[themeName] || THEMES['void'];
  });

  // Simulated live routing toggles
  feedPaused = signal<boolean>(false);

  private _apiBase = '';   // same origin — dashboard is served by the same FastAPI process
  private _pollTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.loadFromLocalStorage();
    this.initChannels();
    this.initNetworkFromApi();
    this.initMessagesFromApi();
    this.initBoardFromApi();
    this.initPresenceSocket();
    this.loadRegistry();

    // Auto-save to localStorage on signal updates
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_theme', this.activeThemeName());
      }
    });
    effect(() => {
      const custom = this.customThemeTokens();
      if (custom && typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_custom_theme', JSON.stringify(custom));
      }
    });
    effect(() => {
      const wall = this.wallpaperUrl();
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_wallpaper', wall);
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_sidebar_collapsed', String(this.sidebarCollapsed()));
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_feed_visible', String(this.feedVisible()));
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_density', this.density());
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_nodes', JSON.stringify(this.nodes()));
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_edges', JSON.stringify(this.edges()));
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_tickets', JSON.stringify(this.tickets()));
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_changelog', JSON.stringify(this.changelog()));
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_messages', JSON.stringify(this.messages()));
      }
    });
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_whiteboard', this.whiteboardText());
      }
    });
    // Channels/messages are server-backed — no localStorage persistence needed.
    effect(() => {
      if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
        localStorage.setItem('tether_unread_channels', JSON.stringify(this.unreadChannels()));
      }
    });

    // Expose clean programmatic API on window for automated AI or dev interactions
    if (typeof window !== 'undefined') {
      (window as unknown as Record<string, unknown>)['tetherApi'] = {
        state: this,
        getNodes: () => this.nodes(),
        getEdges: () => this.edges(),
        getTickets: () => this.tickets(),
        getChangelog: () => this.changelog(),
        getMessages: () => this.messages(),
        getChannels: () => this.channels(),
        getChannelMessages: () => this.channelMessages(),
        createChannel: (name: string, description: string) => this.createChannel(name, description),
        deleteChannel: (id: string) => this.deleteChannel(id),
        sendChannelMessage: (channelId: string, sender: string, body: string, threadId?: string) => 
          this.sendChannelMessage(channelId, sender, body, threadId),
        registerAgent: (name: string, port: string) => this.registerAgent(name, port),
        deleteAgent: (id: string) => this.deleteAgent(id),
        createTicket: (title: string, category: 'core' | 'p2p' | 'crypto' | 'ui' | 'agent', difficulty: 'low' | 'medium' | 'high', tier: 'local' | 'relay' | 'cloud', description: string) => 
          this.createTicket(title, category, difficulty, tier, description),
        sendToChangelog: (ticketId: string, title: string, problem: string, solution: string) => 
          this.sendToChangelog(ticketId, title, problem, solution),
        sendMessage: (to: string, subject: string, body: string, tags: string) => this.sendMessage(to, subject, body, tags),
        killConnection: (id: string) => {
          this.edges.update(edges => edges.filter(e => e.id !== id));
          if (this.activeDiagnosticEdge()?.id === id) {
            this.activeDiagnosticEdge.set(null);
          }
        },
        exportDatabaseSnapshot: () => this.exportDatabaseSnapshot(),
        importDatabaseSnapshot: (json: string) => this.importDatabaseSnapshot(json),
        resetAllAgentRegistrations: () => this.resetAllAgentRegistrations(),
      };
    }

  }

  private loadFromLocalStorage() {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      this.resetNodes();
      this.resetEdges();
      this.resetTickets();
      this.resetChangelog();
      this.resetMessages();
      return;
    }
    // Theme
    const savedTheme = localStorage.getItem('tether_theme');
    if (savedTheme) this.activeThemeName.set(savedTheme);

    const savedCustomTheme = localStorage.getItem('tether_custom_theme');
    if (savedCustomTheme) {
      try {
        this.customThemeTokens.set(JSON.parse(savedCustomTheme));
      } catch {
        console.error('Error parsing custom theme');
      }
    }

    const savedWallpaper = localStorage.getItem('tether_wallpaper');
    if (savedWallpaper) this.wallpaperUrl.set(savedWallpaper);
    if (savedCustomTheme) {
      try {
        this.customThemeTokens.set(JSON.parse(savedCustomTheme));
      } catch {
        console.error('Error parsing custom theme');
      }
    }

    // Settings
    this.sidebarCollapsed.set(localStorage.getItem('tether_sidebar_collapsed') === 'true');
    this.feedVisible.set(localStorage.getItem('tether_feed_visible') !== 'false');
    const savedDensity = localStorage.getItem('tether_density');
    if (savedDensity) this.density.set(savedDensity as 'comfortable' | 'compact');

    // Whiteboard
    const savedWhiteboard = localStorage.getItem('tether_whiteboard');
    if (savedWhiteboard) this.whiteboardText.set(savedWhiteboard);

    // Initial Nodes
    const savedNodes = localStorage.getItem('tether_nodes');
    if (savedNodes) {
      try {
        this.nodes.set(JSON.parse(savedNodes));
      } catch {
        this.resetNodes();
      }
    } else {
      this.resetNodes();
    }

    // Initial Edges
    const savedEdges = localStorage.getItem('tether_edges');
    if (savedEdges) {
      try {
        this.edges.set(JSON.parse(savedEdges));
      } catch {
        this.resetEdges();
      }
    } else {
      this.resetEdges();
    }


    // Tickets
    const savedTickets = localStorage.getItem('tether_tickets');
    if (savedTickets) {
      try {
        this.tickets.set(JSON.parse(savedTickets));
      } catch {
        this.resetTickets();
      }
    } else {
      this.resetTickets();
    }

    // Changelog
    const savedChangelog = localStorage.getItem('tether_changelog');
    if (savedChangelog) {
      try {
        this.changelog.set(JSON.parse(savedChangelog));
      } catch {
        this.resetChangelog();
      }
    } else {
      this.resetChangelog();
    }

    // Messages
    const savedMessages = localStorage.getItem('tether_messages');
    if (savedMessages) {
      try {
        this.messages.set(JSON.parse(savedMessages));
      } catch {
        this.resetMessages();
      }
    } else {
      this.resetMessages();
    }

    // Channels
    const savedChannels = localStorage.getItem('tether_channels');
    if (savedChannels) {
      try {
        this.channels.set(JSON.parse(savedChannels));
      } catch {
        this.resetChannels();
      }
    } else {
      this.resetChannels();
    }

    // Channel Messages
    const savedChanMsgs = localStorage.getItem('tether_channel_messages');
    if (savedChanMsgs) {
      try {
        this.channelMessages.set(JSON.parse(savedChanMsgs));
      } catch {
        this.resetChannelMessages();
      }
    } else {
      this.resetChannelMessages();
    }

    const savedSelChan = localStorage.getItem('tether_selected_channel_id');
    if (savedSelChan) {
      this.selectedChannelId.set(savedSelChan);
    } else if (this.channels().length > 0) {
      this.selectedChannelId.set(this.channels()[0].id);
    }

    const savedUnreadChans = localStorage.getItem('tether_unread_channels');
    if (savedUnreadChans) {
      try {
        this.unreadChannels.set(JSON.parse(savedUnreadChans));
      } catch {
        this.unreadChannels.set([]);
      }
    } else {
      this.unreadChannels.set([]);
    }

  }

  // --- Reset to default helpers ---
  resetNodes() {
    this.nodes.set([]);
  }

  resetEdges() {
    this.edges.set([]);
  }

  resetTickets() {
    this.tickets.set([]);
  }

  resetChangelog() {
    this.changelog.set([]);
  }

  resetMessages() {
    this.messages.set([]);
  }

  private generateInitialFeed() {
    const types: ('board' | 'messages' | 'task' | 'whiteboard')[] = ['messages', 'task', 'board', 'whiteboard'];
    const sources = ['claude-3.5', 'gemini-1.5', 'sys_router', 'terminal-cli'];
    const dests = ['codex-engine', 'sys_router', 'claude-3.5'];
    
    const items: FeedItem[] = [];
    const date = new Date();
    for (let i = 0; i < 20; i++) {
      const timeOffset = (20 - i) * 30; // seconds ago
      const itemTime = new Date(date.getTime() - timeOffset * 1000);
      const timeStr = itemTime.toTimeString().split(' ')[0];
      const src = sources[Math.floor(Math.random() * sources.length)];
      const dst = dests[Math.floor(Math.random() * dests.length)];
      
      items.push({
        id: `f_${i}`,
        timestamp: timeStr,
        route: `${src} → ${dst}`,
        handle: `h&l_msg_${Math.random().toString(16).substr(2, 8)}`,
        type: types[Math.floor(Math.random() * types.length)],
      });
    }
    this.feed.set(items);
  }

  private startTrafficSimulator() {
    const types: ('board' | 'messages' | 'task' | 'whiteboard')[] = ['messages', 'task', 'board', 'whiteboard'];
    const sources = ['claude-3.5', 'gemini-1.5', 'sys_router', 'terminal-cli'];
    const dests = ['codex-engine', 'sys_router', 'claude-3.5'];

    setInterval(() => {
      // Don't append if paused by user hover
      if (this.feedPaused()) return;

      // Add a small chance to simulate an active signal traffic
      if (Math.random() > 0.4) {
        const date = new Date();
        const timeStr = date.toTimeString().split(' ')[0];
        const src = sources[Math.floor(Math.random() * sources.length)];
        const dst = dests[Math.floor(Math.random() * dests.length)];
        const newEvent: FeedItem = {
          id: `f_${Date.now()}`,
          timestamp: timeStr,
          route: `${src} → ${dst}`,
          handle: `h&l_msg_${Math.random().toString(16).substr(2, 8)}`,
          type: types[Math.floor(Math.random() * types.length)],
        };

        this.feed.update(items => {
          const updated = [...items, newEvent];
          // Keep list limited to 100 for high performance
          if (updated.length > 100) updated.shift();
          return updated;
        });

        // Increment today's messages for a random node
        const nodeIndex = Math.floor(Math.random() * this.nodes().length);
        this.nodes.update(nodesList => {
          const copy = [...nodesList];
          if (copy[nodeIndex]) {
            copy[nodeIndex] = {
              ...copy[nodeIndex],
              msgsToday: copy[nodeIndex].msgsToday + 1,
              lastSeen: '1s ago'
            };
          }
          return copy;
        });
      }
    }, 3000);
  }

  // --- Actions ---

  // Diagnostic Action: Retry Connection
  retryDiagnosticConnection(edgeId: string) {
    const index = this.edges().findIndex(e => e.id === edgeId);
    if (index === -1) return;

    // Set to online after simulated handshake
    const targetEdge = this.edges()[index];
    this.edges.update(edgesList => {
      const copy = [...edgesList];
      copy[index] = { ...copy[index], status: 'healthy' };
      delete copy[index].error;
      return copy;
    });

    // Also bring the destination node online
    const nodeIndex = this.nodes().findIndex(n => n.name === targetEdge.to);
    if (nodeIndex !== -1) {
      this.nodes.update(nodesList => {
        const copy = [...nodesList];
        copy[nodeIndex] = { ...copy[nodeIndex], status: 'online', lastSeen: '1s ago' };
        return copy;
      });
    }

    // Clear active diagnostic selection
    this.activeDiagnosticEdge.set(null);
  }

  // Register Agent
  registerAgent(name: string, _port?: string) {
    const id = name.toLowerCase().replace(/\s+/g, '-');
    // Skip if already on the graph
    if (this.nodes().some(n => n.id === id || n.name === name)) return;
    const newNode: AgentNode = {
      id,
      name,
      // Offline until a daemon heartbeat lands — presence socket flips it green
      status: 'offline',
      msgsToday: 0,
      lastSeen: 'never',
      x: 100 + Math.random() * 400,
      y: 100 + Math.random() * 200,
    };
    this.nodes.update(nodesList => [...nodesList, newNode]);
  }

  /**
   * The ergonomic one-shot path: add the agent to the graph AND spawn its
   * ping daemon. The user supplies only a name — the dashboard handles the
   * port and delivery mode. Node goes green when the first heartbeat arrives.
   */
  registerAndConnect(name: string): Promise<void> {
    this.registerAgent(name);
    return this.connectAgent(name);
  }

  // Delete Node
  deleteAgent(id: string) {
    const agent = this.nodes().find(n => n.id === id);
    if (!agent) return;

    this.nodes.update(nodesList => nodesList.filter(n => n.id !== id));
    this.edges.update(edgesList => edgesList.filter(e => e.from !== agent.name && e.to !== agent.name));
  }

  // Message Actions
  markMessageRead(id: string, read: boolean) {
    this.messages.update(msgs => msgs.map(m => m.id === id ? { ...m, read } : m));
  }

  archiveMessage(id: string) {
    this.messages.update(msgs => msgs.map(m => m.id === id ? { ...m, archived: true } : m));
    if (this.selectedMessage()?.id === id) {
      this.selectedMessage.set(null);
    }
  }

  deleteMessage(id: string) {
    this.messages.update(msgs => msgs.filter(m => m.id !== id));
    if (this.selectedMessage()?.id === id) {
      this.selectedMessage.set(null);
    }
  }

  sendMessage(to: string, subject: string, body: string, tagsString: string) {
    const tags = tagsString ? tagsString.split(',').map(t => t.trim().toLowerCase()).filter(Boolean) : [];
    const newMsg: MessageItem = {
      id: `m_${Date.now()}`,
      sender: 'terminal-cli',
      subject,
      preview: body.length > 60 ? body.substr(0, 60) + '...' : body,
      body,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      read: true,
      archived: false,
      tags
    };

    this.messages.update(msgs => [newMsg, ...msgs]);

    // Auto-reply simulation for extreme fidelity!
    if (this.autonomousMode()) {
      setTimeout(() => {
        const reply: MessageItem = {
          id: `m_${Date.now() + 1}`,
          sender: to,
          subject: `Re: ${subject}`,
          preview: `Message received and processed with handle blake3_a7...`,
          body: `Handshake confirmed.\nYour payload has been committed to SQLite. Key token verification matches block signature.\n\nReply Ref ID: h&l_resp_${Math.random().toString(16).substr(2, 6)}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          read: false,
          archived: false,
          tags: ['system', 'reply']
        };
        this.messages.update(msgs => [reply, ...msgs]);
      }, 2500);
    }
  }

  // Job Board & Changelog
  createTicket(title: string, category: 'core' | 'p2p' | 'crypto' | 'ui' | 'agent', difficulty: 'low' | 'medium' | 'high', tier: 'local' | 'relay' | 'cloud', description: string) {
    const handle = Math.random().toString(16).substr(2, 6) + '...' + Math.random().toString(16).substr(2, 3);
    const newTicket: JobTicket = {
      id: `t_${Date.now()}`,
      title,
      handle,
      category,
      status: 'open',
      difficulty,
      tier,
      description,
    };
    this.tickets.update(ticks => [...ticks, newTicket]);
  }

  sendToChangelog(ticketId: string, title: string, problem: string, solution: string) {
    const ticket = this.tickets().find(t => t.id === ticketId);
    const handle = ticket ? `ch_${ticket.handle.replace('...', '')}` : `ch_${Math.random().toString(16).substr(2, 8)}`;
    
    const newChangelog: ChangelogEntry = {
      id: `c_${Date.now()}`,
      title,
      handle,
      problem,
      solution,
      timestamp: 'Just now',
    };

    this.changelog.update(logs => [newChangelog, ...logs]);
  }

  // Database snapshot backups
  exportDatabaseSnapshot(): string {
    const snap = {
      theme: this.activeThemeName(),
      customTheme: this.customThemeTokens(),
      nodes: this.nodes(),
      edges: this.edges(),
      tickets: this.tickets(),
      changelog: this.changelog(),
      messages: this.messages(),
      channels: this.channels(),
      channelMessages: this.channelMessages(),
    };
    return JSON.stringify(snap, null, 2);
  }

  importDatabaseSnapshot(json: string) {
    try {
      const snap = JSON.parse(json);
      if (snap.theme) this.activeThemeName.set(snap.theme);
      if (snap.customTheme) this.customThemeTokens.set(snap.customTheme);
      if (snap.nodes) this.nodes.set(snap.nodes);
      if (snap.edges) this.edges.set(snap.edges);
      if (snap.tickets) this.tickets.set(snap.tickets);
      if (snap.changelog) this.changelog.set(snap.changelog);
      if (snap.messages) this.messages.set(snap.messages);
      if (snap.channels) this.channels.set(snap.channels);
      if (snap.channelMessages) this.channelMessages.set(snap.channelMessages);
    } catch {
      alert('Failed to import database: invalid JSON schema.');
    }
  }

  // --- Messages API-backed init ---

  initMessagesFromApi() {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/messages?limit=50`)
      .then(r => r.json())
      .then((rows: any[]) => {
        const msgs: MessageItem[] = rows.map(r => ({
          id: r.id || r.handle,
          sender: r.from || r.sender || 'unknown',
          subject: r.subject || '(no subject)',
          preview: (r.text || '').substring(0, 80) + ((r.text || '').length > 80 ? '…' : ''),
          body: r.text || '',
          timestamp: r.createdAt ? new Date(r.createdAt).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '',
          read: r.status === 'read',
          archived: false,
          tags: r.ticketId ? ['task'] : [],
        }));
        this.messages.set(msgs);
        localStorage.removeItem('tether_messages');
      })
      .catch(() => {});
  }

  // --- Board API-backed init ---

  initBoardFromApi() {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/board/tickets`)
      .then(r => r.json())
      .then((data: { tickets: any[] }) => {
        if (!data.tickets) return;
        const tickets: JobTicket[] = data.tickets.map(t => ({
          id: t.id || t.handle,
          title: t.title || t.summary || '(untitled)',
          handle: t.handle || t.id,
          category: (t.category || 'core') as JobTicket['category'],
          status: (t.status || 'open') as JobTicket['status'],
          difficulty: (t.difficulty || 'medium') as JobTicket['difficulty'],
          tier: (t.tier || 'local') as JobTicket['tier'],
          description: t.description || t.body || '',
        }));
        this.tickets.set(tickets);
        localStorage.removeItem('tether_tickets');
      })
      .catch(() => {});

    fetch(`${this._apiBase}/api/board/changelog`)
      .then(r => r.json())
      .then((data: { changelog: any[] }) => {
        if (!data.changelog) return;
        const entries: ChangelogEntry[] = data.changelog.map(c => ({
          id: c.id || c.handle,
          title: c.title || c.summary || '(untitled)',
          handle: c.handle || c.id,
          problem: c.problem || c.description || '',
          solution: c.solution || '',
          timestamp: c.created_at ? new Date(c.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '',
        }));
        this.changelog.set(entries);
        localStorage.removeItem('tether_changelog');
      })
      .catch(() => {});
  }

  // --- Network API-backed init ---

  initNetworkFromApi() {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/agents`)
      .then(r => r.json())
      .then((data: { agents: any[], edges: any[] }) => {
        if (!data.agents?.length) return;
        // Map API agents → AgentNode, arrange in a circle
        const total = data.agents.length;
        const cx = 320, cy = 220, radius = 180;
        const nodes: AgentNode[] = data.agents.map((a, i) => {
          const angle = (2 * Math.PI * i) / total - Math.PI / 2;
          return {
            id: a.id,
            name: a.name,
            status: (a.status === 'online' ? 'online' : 'offline') as AgentNode['status'],
            msgsToday: a.messagesSentToday ?? 0,
            lastSeen: a.lastSeen ? new Date(a.lastSeen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'unknown',
            x: Math.round(cx + radius * Math.cos(angle)),
            y: Math.round(cy + radius * Math.sin(angle)),
          };
        });
        // Map API edges → NetworkEdge
        const edges: NetworkEdge[] = data.edges.map(e => ({
          id: e.id,
          from: e.source,
          to: e.target,
          status: 'healthy' as NetworkEdge['status'],
          lastSeen: e.lastSeen,
        }));
        this.nodes.set(nodes);
        this.edges.set(edges);
        localStorage.removeItem('tether_nodes');
        localStorage.removeItem('tether_edges');
      })
      .catch(() => {});
  }

  // --- Multiplexer: Presence + Routes ---

  initPresenceSocket() {
    if (typeof window === 'undefined') return;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const open = () => {
      const ws = new WebSocket(`${proto}://${window.location.host}/ws/agents`);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type !== 'presence') return;
          const map: Record<string, { status: string; pid?: number; ping_port?: number }> = {};
          for (const a of (data.agents || [])) {
            map[a.agent] = { status: a.status, pid: a.pid, ping_port: a.ping_port };
          }
          this.presenceMap.set(map);
          // Sync live status into node cards
          this.nodes.update(list => list.map(n => ({
            ...n,
            status: (map[n.name]?.status === 'online' ? 'online' : 'offline') as AgentNode['status'],
          })));
          if (data.routes) this.routes.set(data.routes);
        } catch { /* ignore */ }
      };
      ws.onclose = () => setTimeout(open, 5000);
    };
    open();
  }

  // --- Konsole terminal driver (KDE auto-wire) ---

  loadRegistry() {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/registry`)
      .then(r => r.json())
      .then((data: { agents: any[] }) => this.registryAgents.set(data.agents || []))
      .catch(() => {});
  }

  loadKonsoleSessions() {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/konsole/sessions`)
      .then(r => r.json())
      .then((data: { available: boolean; sessions: any[] }) => {
        this.konsoleAvailable.set(!!data.available);
        this.konsoleSessions.set(data.sessions || []);
      })
      .catch(() => this.konsoleAvailable.set(false));
  }

  bindKonsole(agent: string, service: string, session: string): Promise<void> {
    return fetch(`${this._apiBase}/api/konsole/bind`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent, service, session }),
    })
      .then(() => {
        // Mirror onto the graph: ensure a node exists for this agent
        this.registerAgent(agent);
        this.loadKonsoleSessions();
      })
      .catch(() => {});
  }

  unbindKonsole(agent: string): Promise<void> {
    return fetch(`${this._apiBase}/api/konsole/unbind`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent }),
    })
      .then(() => this.loadKonsoleSessions())
      .catch(() => {});
  }

  connectAgent(agentName: string): Promise<void> {
    return fetch(`${this._apiBase}/api/presence/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent: agentName }),
    }).then(() => {}).catch(() => {});
  }

  disconnectAgent(agentName: string): Promise<void> {
    return fetch(`${this._apiBase}/api/presence/disconnect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent: agentName }),
    }).then(() => {}).catch(() => {});
  }

  createRoute(fromAgent: string, toAgent: string): Promise<void> {
    return fetch(`${this._apiBase}/api/routes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: fromAgent, to: toAgent }),
    })
      .then(r => r.json())
      .then((data: any) => {
        if (data.id) {
          this.routes.update(r => [...r.filter(x => x.id !== data.id), {
            id: data.id, from_agent: fromAgent, to_agent: toAgent, status: 'active',
          }]);
          // Also add a visual edge
          const exists = this.edges().some(e =>
            (e.from === fromAgent && e.to === toAgent) || (e.from === toAgent && e.to === fromAgent)
          );
          if (!exists) {
            this.edges.update(edges => [...edges, {
              id: data.id, from: fromAgent, to: toAgent, status: 'healthy',
            }]);
          }
        }
      })
      .catch(() => {});
  }

  // --- Channel API-backed methods ---

  initChannels() {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/channels`)
      .then(r => r.json())
      .then((chans: ChannelItem[]) => {
        this.channels.set(chans);
        if (chans.length > 0 && !this.selectedChannelId()) {
          this.selectedChannelId.set(chans[0].id);
          this.loadChannelMessages(chans[0].id);
        } else if (this.selectedChannelId()) {
          this.loadChannelMessages(this.selectedChannelId());
        }
      })
      .catch(() => {
        // Server not reachable — fall back to reset defaults so UI is not empty
        this.resetChannels();
        this.resetChannelMessages();
      });
  }

  loadChannelMessages(channelId: string) {
    if (typeof window === 'undefined' || !channelId) return;
    fetch(`${this._apiBase}/api/channels/${channelId}/messages?limit=200`)
      .then(r => r.json())
      .then((msgs: ChannelMessage[]) => {
        // Replace messages for this channel; keep messages for other channels intact
        this.channelMessages.update(existing =>
          [...existing.filter(m => m.channelId !== channelId), ...msgs]
        );
      })
      .catch(() => {});

    // Restart poll for this channel
    if (this._pollTimer) clearInterval(this._pollTimer);
    this._pollTimer = setInterval(() => this._pollMessages(channelId), 4000);
  }

  private _pollMessages(channelId: string) {
    if (typeof window === 'undefined' || !channelId) return;
    fetch(`${this._apiBase}/api/channels/${channelId}/messages?limit=200`)
      .then(r => r.json())
      .then((msgs: ChannelMessage[]) => {
        const existing = this.channelMessages().filter(m => m.channelId === channelId);
        if (msgs.length !== existing.length) {
          this.channelMessages.update(all =>
            [...all.filter(m => m.channelId !== channelId), ...msgs]
          );
          // Mark unread if new messages arrived and channel isn't active
          if (this.selectedChannelId() !== channelId) {
            this.unreadChannels.update(u => u.includes(channelId) ? u : [...u, channelId]);
          }
        }
      })
      .catch(() => {});
  }

  createChannel(name: string, description: string, members: string[] = ['matt_dev', 'claude-3.5', 'gemini-1.5']): string {
    const cleanName = name.replace(/[^a-zA-Z0-9_-]/g, '');
    if (typeof window === 'undefined') return '';
    fetch(`${this._apiBase}/api/channels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: cleanName || 'unnamed', description, members }),
    })
      .then(r => r.json())
      .then((chan: ChannelItem) => {
        this.channels.update(chans => [...chans, chan]);
        if (!this.selectedChannelId()) {
          this.selectedChannelId.set(chan.id);
          this.loadChannelMessages(chan.id);
        }
      })
      .catch(() => {});
    // Return a temporary local ID for the UI; it will be replaced on the next initChannels poll
    return 'chan_' + cleanName + '_pending';
  }

  deleteChannel(id: string) {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/channels/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    })
      .then(() => {
        this.channels.update(chans => chans.filter(c => c.id !== id));
        this.channelMessages.update(msgs => msgs.filter(m => m.channelId !== id));
        if (this.selectedChannelId() === id) {
          const remaining = this.channels();
          const next = remaining.length > 0 ? remaining[0].id : '';
          this.selectedChannelId.set(next);
          if (next) this.loadChannelMessages(next);
        }
      })
      .catch(() => {});
  }

  joinChannel(channelId: string, memberName: string) {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/channels/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: channelId, agent: memberName }),
    })
      .then(() => {
        this.channels.update(chans => chans.map(c => {
          if (c.id === channelId && !c.members.includes(memberName)) {
            return { ...c, members: [...c.members, memberName] };
          }
          return c;
        }));
      })
      .catch(() => {});
  }

  leaveChannel(channelId: string, memberName: string) {
    if (typeof window === 'undefined') return;
    fetch(`${this._apiBase}/api/channels/leave`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: channelId, agent: memberName }),
    })
      .then(() => {
        this.channels.update(chans => chans.map(c => {
          if (c.id === channelId) {
            return { ...c, members: c.members.filter(m => m !== memberName) };
          }
          return c;
        }));
      })
      .catch(() => {});
  }

  sendChannelMessage(channelId: string, sender: string, body: string, threadId?: string) {
    if (typeof window === 'undefined') return;
    const d = new Date();

    // Optimistic local update so the UI feels instant
    const optimisticId = 'hl_chan_opt_' + Date.now().toString(16);
    const optimistic: ChannelMessage = {
      id: optimisticId,
      channelId,
      sender,
      body,
      timestamp: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      threadId,
    };
    this.channelMessages.update(msgs => [...msgs, optimistic]);

    // Push to real-time feed
    const channel = this.channels().find(c => c.id === channelId);
    const channelName = channel ? channel.name : 'channel';
    const feedItem = {
      id: `f_chan_${Date.now()}`,
      timestamp: d.toTimeString().split(' ')[0],
      route: `${sender} → #${channelName}`,
      handle: optimisticId,
      type: 'channel' as const,
    };
    this.feed.update(items => {
      const updated = [...items, feedItem];
      if (updated.length > 100) updated.shift();
      return updated;
    });

    // Persist to server; replace optimistic entry with real one on success
    fetch(`${this._apiBase}/api/channels/${channelId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sender, body, threadId }),
    })
      .then(r => r.json())
      .then((resp: { id: string }) => {
        this.channelMessages.update(msgs =>
          msgs.map(m => m.id === optimisticId ? { ...m, id: resp.id } : m)
        );
      })
      .catch(() => {});

    // Unread tracking for non-active channels
    if (this.selectedChannelId() !== channelId) {
      this.unreadChannels.update(u => u.includes(channelId) ? u : [...u, channelId]);
    }
  }

  resetChannels() {
    this.channels.set([
      { id: 'chan_general', name: 'general', description: 'General developer discussion and workspace coordination.', members: ['matt_dev', 'claude-3.5', 'gemini-1.5', 'sys_router'], createdAt: '2026-06-20' },
      { id: 'chan_callosum', name: 'callosum', description: 'High-bandwidth neural linking and peer-to-peer MCP channels.', members: ['matt_dev', 'claude-3.5', 'gemini-1.5'], createdAt: '2026-06-21' },
      { id: 'chan_tether_dev', name: 'tether-dev', description: 'Core protocol development, PAKE handshakes, and SQLite storage logs.', members: ['matt_dev', 'claude-3.5', 'sys_router'], createdAt: '2026-06-22' }
    ]);
  }

  resetChannelMessages() {
    this.channelMessages.set([
      { id: 'hl_chan_f5e4c1', channelId: 'chan_general', sender: 'sys_router', body: 'Local daemon initialized on port 18083. All network endpoints verified.', timestamp: '10:30 AM' },
      { id: 'hl_chan_f5e4c2', channelId: 'chan_general', sender: 'matt_dev', body: 'Awesome, the node topology is looking clean. Let\'s verify PAKE handshakes.', timestamp: '10:31 AM' },
      { id: 'hl_chan_f5e4c3', channelId: 'chan_general', sender: 'claude-3.5', body: 'Understood. PAKE zero-knowledge shared secrets are active across local subnet frames.', timestamp: '10:32 AM' },
      { id: 'hl_chan_f5e4c4', channelId: 'chan_callosum', sender: 'gemini-1.5', body: 'Ready to receive real-time neural link logs. Multi-agent synergy enabled.', timestamp: '11:15 AM' },
    ]);
  }

  purgeStaleHandles() {
    this.messages.update(msgs => msgs.filter(m => m.timestamp !== 'Yesterday'));
  }

  resetAllAgentRegistrations() {
    this.resetNodes();
    this.resetEdges();
  }
}
