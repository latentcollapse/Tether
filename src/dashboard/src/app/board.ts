import {ChangeDetectionStrategy, Component, computed, inject, signal} from '@angular/core';
import {FormControl, FormGroup, FormsModule, ReactiveFormsModule, Validators} from '@angular/forms';
import {TetherState, JobTicket} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

@Component({
  selector: 'app-board',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, ReactiveFormsModule, FormsModule, LucideIcon],
  template: `
    <div class="flex flex-col h-full bg-[var(--bg-base)] text-[var(--text-primary)]" id="board-root">
      <!-- Header / Filter bar -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border)] px-6 py-3 bg-[var(--bg-surface)]">
        <div class="flex items-center space-x-3">
          <div class="flex rounded-lg border border-[var(--border)] p-0.5 bg-[var(--bg-base)] shrink-0">
            <button
              (click)="viewMode.set('grid')"
              [class]="viewMode() === 'grid' ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)] font-medium' : 'text-[var(--text-secondary)]'"
              class="px-2.5 py-1 text-xs rounded-md transition-colors"
            >
              Card Grid
            </button>
            <button
              (click)="viewMode.set('dag')"
              [class]="viewMode() === 'dag' ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)] font-medium' : 'text-[var(--text-secondary)]'"
              class="px-2.5 py-1 text-xs rounded-md transition-colors"
            >
              Dependency DAG
            </button>
          </div>

          <!-- Board Summary Widget -->
          <div class="hidden md:flex items-center space-x-2 text-[11px] font-mono border-l border-[var(--border)] pl-3 text-[var(--text-muted)]">
            <span>Summary:</span>
            <span class="text-[var(--text-primary)]">O:{{ counts().open }}</span>
            <span class="text-amber-400">A:{{ counts().active }}</span>
            <span class="text-emerald-400">R:{{ counts().ready }}</span>
            <span class="text-blue-400">C:{{ counts().completed }}</span>
          </div>
        </div>

        <!-- Filter bar -->
        <div class="flex flex-wrap items-center gap-2">
          <select 
            [(ngModel)]="filterCategory" 
            class="px-2.5 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
            title="Filter by category"
          >
            <option value="all">All Categories</option>
            <option value="core">Core Kernel</option>
            <option value="p2p">P2P Protocols</option>
            <option value="crypto">Cryptography</option>
            <option value="ui">User Interface</option>
            <option value="agent">Agent Models</option>
          </select>

          <select 
            [(ngModel)]="filterTier" 
            class="px-2.5 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
            title="Filter by tier"
          >
            <option value="all">All Tiers</option>
            <option value="local">local</option>
            <option value="relay">relay</option>
            <option value="cloud">cloud</option>
          </select>

          <button 
            (click)="showCreateModal.set(true)"
            class="px-3 py-1 text-xs font-semibold rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90 flex items-center space-x-1"
          >
            <lucide-icon name="plus" [size]="12"></lucide-icon>
            <span>Create Ticket</span>
          </button>
        </div>
      </div>

      <!-- Split Layout: Tasks Area and Scratchpad Sidebar -->
      <div class="flex-1 flex overflow-hidden min-h-0">
        
        <!-- Tasks viewport -->
        <div class="flex-1 p-6 overflow-y-auto min-h-0">
          
          <!-- GRID KANBAN MODE -->
          @if (viewMode() === 'grid') {
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="kanban-columns">
              <!-- OPEN COLUMN -->
              <div class="flex flex-col min-h-[300px]">
                <div class="flex items-center justify-between mb-3 border-b border-[var(--border)] pb-2 px-1">
                  <span class="text-xs font-semibold text-[var(--text-secondary)] uppercase">Open</span>
                  <span class="px-2 py-0.5 text-[10px] rounded-full font-mono bg-[var(--bg-surface)] text-[var(--text-muted)]">{{ openTickets().length }}</span>
                </div>
                <div class="space-y-3 flex-1">
                  @for (t of openTickets(); track t.id) {
                    <ng-container *ngTemplateOutlet="cardTemplate; context: { $implicit: t }"></ng-container>
                  }
                  @if (openTickets().length === 0) {
                    <div class="border-2 border-dashed border-[var(--border)]/20 rounded-xl p-6 text-center text-xs text-[var(--text-muted)]">No open tickets.</div>
                  }
                </div>
              </div>

              <!-- ACTIVE COLUMN -->
              <div class="flex flex-col min-h-[300px]">
                <div class="flex items-center justify-between mb-3 border-b border-[var(--border)] pb-2 px-1">
                  <span class="text-xs font-semibold text-amber-500 uppercase">Active</span>
                  <span class="px-2 py-0.5 text-[10px] rounded-full font-mono bg-[var(--bg-surface)] text-amber-500/20">{{ activeTickets().length }}</span>
                </div>
                <div class="space-y-3 flex-1">
                  @for (t of activeTickets(); track t.id) {
                    <ng-container *ngTemplateOutlet="cardTemplate; context: { $implicit: t }"></ng-container>
                  }
                  @if (activeTickets().length === 0) {
                    <div class="border-2 border-dashed border-[var(--border)]/20 rounded-xl p-6 text-center text-xs text-[var(--text-muted)]">No active threads.</div>
                  }
                </div>
              </div>

              <!-- READY COLUMN -->
              <div class="flex flex-col min-h-[300px]">
                <div class="flex items-center justify-between mb-3 border-b border-[var(--border)] pb-2 px-1">
                  <span class="text-xs font-semibold text-emerald-500 uppercase">Ready</span>
                  <span class="px-2 py-0.5 text-[10px] rounded-full font-mono bg-[var(--bg-surface)] text-emerald-500/20">{{ readyTickets().length }}</span>
                </div>
                <div class="space-y-3 flex-1">
                  @for (t of readyTickets(); track t.id) {
                    <ng-container *ngTemplateOutlet="cardTemplate; context: { $implicit: t }"></ng-container>
                  }
                  @if (readyTickets().length === 0) {
                    <div class="border-2 border-dashed border-[var(--border)]/20 rounded-xl p-6 text-center text-xs text-[var(--text-muted)]">None in validation stage.</div>
                  }
                </div>
              </div>

              <!-- COMPLETED COLUMN -->
              <div class="flex flex-col min-h-[300px]">
                <div class="flex items-center justify-between mb-3 border-b border-[var(--border)] pb-2 px-1">
                  <span class="text-xs font-semibold text-blue-500 uppercase">Completed</span>
                  <span class="px-2 py-0.5 text-[10px] rounded-full font-mono bg-[var(--bg-surface)] text-blue-500/20">{{ completedTickets().length }}</span>
                </div>
                <div class="space-y-3 flex-1">
                  @for (t of completedTickets(); track t.id) {
                    <ng-container *ngTemplateOutlet="cardTemplate; context: { $implicit: t }"></ng-container>
                  }
                  @if (completedTickets().length === 0) {
                    <div class="border-2 border-dashed border-[var(--border)]/20 rounded-xl p-6 text-center text-xs text-[var(--text-muted)]">No resolved blocks yet.</div>
                  }
                </div>
              </div>
            </div>
          }

          <!-- DEPENDENCY DAG GRAPH MODE -->
          @if (viewMode() === 'dag') {
            <div class="w-full h-full min-h-[460px] relative border border-[var(--border)] rounded-xl bg-[var(--bg-surface)] p-6 overflow-hidden flex flex-col justify-between animate-fade-in" id="dag-viewport">
              <div class="text-[10px] uppercase font-bold tracking-wider text-[var(--text-muted)] font-mono flex items-center space-x-1">
                <span class="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse"></span>
                <span>Tether Block Dependency Tree (Pre-requisites)</span>
              </div>
              
              <!-- Interactive SVG canvas for blocks -->
              <div class="flex-1 relative py-8 px-12 flex flex-col justify-between items-center min-h-[380px]">
                
                <!-- SVG Connections layer with Bezier Curves and Arrowheads -->
                <svg class="absolute inset-0 w-full h-full pointer-events-none">
                  <defs>
                    <marker id="arrow-accent" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                      <path d="M 0 2 L 8 5 L 0 8 z" fill="var(--accent)" />
                    </marker>
                    <marker id="arrow-border" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                      <path d="M 0 2 L 8 5 L 0 8 z" fill="var(--border)" />
                    </marker>
                  </defs>
                  
                  <!-- Top Center (50%, 25%) to Left Mid (25%, 52%) -->
                  <path d="M 50% 25% C 50% 38%, 25% 38%, 25% 48%" stroke="var(--accent)" stroke-width="1.5" fill="none" marker-end="url(#arrow-accent)" stroke-dasharray="3 3"></path>
                  
                  <!-- Top Center (50%, 25%) to Right Mid (75%, 52%) -->
                  <path d="M 50% 25% C 50% 38%, 75% 38%, 75% 48%" stroke="var(--accent)" stroke-width="1.5" fill="none" marker-end="url(#arrow-accent)"></path>
                  
                  <!-- Left Mid (25%, 58%) to Bottom Center (50%, 78%) -->
                  <path d="M 25% 58% C 25% 70%, 50% 70%, 50% 77%" stroke="var(--border)" stroke-width="1.5" fill="none" marker-end="url(#arrow-border)"></path>
                  
                  <!-- Right Mid (75%, 58%) to Bottom Center (50%, 78%) -->
                  <path d="M 75% 58% C 75% 70%, 50% 70%, 50% 77%" stroke="var(--border)" stroke-width="1.5" fill="none" marker-end="url(#arrow-border)"></path>
                </svg>

                <!-- Row 1: Core Base Core -->
                <div class="z-20">
                  <div class="px-5 py-3 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-elevated)] shadow-md text-center text-xs min-w-[160px] transition-transform hover:scale-105 duration-200">
                    <span class="block font-bold text-[var(--text-primary)] font-mono">BLAKE3 Core Queue</span>
                    <span class="text-[9px] text-[var(--text-muted)] font-mono mt-0.5 block uppercase font-semibold">Completed</span>
                  </div>
                </div>

                <!-- Row 2: Secondary dependencies -->
                <div class="flex justify-between w-full max-w-lg z-20">
                  <div class="px-5 py-3 rounded-lg border border-yellow-500 bg-[var(--bg-elevated)] shadow-md text-center text-xs min-w-[160px] transition-transform hover:scale-105 duration-200">
                    <span class="block font-bold text-[var(--text-primary)] font-mono">Subnet Discovery</span>
                    <span class="text-[9px] text-yellow-500 font-mono mt-0.5 block uppercase font-semibold">PAKE pending</span>
                  </div>
                  <div class="px-5 py-3 rounded-lg border border-emerald-500 bg-[var(--bg-elevated)] shadow-md text-center text-xs min-w-[160px] transition-transform hover:scale-105 duration-200">
                    <span class="block font-bold text-[var(--text-primary)] font-mono">SQLite Block Cache</span>
                    <span class="text-[9px] text-emerald-500 font-mono mt-0.5 block uppercase font-semibold">Ready state</span>
                  </div>
                </div>

                <!-- Row 3: Target block -->
                <div class="z-20">
                  <div class="px-5 py-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] shadow-md text-center text-xs min-w-[160px] transition-transform hover:scale-105 duration-200">
                    <span class="block font-bold text-[var(--text-secondary)] font-mono">UI Graph Re-bounds</span>
                    <span class="text-[9px] text-[var(--text-muted)] font-mono mt-0.5 block uppercase font-semibold">Not started</span>
                  </div>
                </div>
              </div>

              <!-- Legend info -->
              <div class="flex space-x-4 border-t border-[var(--border)]/40 pt-2 text-[10px] text-[var(--text-muted)] font-mono">
                <span class="flex items-center"><span class="w-2 h-2 rounded bg-[var(--border-strong)] mr-1.5"></span> Base Node</span>
                <span class="flex items-center"><span class="w-2 h-2 rounded bg-yellow-500 mr-1.5"></span> Degraded / Pending</span>
                <span class="flex items-center"><span class="w-2 h-2 rounded bg-emerald-500 mr-1.5"></span> Handshake Ready</span>
              </div>
            </div>
          }

        </div>

        <!-- WHITEBOARD SIDEBAR -->
        <div class="w-[300px] border-l border-[var(--border)] bg-[var(--bg-surface)] flex flex-col h-full overflow-hidden" id="scratchpad-sidebar">
          <div class="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <lucide-icon name="board" [size]="14"></lucide-icon>
              <h3 class="text-xs font-semibold uppercase tracking-wider text-[var(--text-primary)]">Scratchpad</h3>
            </div>
            <span class="text-[9px] font-mono text-[var(--text-muted)]">Auto-saved</span>
          </div>

          <!-- Plain text scratchpad textarea -->
          <div class="flex-1 p-3 flex flex-col">
            <textarea
              [(ngModel)]="state.whiteboardText"
              [ngModelOptions]="{standalone: true}"
              class="flex-1 w-full p-2.5 text-[11px] font-mono rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none resize-none leading-relaxed"
              placeholder="Jot down notes, snippets, task assignments, or connection logs here. Syncs instantly in localStorage across tabs."
            ></textarea>
          </div>
        </div>

      </div>

      <!-- CARD COMPONENT TEMPLATE -->
      <ng-template #cardTemplate let-t>
        <div 
          class="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] hover:border-[var(--border-strong)]/40 transition-all cursor-pointer shadow-xs space-y-2.5"
          (click)="openTicketDetails(t)"
        >
          <div class="flex items-center justify-between">
            <span 
              class="px-1.5 py-0.2 rounded text-[8px] font-semibold uppercase font-mono"
              [class.bg-purple-500/10]="t.category === 'crypto' || t.category === 'p2p'"
              [class.text-purple-400]="t.category === 'crypto' || t.category === 'p2p'"
              [class.bg-blue-500/10]="t.category === 'ui'"
              [class.text-blue-400]="t.category === 'ui'"
              [class.bg-emerald-500/10]="t.category === 'core' || t.category === 'agent'"
              [class.text-emerald-400]="t.category === 'core' || t.category === 'agent'"
            >
              {{ t.category }}
            </span>

            <span class="text-[10px] text-[var(--text-muted)] font-mono truncate max-w-[80px]" [title]="t.handle">
              {{ t.handle }}
            </span>
          </div>

          <h4 class="text-xs font-semibold text-[var(--text-primary)] leading-snug">
            {{ t.title }}
          </h4>

          <div class="flex items-center justify-between pt-1 border-t border-[var(--border)]/20 text-[10px]">
            <span 
              class="font-mono flex items-center space-x-1"
              [class.text-red-400]="t.difficulty === 'high'"
              [class.text-yellow-500]="t.difficulty === 'medium'"
              [class.text-[var(--text-muted)]]="t.difficulty === 'low'"
            >
              <span class="inline-block w-1.5 h-1.5 rounded-full bg-current"></span>
              <span>{{ t.difficulty }}</span>
            </span>

            <span class="text-[var(--text-muted)] font-medium">
              tier: <span class="text-[var(--text-secondary)] font-mono">{{ t.tier }}</span>
            </span>
          </div>
        </div>
      </ng-template>

      <!-- TICKET DETAILS OVERLAY / SIDE PANEL -->
      @if (selectedTicket()) {
        @let t = selectedTicket()!;
        <div class="fixed inset-0 bg-black/60 backdrop-blur-xs z-[90] flex items-center justify-center p-4" id="ticket-detail-overlay">
          <div class="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl max-w-md w-full p-5 shadow-2xl space-y-4">
            <div class="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
              <span class="text-[10px] font-mono text-[var(--text-muted)]">TICKET #{{ t.handle }}</span>
              <button (click)="selectedTicket.set(null)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <lucide-icon name="close" [size]="14"></lucide-icon>
              </button>
            </div>

            <div class="space-y-3">
              <h3 class="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">{{ t.title }}</h3>
              <div class="grid grid-cols-2 gap-2 text-[11px] font-mono text-[var(--text-secondary)] bg-[var(--bg-base)] p-3 rounded border border-[var(--border)]">
                <div>Category: <span class="text-[var(--text-primary)] uppercase">{{ t.category }}</span></div>
                <div>Difficulty: <span class="text-[var(--text-primary)] uppercase">{{ t.difficulty }}</span></div>
                <div>Deployment: <span class="text-[var(--text-primary)] lowercase">{{ t.tier }}</span></div>
                <div>Status: <span class="text-[var(--text-primary)] uppercase">{{ t.status }}</span></div>
              </div>

              <div class="space-y-1">
                <span class="block text-[10px] text-[var(--text-muted)] font-bold uppercase">Description</span>
                <p class="text-xs text-[var(--text-secondary)] leading-relaxed bg-[var(--bg-elevated)]/30 p-2.5 rounded border border-[var(--border)]/40 whitespace-pre-wrap">
                  {{ t.description }}
                </p>
              </div>
            </div>

            <!-- Buttons: Send To Changelog / Actions -->
            <div class="flex items-center justify-between pt-2 border-t border-[var(--border)]/30">
              <button 
                (click)="openChangelogModal(t)"
                class="px-2.5 py-1 text-[11px] font-medium rounded border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 flex items-center space-x-1"
                title="Publish ticket as changelog audit block"
              >
                <lucide-icon name="changelog" [size]="12"></lucide-icon>
                <span>Send to Changelog</span>
              </button>

              <div class="flex space-x-2">
                @if (t.status !== 'completed') {
                  <button 
                    (click)="promoteStatus(t)"
                    class="px-3 py-1 text-[11px] font-semibold rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-95"
                  >
                    Promote Stage
                  </button>
                }
                <button 
                  (click)="selectedTicket.set(null)"
                  class="px-3 py-1 text-[11px] font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      }

      <!-- CREATE NEW TICKET MODAL -->
      @if (showCreateModal()) {
        <div class="fixed inset-0 bg-black/60 backdrop-blur-xs z-[100] flex items-center justify-center p-4" id="create-ticket-modal">
          <div class="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl max-w-sm w-full p-5 shadow-2xl space-y-4">
            <div class="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
              <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">Create Board Ticket</h3>
              <button (click)="showCreateModal.set(false)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <lucide-icon name="close" [size]="14"></lucide-icon>
              </button>
            </div>

            <form [formGroup]="createForm" (ngSubmit)="onTicketSubmit()" class="space-y-3">
              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Ticket Title</label>
                <input 
                  type="text"
                  formControlName="title"
                  placeholder="e.g. Implement subnet IP address whitelist"
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>

              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Category</label>
                  <select 
                    formControlName="category"
                    class="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                  >
                    <option value="core">Core Kernel</option>
                    <option value="p2p">P2P Protocols</option>
                    <option value="crypto">Cryptography</option>
                    <option value="ui">User Interface</option>
                    <option value="agent">Agent Models</option>
                  </select>
                </div>

                <div>
                  <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Difficulty</label>
                  <select 
                    formControlName="difficulty"
                    class="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Work Category Tier</label>
                <select 
                  formControlName="tier"
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                >
                  <option value="local">local</option>
                  <option value="relay">relay</option>
                  <option value="cloud">cloud</option>
                </select>
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Full Scope / Description</label>
                <textarea 
                  formControlName="description"
                  rows="4"
                  placeholder="Detailed task guidelines..."
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none resize-none font-sans"
                ></textarea>
              </div>

              <div class="flex justify-end space-x-2 pt-2">
                <button 
                  type="button"
                  (click)="showCreateModal.set(false)"
                  class="px-3 py-1.5 text-xs font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  [disabled]="createForm.invalid"
                  class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] disabled:opacity-50"
                >
                  Propose Block
                </button>
              </div>
            </form>
          </div>
        </div>
      }

      <!-- SEND TO CHANGELOG INTERMEDIATE MODAL -->
      @if (changelogModalTicket(); as t) {
        <div class="fixed inset-0 bg-black/70 backdrop-blur-xs z-[110] flex items-center justify-center p-4" id="send-changelog-modal">
          <div class="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl max-w-sm w-full p-5 shadow-2xl space-y-4">
            <div class="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
              <h3 class="text-xs font-semibold text-purple-400 flex items-center space-x-1">
                <lucide-icon name="changelog" [size]="14"></lucide-icon>
                <span>Commit to Changelog Archive</span>
              </h3>
              <button (click)="changelogModalTicket.set(null)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <lucide-icon name="close" [size]="14"></lucide-icon>
              </button>
            </div>

            <div class="space-y-3 text-xs">
              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Changelog Block Title</label>
                <input 
                  type="text"
                  [(ngModel)]="clTitle"
                  [ngModelOptions]="{standalone: true}"
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none font-medium"
                />
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">The Problem (What was broken or missing)</label>
                <textarea 
                  [(ngModel)]="clProblem"
                  [ngModelOptions]="{standalone: true}"
                  rows="3"
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none resize-none font-mono"
                ></textarea>
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">The Solution (What was implemented)</label>
                <textarea 
                  [(ngModel)]="clSolution"
                  [ngModelOptions]="{standalone: true}"
                  rows="3"
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none resize-none font-mono"
                ></textarea>
              </div>
            </div>

            <div class="flex justify-end space-x-2 pt-2 border-t border-[var(--border)]/20">
              <button 
                (click)="changelogModalTicket.set(null)"
                class="px-3 py-1.5 text-xs font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
              >
                Cancel
              </button>
              <button 
                (click)="submitChangelog()"
                class="px-4 py-1.5 text-xs font-medium rounded bg-purple-600 text-white hover:bg-purple-500"
              >
                Publish Audit Block
              </button>
            </div>
          </div>
        </div>
      }

    </div>
  `,
})
export class Board {
  state = inject(TetherState);
  viewMode = signal<'grid' | 'dag'>('grid');

