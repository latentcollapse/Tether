export interface InboxMessage {
  id: string;
  handle: string;
  from: string;
  to: string;
  subject: string;
  text: string;
  status: 'open' | 'read' | 'closed';
  createdAt: string;
  ticketId?: string;
}
