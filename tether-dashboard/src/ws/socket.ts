import { useConnectionStore } from '../store/connectionStore';
import { useMessageStore } from '../store/messageStore';
import { useAgentStore } from '../store/agentStore';
import { useInboxStore } from '../store/inboxStore';
import { useAuthStore } from '../store/authStore';
import { api } from '../api/client';

let ws: WebSocket | null = null;
let pollInterval: ReturnType<typeof setInterval> | null = null;

export function connectWebSocket() {
  const token = useAuthStore.getState().token;
  if (!token) return;

  const { setConnected, resetReconnects, incrementReconnects } = useConnectionStore.getState();
  
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  startPolling();
  pollDashboardData()
    .then(() => {
      setConnected(true);
      resetReconnects();
    })
    .catch((err) => {
      console.warn("Dashboard data polling failed", err);
      setConnected(false);
      incrementReconnects();
    });
}

export function disconnectWebSocket() {
  if (ws) {
    ws.close();
    ws = null;
  }
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
  useConnectionStore.getState().setConnected(false);
}

function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(() => {
    pollDashboardData().catch((err) => {
      console.warn("Dashboard data polling failed", err);
      useConnectionStore.getState().setConnected(false);
      useConnectionStore.getState().incrementReconnects();
    });
  }, 5000);
}

async function pollDashboardData() {
  const [agentResponse, feed, inbox] = await Promise.all([
    api.getAgents(),
    api.getFeed(50),
    api.getInbox(),
  ]);
  useAgentStore.getState().setAgents(agentResponse.agents);
  useAgentStore.getState().setEdges(agentResponse.edges);
  useMessageStore.getState().setFeed(feed);
  useInboxStore.getState().setMessages(inbox);
  useConnectionStore.getState().setConnected(true);
  useConnectionStore.getState().resetReconnects();
}