  // Filters
  filterCategory = 'all';
  filterTier = 'all';

  // Selected Overlay States
  selectedTicket = signal<JobTicket | null>(null);
  showCreateModal = signal<boolean>(false);

  // Changelog dialog states
  changelogModalTicket = signal<JobTicket | null>(null);
  clTitle = '';
  clProblem = '';
  clSolution = '';

  // Forms
  createForm = new FormGroup({
    title: new FormControl('', [Validators.required]),
    category: new FormControl<'core' | 'p2p' | 'crypto' | 'ui' | 'agent'>('core', [Validators.required]),
    difficulty: new FormControl<'low' | 'medium' | 'high'>('medium', [Validators.required]),
    tier: new FormControl<'local' | 'relay' | 'cloud'>('local', [Validators.required]),
    description: new FormControl('', [Validators.required]),
  });

  // Category counts
  counts = computed(() => {
    const list = this.state.tickets();
    return {
      open: list.filter(t => t.status === 'open').length,
      active: list.filter(t => t.status === 'active').length,
      ready: list.filter(t => t.status === 'ready').length,
      completed: list.filter(t => t.status === 'completed').length,
    };
  });

  // Filtered computed queues
  filteredTickets = computed(() => {
    const list = this.state.tickets();
    const cat = this.filterCategory;
    const tier = this.filterTier;

    return list.filter(t => {
      const matchCat = cat === 'all' || t.category === cat;
      const matchTier = tier === 'all' || t.tier === tier;
      return matchCat && matchTier;
    });
  });

