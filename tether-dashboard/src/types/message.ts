export interface MessageEvent {
  id: string;
  timestamp: string; // ISO Date String
  from: string;
  to: string;
  handle: string;
  ticketId?: string;
}

export type FeedItem = MessageEvent;
