import { useConnectionStore } from '../store/connectionStore';
import { useMessageStore } from '../store/messageStore';
import { useAgentStore } from '../store/agentStore';
import { useAuthStore } from '../store/authStore';
import { WS_URL } from '../utils/constants';
import { mockAgents } from '../api/mocks';

// The relay uses a real WebSocket, but since backend isn't ready, we'll mock it if it fails to connect.
let ws: WebSocket | null = null;
let reconnectTimer: any = null;
let mockInterval: any = null;

export function connectWebSocket() {
  const token = useAuthStore.getState().token;
  if (!token) return;

  const { isConnected, setConnected, incrementReconnects, resetReconnects, reconnectAttempts } = useConnectionStore.getState();
  
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    // In a real environment, this connects to the python relay.
    // ws = new WebSocket(`${WS_URL}?token=${token}`);
    
    // For AI Studio environment without the physical relay port available, 
    // we bypass it and immediately trigger mock mode.
    throw new Error("Local mock mode active");

  } catch (err) {
    console.warn("WebSocket fallback to local simulation", err);
    startMockSimulation();
    setConnected(true);
    resetReconnects();
  }
}

export function disconnectWebSocket() {
  if (ws) {
    ws.close();
    ws = null;
  }
  if (mockInterval) {
    clearInterval(mockInterval);
    mockInterval = null;
  }
  useConnectionStore.getState().setConnected(false);
}

function startMockSimulation() {
  if (mockInterval) clearInterval(mockInterval);
  
  // Seed initial agents
  useAgentStore.getState().setAgents(mockAgents);

  mockInterval = setInterval(() => {
    const paused = useMessageStore.getState().isPaused;
    if (paused) return;

    // Simulate random routing event
    const froms = ['claude', 'codex', 'helper'];
    const tos = ['claude', 'codex', 'system'];
    const from = froms[Math.floor(Math.random() * froms.length)] + '@my-laptop';
    const to = tos[Math.floor(Math.random() * tos.length)] + (Math.random() > 0.5 ? '@cloud-box' : '@my-laptop');
    if (from === to) return;

    const hash = 'h&l_messages_' + Math.random().toString(16).substring(2, 14) + Math.random().toString(16).substring(2, 14);
    
    useMessageStore.getState().addMessage({
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      from,
      to,
      handle: hash,
      ticketId: Math.random() > 0.7 ? `D-${Math.floor(Math.random() * 900) + 100}` : undefined
    });

  }, 1200);
}
