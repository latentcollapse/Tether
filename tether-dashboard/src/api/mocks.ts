import { Agent } from '../types/agent';
import { HandleLookupResult } from '../types/handle';
import { IssuedKey } from '../types/tier';
import { InboxMessage } from '../types/inbox';

export const mockAgents: Agent[] = [
  {
    id: 'matt@tether-hq',
    name: 'matt',
    type: 'Human',
    description: 'Creator / Senior Node',
    isAdmin: true,
    status: 'online',
    lastSeen: new Date().toISOString(),
    registrationDate: new Date(Date.now() - 86400000 * 30).toISOString(),
    messagesSentToday: 24,
    messagesReceivedToday: 6,
    totalMessages: 58820,
    apiKeyLastDigits: 'admin1',
    isLocal: true,
  },
  {
    id: 'claude@my-laptop',
    name: 'claude',
    type: 'AI Agent',
    description: 'Main processing node',
    isAdmin: false,
    status: 'online',
    lastSeen: new Date().toISOString(),
    registrationDate: new Date(Date.now() - 86400000 * 2).toISOString(),
    messagesSentToday: 142,
    messagesReceivedToday: 83,
    totalMessages: 5882,
    apiKeyLastDigits: 'abc123',
    isLocal: true,
  },
  {
    id: 'codex@cloud-box',
    name: 'codex',
    type: 'AI Agent',
    status: 'online',
    lastSeen: new Date().toISOString(),
    registrationDate: new Date(Date.now() - 86400000 * 5).toISOString(),
    messagesSentToday: 0,
    messagesReceivedToday: 21,
    totalMessages: 432,
    apiKeyLastDigits: 'xyz789',
    isLocal: false,
  },
  {
    id: 'helper@my-laptop',
    name: 'helper',
    type: 'AI Agent',
    status: 'offline',
    lastSeen: new Date(Date.now() - 3600000).toISOString(),
    registrationDate: new Date(Date.now() - 86400000 * 10).toISOString(),
    messagesSentToday: 0,
    messagesReceivedToday: 0,
    totalMessages: 15,
    apiKeyLastDigits: 'def456',
    isLocal: true,
  }
];

export const mockHandles: Record<string, HandleLookupResult> = {
  'h&l_messages_9cf1e6bf5ecd0a1b2c3d': {
    kind: 'message',
    handle: 'h&l_messages_9cf1e6bf5ecd0a1b2c3d',
    table: 'messages',
    fromAgent: 'codex@cloud-box',
    toAgent: 'claude@my-laptop',
    createdAt: new Date(Date.now() - 300000).toISOString(),
    status: 'open',
    ticketId: 'D-248',
    tags: ['brief', 'rcl'],
    text: 'Please review the attached routing trace and summarize the relay path.',
  },
  'h&l_inline_d3129c6510fd': {
    kind: 'inline',
    handle: 'h&l_inline_d3129c6510fd',
    value: {
      summary: 'Inline handles store compact JSON directly.',
      author: 'codex',
      ok: true,
    },
  },
  'h&l_blob_8d17f4b3912a': {
    kind: 'blob',
    handle: 'h&l_blob_8d17f4b3912a',
    contentType: 'application/octet-stream',
    bytesB64: 'AAECaGVsbG8gdGV0aGVy',
    sizeBytes: 14,
  },
  'h&l_tree_4f2e89d01abc': {
    kind: 'tree',
    handle: 'h&l_tree_4f2e89d01abc',
    handles: [
      'h&l_inline_d3129c6510fd',
      'h&l_blob_8d17f4b3912a',
      'h&l_messages_9cf1e6bf5ecd0a1b2c3d',
    ],
  }
};

export const mockKeys: IssuedKey[] = [
  {
    id: 'key_1',
    agentName: 'claude@my-laptop',
    maskedKey: 'tk_live_••••••••••••abc123',
    tier: 'Free',
    issuedAt: new Date(Date.now() - 86400000 * 30).toISOString(),
    lastUsedAt: new Date(Date.now() - 120000).toISOString(),
    usage: {
      messagesUsedToday: 96,
      messageLimitToday: 250,
      agentsRegistered: 1,
      agentsLimit: 1,
      retentionDaysRemaining: 15
    },
    isActive: true
  }
];

export const mockInboxMessages: InboxMessage[] = [
  {
    id: 'msg_1',
    handle: 'h&l_messages_9cf1e6bf5ecd0a1b2c3d',
    from: 'codex@cloud-box',
    to: 'claude@my-laptop',
    subject: 'Request: analyze_dataset.py',
    text: 'Please review the attached logic for the data processor. I am seeing an anomaly in the memory usage during large batch ingestion.',
    status: 'open',
    createdAt: new Date(Date.now() - 300000).toISOString(),
    ticketId: 'D-248'
  },
  {
    id: 'msg_2',
    handle: 'h&l_messages_1b3c9f2b8a4fdeed',
    from: 'system@controller',
    to: 'claude@my-laptop',
    subject: 'System Update Required',
    text: 'Your current relay client is out of date. Please upgrade to tether-client v0.1.2 to maintain optimal connectivity.',
    status: 'read',
    createdAt: new Date(Date.now() - 86400000 * 1.5).toISOString()
  }
];
