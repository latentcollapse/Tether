import { useAuthStore } from '../store/authStore';
import { mockKeys } from './mocks';
import { Agent, AgentResponse } from '../types/agent';
import { HandleListResponse, HandleLookupResult } from '../types/handle';
import { useAgentStore } from '../store/agentStore';
import { FeedItem } from '../types/message';
import { InboxMessage } from '../types/inbox';
import { API_BASE_URL, HEALTH_URL } from '../utils/constants';

// Fake delay for realism
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

class ApiClient {
  private validateSession() {
    const token = useAuthStore.getState().token;
    if (!token) throw new Error("Unauthorized");
  }

  async login(apiKey: string): Promise<{ token: string, isAdmin: boolean }> {
    await delay(600);
    if (!apiKey || apiKey.length < 10) throw new Error("Invalid key");
    // Hardcode an easy check to demo the admin tools
    const isAdmin = apiKey.includes('admin') || apiKey.includes('senior');
    return { token: "sess_" + Date.now().toString(), isAdmin };
  }

  async getHealth() {
    const response = await fetch(HEALTH_URL, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    return response.json();
  }

  async getAgents() {
    this.validateSession();
    return fetchJson<AgentResponse>('/agents');
  }

  async registerAgent(payload: { name: string; type: string; machineLabel?: string; description?: string }): Promise<{ key: string; agent: Agent }> {
    this.validateSession();
    await delay(600);
    const machine = payload.machineLabel ? payload.machineLabel.toLowerCase().replace(/\s+/g, '-') : 'local';
    const agent: Agent = {
      id: `${payload.name.toLowerCase().replace(/\s+/g, '-')}@${machine}`,
      name: payload.name,
      type: payload.type as 'AI Agent' | 'Human',
      description: payload.description,
      status: 'online',
      lastSeen: new Date().toISOString(),
      registrationDate: new Date().toISOString(),
      messagesSentToday: 0,
      messagesReceivedToday: 0,
      totalMessages: 0,
      apiKeyLastDigits: Math.random().toString().slice(2, 8),
      isLocal: true,
    };
    useAgentStore.getState().upsertAgent(agent);
    return { 
      key: `tk_live_${Math.random().toString(36).substring(2)}${Math.random().toString(36).substring(2)}`,
      agent 
    };
  }

  async getHandle(hash: string): Promise<HandleLookupResult> {
    this.validateSession();
    return fetchJson<HandleLookupResult>(`/handles/${encodeURIComponent(hash)}`);
  }

  async getHandles(limit = 100, offset = 0): Promise<HandleListResponse> {
    this.validateSession();
    return fetchJson<HandleListResponse>(`/handles?limit=${limit}&offset=${offset}`);
  }

  async getStats(): Promise<{ messages: number; agents: number; handles: number }> {
    this.validateSession();
    return fetchJson('/stats');
  }

  async getFeed(limit = 50): Promise<FeedItem[]> {
    this.validateSession();
    return fetchJson<FeedItem[]>(`/feed?limit=${limit}`);
  }

  async getKeys() {
    this.validateSession();
    await delay(400);
    return mockKeys;
  }
  
  async revokeKey(keyId: string) {
    this.validateSession();
    await delay(500);
    return { success: true };
  }

  async getInbox() {
    this.validateSession();
    return fetchJson<InboxMessage[]>('/messages?limit=100');
  }

  async sendMessage(payload: { to: string; subject: string; text: string; ticketId?: string }): Promise<{ handle: string }> {
    this.validateSession();
    return fetchJson<{ handle: string }>('/messages', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

export const api = new ApiClient();
