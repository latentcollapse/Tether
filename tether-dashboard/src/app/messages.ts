import {ChangeDetectionStrategy, Component, computed, inject, signal} from '@angular/core';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {TetherState, MessageItem} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

@Component({
  selector: 'app-messages',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, ReactiveFormsModule, LucideIcon],
  template: `
    <div class="flex flex-col h-full bg-[var(--bg-base)] text-[var(--text-primary)]" id="messages-root">
      <!-- Tabs Header -->
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-2 bg-[var(--bg-surface)]">
        <div class="flex space-x-2">
          <button
            id="tab-inbox"
            (click)="activeSubTab.set('inbox')"
            [class]="activeSubTab() === 'inbox'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Inbox
            @if (unreadCount() > 0) {
              <span class="ml-1 px-1.5 py-0.2 text-[9px] font-bold rounded-full bg-red-500 text-white">
                {{ unreadCount() > 99 ? '99+' : unreadCount() }}
              </span>
            }
          </button>
          <button
            id="tab-compose"
            (click)="activeSubTab.set('compose')"
            [class]="activeSubTab() === 'compose'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Compose
          </button>
          <button
            id="tab-search"
            (click)="activeSubTab.set('search')"
            [class]="activeSubTab() === 'search'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Search
          </button>
        </div>

        <div class="text-[11px] text-[var(--text-muted)] font-mono">
          Mail daemon connected to local queue
        </div>
      </div>

      <!-- Content Area -->
      <div class="flex-1 overflow-hidden relative flex">
        
        <!-- INBOX TAB -->
        @if (activeSubTab() === 'inbox') {
          <div class="flex-1 flex flex-col min-h-0 bg-[var(--bg-base)]">
            <!-- Batch Actions Bar -->
            @if (selectedIds().size > 0) {
              <div class="px-6 py-2 border-b border-[var(--border)] bg-[var(--accent-dim)] flex items-center justify-between" id="batch-actions-bar">
                <span class="text-xs font-medium text-[var(--accent)]">
                  {{ selectedIds().size }} messages selected
                </span>
                <div class="flex space-x-2">
                  <button 
                    (click)="batchMarkRead(true)"
                    class="px-2 py-1 text-[10px] font-medium rounded bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border)]"
                  >
                    Mark Read
                  </button>
                  <button 
                    (click)="batchMarkRead(false)"
                    class="px-2 py-1 text-[10px] font-medium rounded bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border)]"
                  >
                    Mark Unread
                  </button>
                  <button 
                    (click)="batchArchive()"
                    class="px-2 py-1 text-[10px] font-medium rounded bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border)]"
                  >
                    Archive
                  </button>
                  <button 
                    (click)="batchDelete()"
                    class="px-2 py-1 text-[10px] font-medium rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30"
                  >
                    Delete
                  </button>
                </div>
              </div>
            }

            <!-- Message List -->
            <div class="flex-1 overflow-y-auto min-h-0 divide-y divide-[var(--border)]/30">
              @if (nonArchivedMessages().length === 0) {
                <div class="p-12 text-center text-[var(--text-muted)] text-xs">
                  <lucide-icon name="mail" [size]="24" class="mx-auto mb-2 opacity-55"></lucide-icon>
                  Inbox is empty. Active network agents will post diagnostic payloads here.
                </div>
              } @else {
                @for (msg of nonArchivedMessages(); track msg.id) {
                  <div 
                    [class.bg-[var(--bg-elevated)]]="!msg.read"
                    [class.bg-[var(--bg-base)]]="msg.read"
                    class="flex items-start px-6 py-3 hover:bg-[var(--bg-elevated)]/50 cursor-pointer group transition-all"
                    (click)="openMessage(msg)"
                  >
                    <!-- Checkbox selection -->
                    <div class="pt-0.5 pr-3" (click)="$event.stopPropagation()">
                      <input 
                        type="checkbox" 
                        [checked]="selectedIds().has(msg.id)"
                        (change)="toggleSelect(msg.id)"
                        class="rounded border-[var(--border)] text-[var(--accent)] focus:ring-[var(--accent)]"
                      />
                    </div>

                    <!-- Read status dot -->
                    <div class="pt-1.5 pr-2">
                      <span 
                        class="inline-block w-1.5 h-1.5 rounded-full"
                        [class.bg-[var(--accent)]]="!msg.read"
                        [class.bg-transparent]="msg.read"
                      ></span>
                    </div>

                    <!-- Sender column -->
                    <div class="w-32 truncate text-xs font-semibold text-[var(--text-primary)] font-mono shrink-0">
                      {{ msg.sender }}
                    </div>

                    <!-- Subject + Preview body -->
                    <div class="flex-1 min-w-0 pr-4">
                      <div 
                        class="text-xs truncate text-[var(--text-primary)]"
                        [class.font-bold]="!msg.read"
                        [class.font-normal]="msg.read"
                      >
                        {{ msg.subject }}
                      </div>
                      <div class="text-[11px] text-[var(--text-muted)] truncate mt-0.5">
                        {{ msg.preview }}
                      </div>
                    </div>

                    <!-- Tags & Time -->
                    <div class="flex items-center space-x-2 shrink-0 self-start pt-0.5">
                      @for (tag of msg.tags; track tag) {
                        <span class="px-1.5 py-0.2 text-[8px] uppercase tracking-wider font-semibold rounded bg-[var(--border)] text-[var(--text-secondary)]">
                          {{ tag }}
                        </span>
                      }
                      <span class="text-[10px] text-[var(--text-muted)] font-mono">{{ msg.timestamp }}</span>
                    </div>
                  </div>
                }
              }
            </div>
          </div>
        }

        <!-- COMPOSE TAB -->
        @if (activeSubTab() === 'compose') {
          <div class="flex-1 p-6 overflow-y-auto bg-[var(--bg-base)]" id="compose-panel">
            <div class="max-w-2xl mx-auto p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
              <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-4">
                New Message
              </h3>

              <form [formGroup]="composeForm" (ngSubmit)="onComposeSubmit()" class="space-y-4">
                <!-- Recipient Selection -->
                <div class="relative">
                  <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium">To (Agent Selector)</label>
                  <select 
                    formControlName="to"
                    class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--border-strong)] focus:outline-none"
                  >
                    <option value="">Select Target Agent...</option>
                    @for (node of state.nodes(); track node.id) {
                      <option [value]="node.name">{{ node.name }}</option>
                    }
                  </select>
                  @if (composeForm.get('to')?.invalid && composeForm.get('to')?.touched) {
                    <span class="text-[9px] text-red-400 mt-1 block">A target agent is required.</span>
                  }
                </div>

                <!-- Subject -->
                <div>
                  <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium">Subject</label>
                  <input 
                    type="text"
                    formControlName="subject"
                    placeholder="Subject of the message..."
                    class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--border-strong)] focus:outline-none"
                  />
                  @if (composeForm.get('subject')?.invalid && composeForm.get('subject')?.touched) {
                    <span class="text-[9px] text-red-400 mt-1 block">Subject is required.</span>
                  }
                </div>

                <!-- Body Editor (Markdown preferred) -->
                <div>
                  <div class="flex justify-between items-center mb-1">
                    <label class="block text-[11px] text-[var(--text-secondary)] font-medium">Message Body</label>
                    <button 
                      type="button"
                      (click)="monoMode.set(!monoMode())"
                      class="text-[10px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center space-x-1"
                    >
                      <lucide-icon name="terminal" [size]="10"></lucide-icon>
                      <span>{{ monoMode() ? 'Monospace Enabled' : 'Standard Font' }}</span>
                    </button>
                  </div>
                  <textarea 
                    formControlName="body"
                    rows="8"
                    placeholder="Write your message here..."
                    [class.font-mono]="monoMode()"
                    class="w-full px-3 py-2 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--border-strong)] focus:outline-none"
                  ></textarea>
                  @if (composeForm.get('body')?.invalid && composeForm.get('body')?.touched) {
                    <span class="text-[9px] text-red-400 mt-1 block">Message body cannot be empty.</span>
                  }
                </div>

                <!-- Tags list -->
                <div>
                  <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium">Tags (Optional, comma-separated)</label>
                  <input 
                    type="text"
                    formControlName="tags"
                    placeholder="e.g. debug, p2p, sqlite"
                    class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--border-strong)] focus:outline-none"
                  />
                </div>

                <!-- Submit buttons -->
                <div class="flex justify-end pt-2 space-x-2">
                  <button 
                    type="button" 
                    (click)="composeForm.reset(); activeSubTab.set('inbox');"
                    class="px-3 py-1.5 text-xs font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    [disabled]="composeForm.invalid"
                    class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] disabled:opacity-50 hover:opacity-90 transition-opacity"
                  >
                    Send Message
                  </button>
                </div>
              </form>
            </div>
          </div>
        }

        <!-- SEARCH TAB -->
        @if (activeSubTab() === 'search') {
          <div class="flex-1 flex flex-col min-h-0 bg-[var(--bg-base)] p-6 overflow-hidden" id="search-panel">
            <!-- Search field -->
            <div class="mb-4 relative">
              <input 
                type="text"
                [value]="searchQuery()"
                (input)="onSearchInput($event)"
                placeholder="Search across all message headers, payloads, sender names..."
                class="w-full pl-9 pr-4 py-2 text-xs rounded border border-[var(--border)] bg-[var(--bg-surface)] text-[var(--text-primary)] focus:border-[var(--border-strong)] focus:outline-none"
              />
              <lucide-icon name="search" [size]="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"></lucide-icon>
            </div>

            <!-- Type Filters -->
            <div class="flex flex-wrap items-center gap-1.5 mb-4">
              <span class="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold mr-1">Filter type:</span>
              @for (filter of filters; track filter) {
                <button
                  (click)="activeFilter.set(filter)"
                  [class]="activeFilter() === filter 
                    ? 'px-2 py-0.5 text-[10px] font-medium rounded bg-[var(--accent)] text-[var(--bg-base)]'
                    : 'px-2 py-0.5 text-[10px] font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'"
                >
                  {{ filter }}
                </button>
              }
            </div>

            <!-- Results table -->
            <div class="flex-1 overflow-y-auto border border-[var(--border)] rounded-lg bg-[var(--bg-surface)] min-h-0">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="border-b border-[var(--border)] text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold bg-[var(--bg-base)]/50">
                    <th class="px-4 py-2">Type</th>
                    <th class="px-4 py-2">Sender / Node</th>
                    <th class="px-4 py-2">Subject / Headline</th>
                    <th class="px-4 py-2">Timestamp</th>
                    <th class="px-4 py-2 text-right">Age</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-[var(--border)]/20 text-xs">
                  @if (searchResults().length === 0) {
                    <tr>
                      <td colspan="5" class="px-4 py-8 text-center text-[var(--text-muted)]">
                        No results match your search term or chosen category filter.
                      </td>
                    </tr>
                  } @else {
                    @for (item of searchResults(); track item.id) {
                      <tr 
                        class="hover:bg-[var(--bg-elevated)]/30 cursor-pointer transition-colors"
                        (click)="openMessage(item)"
                      >
                        <td class="px-4 py-2.5">
                          <span class="px-1.5 py-0.2 text-[9px] font-medium rounded bg-purple-500/10 text-purple-400 uppercase">
                            {{ item.tags[0] || 'system' }}
                          </span>
                        </td>
                        <td class="px-4 py-2.5 font-mono text-[var(--text-secondary)]">
                          {{ item.sender }}
                        </td>
                        <td class="px-4 py-2.5 font-medium text-[var(--text-primary)] truncate max-w-xs">
                          {{ item.subject }}
                        </td>
                        <td class="px-4 py-2.5 text-[var(--text-muted)] font-mono">
                          {{ item.timestamp }}
                        </td>
                        <td class="px-4 py-2.5 text-right text-[var(--text-muted)]">
                          Active
                        </td>
                      </tr>
                    }
                  }
                </tbody>
              </table>
            </div>
          </div>
        }

        <!-- SLIDE-IN DETAIL PANEL -->
        @if (state.selectedMessage(); as activeMsg) {
          <div 
            class="absolute top-0 right-0 w-[420px] h-full bg-[var(--bg-surface)] border-l border-[var(--border)] shadow-2xl z-50 flex flex-col transition-all duration-300"
            id="message-detail-panel"
          >
            <!-- Header actions -->
            <div class="px-5 py-3 border-b border-[var(--border)] flex items-center justify-between bg-[var(--bg-base)]/40">
              <span class="text-[11px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">Message Detail</span>
              
              <div class="flex items-center space-x-2">
                <button 
                  (click)="state.archiveMessage(activeMsg.id)" 
                  class="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
                  title="Archive message"
                >
                  <lucide-icon name="archive" [size]="14"></lucide-icon>
                </button>
                <button 
                  (click)="deleteMessage(activeMsg.id)" 
                  class="p-1 rounded text-red-400 hover:bg-red-500/10"
                  title="Delete message"
                >
                  <lucide-icon name="trash" [size]="14"></lucide-icon>
                </button>
                <span class="h-4 w-px bg-[var(--border)]"></span>
                <button 
                  (click)="state.selectedMessage.set(null)" 
                  class="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  title="Close panel"
                >
                  <lucide-icon name="close" [size]="14"></lucide-icon>
                </button>
              </div>
            </div>

            <!-- Content Area -->
            <div class="flex-1 overflow-y-auto p-5 space-y-4">
              <div>
                <h2 class="text-sm font-bold text-[var(--text-primary)]">
                  {{ activeMsg.subject }}
                </h2>
                <div class="flex flex-wrap items-center gap-1.5 mt-2">
                  @for (tag of activeMsg.tags; track tag) {
                    <span class="px-1.5 py-0.2 text-[9px] rounded bg-[var(--border)] text-[var(--text-secondary)] uppercase">
                      {{ tag }}
                    </span>
                  }
                </div>
              </div>

              <!-- Meta data cards -->
              <div class="p-3 rounded-lg border border-[var(--border)] bg-[var(--bg-base)] text-xs space-y-1 font-mono">
                <div class="flex justify-between">
                  <span class="text-[var(--text-muted)]">From:</span>
                  <span class="text-[var(--text-secondary)] font-semibold">{{ activeMsg.sender }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-[var(--text-muted)]">Dispatched:</span>
                  <span class="text-[var(--text-secondary)]">{{ activeMsg.timestamp }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-[var(--text-muted)]">BLAKE3 Hash:</span>
                  <span class="text-[var(--text-primary)]">b3_{{ activeMsg.id.substring(2) }}f4e912</span>
                </div>
              </div>

              <!-- Message Body -->
              <div class="p-3.5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/30 text-xs text-[var(--text-primary)] font-sans whitespace-pre-wrap leading-relaxed">
                {{ activeMsg.body }}
              </div>
            </div>

            <!-- Action buttons footer -->
            <div class="p-4 border-t border-[var(--border)] bg-[var(--bg-base)]/40 flex justify-end space-x-2">
              <button 
                (click)="state.selectedMessage.set(null)"
                class="px-3 py-1.5 text-xs font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
              >
                Close
              </button>
              <button 
                (click)="triggerReply(activeMsg)"
                class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90"
              >
                Reply to Agent
              </button>
            </div>
          </div>
        }

      </div>
    </div>
  `,
})
export class Messages {
  state = inject(TetherState);
  activeSubTab = signal<'inbox' | 'compose' | 'search'>('inbox');
  monoMode = signal<boolean>(false);

