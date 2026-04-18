export interface MessageHandleData {
  kind: 'message';
  handle: string;
  table: string;
  fromAgent: string;
  toAgent: string;
  createdAt: string;
  status: 'open' | 'stale' | 'closed' | 'read';
  ticketId?: string;
  tags: string[];
  text?: string;
}

export interface InlineHandleData {
  kind: 'inline';
  handle: string;
  value: unknown;
}

export interface BlobHandleData {
  kind: 'blob';
  handle: string;
  contentType: string;
  bytesB64: string;
  sizeBytes: number;
}

export interface TreeHandleData {
  kind: 'tree';
  handle: string;
  handles: string[];
}

export type HandleLookupResult =
  | MessageHandleData
  | InlineHandleData
  | BlobHandleData
  | TreeHandleData;
