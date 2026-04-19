export interface Agent {
  id: string; // The @ name
  name: string; // Simple name
  type?: 'AI Agent' | 'Human';
  description?: string;
  isAdmin?: boolean;
  status: 'online' | 'offline' | 'idle';
  lastSeen: string;
  registrationDate: string;
  messagesSentToday: number;
  messagesReceivedToday: number;
  totalMessages: number;
  apiKeyLastDigits: string;
  isLocal: boolean;
}

export interface AgentEdge {
  id: string;
  source: string;
  target: string;
  count: number;
  todayCount: number;
  lastSeen: string;
}

export interface AgentResponse {
  agents: Agent[];
  edges: AgentEdge[];
}