  // Search query & filter state
  searchQuery = signal<string>('');
  activeFilter = signal<string>('ALL');
  filters = ['ALL', 'SYSTEM', 'TASKS', 'CRYPTO', 'BILLING'];

  // Checkbox message selections
  selectedIds = signal<Set<string>>(new Set());

  // Form Group
  composeForm = new FormGroup({
    to: new FormControl('', [Validators.required]),
    subject: new FormControl('', [Validators.required]),
    body: new FormControl('', [Validators.required]),
    tags: new FormControl(''),
  });

  // Filter messages for non-archived inbox list
  nonArchivedMessages = computed(() => {
    return this.state.messages().filter(m => !m.archived);
  });

  unreadCount = computed(() => {
    return this.nonArchivedMessages().filter(m => !m.read).length;
  });

  searchResults = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    const filter = this.activeFilter().toLowerCase();
    
    return this.state.messages().filter(m => {
      // Apply search query match
      const queryMatches = !query || 
        m.sender.toLowerCase().includes(query) ||
        m.subject.toLowerCase().includes(query) ||
        m.body.toLowerCase().includes(query);

      // Apply category filter match
      const filterMatches = filter === 'all' || 
        m.tags.some(t => t.toLowerCase() === filter);

      return queryMatches && filterMatches;
    });
  });

  toggleSelect(id: string) {
    this.selectedIds.update(set => {
      const next = new Set(set);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  batchMarkRead(read: boolean) {
    this.selectedIds().forEach(id => {
      this.state.markMessageRead(id, read);
    });
    this.selectedIds.set(new Set());
  }

  batchArchive() {
    this.selectedIds().forEach(id => {
      this.state.archiveMessage(id);
    });
    this.selectedIds.set(new Set());
  }

  batchDelete() {
    if (confirm(`Permanently delete the ${this.selectedIds().size} selected diagnostic payloads?`)) {
      this.selectedIds().forEach(id => {
        this.state.deleteMessage(id);
      });
      this.selectedIds.set(new Set());
    }
  }

  openMessage(msg: MessageItem) {
    this.state.markMessageRead(msg.id, true);
    this.state.selectedMessage.set(msg);
  }

  deleteMessage(id: string) {
    if (confirm('Delete this diagnostic payload from DB logs?')) {
      this.state.deleteMessage(id);
    }
  }

  triggerReply(msg: MessageItem) {
    this.state.selectedMessage.set(null);
    this.activeSubTab.set('compose');
    this.composeForm.patchValue({
      to: msg.sender,
      subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
      body: `\n\n--- On ${msg.timestamp}, ${msg.sender} wrote:\n> ${msg.preview}`,
    });
  }

  onSearchInput(event: Event) {
    const target = event.target as HTMLInputElement;
    this.searchQuery.set(target.value);
  }

  onComposeSubmit() {
    if (this.composeForm.invalid) return;
    
    const to = this.composeForm.value.to || '';
    const subject = this.composeForm.value.subject || '';
    const body = this.composeForm.value.body || '';
    const tags = this.composeForm.value.tags || '';

    this.state.sendMessage(to, subject, body, tags);
    this.composeForm.reset({ to: '', subject: '', body: '', tags: '' });
    this.activeSubTab.set('inbox');
  }
}