  openTickets = computed(() => this.filteredTickets().filter(t => t.status === 'open'));
  activeTickets = computed(() => this.filteredTickets().filter(t => t.status === 'active'));
  readyTickets = computed(() => this.filteredTickets().filter(t => t.status === 'ready'));
  completedTickets = computed(() => this.filteredTickets().filter(t => t.status === 'completed'));

  openTicketDetails(t: JobTicket) {
    this.selectedTicket.set(t);
  }

  promoteStatus(t: JobTicket) {
    const statusMap: Record<string, 'open' | 'active' | 'ready' | 'completed'> = {
      'open': 'active',
      'active': 'ready',
      'ready': 'completed'
    };
    const next = statusMap[t.status];
    if (next) {
      this.state.tickets.update(ticks => ticks.map(item => item.id === t.id ? { ...item, status: next } : item));
      this.selectedTicket.update(selected => selected ? { ...selected, status: next } : null);
    }
  }

  onTicketSubmit() {
    if (this.createForm.invalid) return;

    const title = this.createForm.value.title || '';
    const category = this.createForm.value.category || 'core';
    const difficulty = this.createForm.value.difficulty || 'medium';
    const tier = this.createForm.value.tier || 'local';
    const desc = this.createForm.value.description || '';

    this.state.createTicket(title, category, difficulty, tier, desc);
    this.createForm.reset({ title: '', category: 'core', difficulty: 'medium', tier: 'local', description: '' });
    this.showCreateModal.set(false);
  }

  openChangelogModal(t: JobTicket) {
    this.selectedTicket.set(null);
    this.changelogModalTicket.set(t);
    this.clTitle = t.title;
    this.clProblem = `No audit trails found in Drizzle database for block hash verification of: ${t.handle}.`;
    this.clSolution = `Integrated content address check and updated background SQLite tables to commit blocks instantly. Verified using test loopbacks.`;
  }

  submitChangelog() {
    const t = this.changelogModalTicket();
    if (!t) return;

    this.state.sendToChangelog(t.id, this.clTitle, this.clProblem, this.clSolution);
    this.changelogModalTicket.set(null);
    alert('Published audit block to Changelog archive.');
  }
}
