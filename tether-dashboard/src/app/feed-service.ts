import { Injectable, inject } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { TetherState, FeedItem } from './tether-state';

@Injectable({
  providedIn: 'root'
})
export class FeedService {
  private state = inject(TetherState);
  private eventSubject = new BehaviorSubject<FeedItem[]>([]);
  events$ = this.eventSubject.asObservable();
  private ws?: WebSocket;

  constructor() {
    if (typeof window === 'undefined') return;

    // Boot from REST so the feed is populated immediately on load
    fetch('/api/feed?limit=50')
      .then(r => r.json())
      .then((rows: any[]) => {
        const items: FeedItem[] = rows.map(r => this._rowToItem(r)).reverse();
        this.eventSubject.next(items);
        this.state.feed.set(items);
      })
      .catch(() => {})
      .finally(() => this._openSocket());
  }

  private _openSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${window.location.host}/ws/feed`;
    this.ws = new WebSocket(url);

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type !== 'feed' || !data.items?.length) return;

        const newItems: FeedItem[] = data.items.map((r: any) => this._rowToItem(r));
        const existing = this.eventSubject.value;

        // First WS message is the seed batch — skip items already in the list from REST boot
        const existingIds = new Set(existing.map(i => i.id));
        const fresh = newItems.filter(i => !existingIds.has(i.id));
        if (!fresh.length) return;

        const updated = [...existing, ...fresh];
        if (updated.length > 200) updated.splice(0, updated.length - 200);

        this.eventSubject.next(updated);
        this.state.feed.set(updated);

        // Keep msgsToday in sync for nodes that appear in new items
        const activeNames = new Set(fresh.flatMap(i => i.route.split(' → ')));
        this.state.nodes.update(list =>
          list.map(n => activeNames.has(n.name)
            ? { ...n, msgsToday: n.msgsToday + 1, lastSeen: 'just now' }
            : n
          )
        );
      } catch { /* ignore parse errors */ }
    };

    this.ws.onclose = () => {
      // Reconnect after 3s on unexpected close
      setTimeout(() => this._openSocket(), 3000);
    };
  }

  private _rowToItem(r: any): FeedItem {
    const tableMap: Record<string, FeedItem['type']> = {
      messages: 'messages',
      tickets: 'task',
      changelog: 'board',
    };
    return {
      id: r.id || r.handle,
      timestamp: r.timestamp
        ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        : '',
      route: `${r.from || r.sender || '?'} → ${r.to || r.table || '?'}`,
      handle: r.handle,
      type: tableMap[r.table] ?? 'whiteboard',
    };
  }

  pushEvent(event: FeedItem) {
    const current = this.eventSubject.value;
    const updated = [...current, event];
    if (updated.length > 200) updated.shift();
    this.eventSubject.next(updated);
    this.state.feed.set(updated);
  }
}
