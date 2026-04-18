import { useAuthStore } from '../store/authStore';
import { mockAgents, mockHandles, mockKeys, mockInboxMessages } from './mocks';
import { Agent } from '../types/agent';
import { HandleLookupResult } from '../types/handle';
import { useAgentStore } from '../store/agentStore';
import { HEALTH_URL } from '../utils/constants';

// Fake delay for realism
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

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
    await delay(300);
    return mockAgents;
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
    await delay(200);
    // Find matching handle by prefix
    const handleKey = Object.keys(mockHandles).find(k => k.startsWith(hash) || k === hash);
    if (handleKey) return mockHandles[handleKey];
    throw new Error("Handle not found");
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
    await delay(300);
    return mockInboxMessages;
  }

  async sendMessage(payload: { to: string; subject: string; text: string; ticketId?: string }): Promise<{ handle: string }> {
    this.validateSession();
    await delay(500);
    const hash = 'h&l_messages_' + Math.random().toString(16).substring(2, 14) + Math.random().toString(16).substring(2, 14);
    return { handle: hash };
  }
}

export const api = new ApiClient();
