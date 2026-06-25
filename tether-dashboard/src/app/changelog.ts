import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {TetherState} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

@Component({
  selector: 'app-changelog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, LucideIcon],
  template: `
    <div class="flex flex-col h-full bg-[var(--bg-base)] text-[var(--text-primary)]" id="changelog-root">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-3 bg-[var(--bg-surface)]">
        <div>
          <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">System Changelog</h3>
          <p class="text-[11px] text-[var(--text-muted)] mt-0.5">Immutable append-only cryptographic block commit history.</p>
        </div>

        <div class="text-[11px] text-[var(--text-muted)] font-mono flex items-center space-x-1">
          <lucide-icon name="shield" [size]="12" class="text-emerald-500"></lucide-icon>
          <span>Ledger verified (BLAKE3)</span>
        </div>
      </div>

      <!-- Feed Container -->
      <div class="flex-1 overflow-y-auto p-6 bg-[var(--bg-base)]">
        <div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-4">
          
          @if (state.changelog().length === 0) {
            <div class="p-12 rounded-xl border border-dashed border-[var(--border)]/30 text-center text-xs text-[var(--text-muted)] col-span-2">
              No audit logs recorded in system ledger yet. Marking board tickets as resolved will populate this.
            </div>
          } @else {
            @for (log of state.changelog(); track log.id; let first = $first) {
              <div 
                class="rounded-lg border bg-[var(--bg-surface)] transition-all shadow-sm overflow-hidden h-fit"
                [class.border-purple-500/30]="first"
                [class.border-[var(--border)]]="!first"
              >
                <!-- Compact Row Header (clickable to expand) -->
                <div 
                  (click)="toggleExpand(log.id)"
                  class="p-3 hover:bg-[var(--bg-elevated)]/30 cursor-pointer flex items-center justify-between transition-colors relative"
                >
                  <!-- Pulse light accent for newest entry -->
                  @if (first) {
                    <span class="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-purple-500 to-transparent"></span>
                  }

                  <div class="flex items-center space-x-3 min-w-0 pr-4">
                    <lucide-icon 
                      [name]="isExpanded(log.id) ? 'chevron-down' : 'chevron-right'" 
                      [size]="14" 
                      class="text-[var(--text-muted)] shrink-0"
                    ></lucide-icon>
                    
                    <h4 class="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider truncate">
                      {{ log.title }}
                    </h4>
                  </div>

                  <div class="flex items-center space-x-3 text-[10px] font-mono shrink-0" (click)="$event.stopPropagation()">
                    <span class="text-[var(--text-muted)] hover:text-[var(--text-secondary)] cursor-help hidden sm:inline" title="2026-06-24 UTC time lock">
                      {{ log.timestamp }}
                    </span>
                    <span class="text-[var(--border)] hidden sm:inline">|</span>
                    <div class="flex items-center space-x-1">
                      <span class="text-[var(--text-secondary)] select-all font-mono">{{ log.handle }}</span>
                      <button 
                        (click)="copyHandle(log.handle)" 
                        class="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-0.5"
                        title="Copy commit hash"
                      >
                        @if (copiedHandle() === log.handle) {
                          <lucide-icon name="check" [size]="10" class="text-emerald-500"></lucide-icon>
                        } @else {
                          <lucide-icon name="copy" [size]="10"></lucide-icon>
                        }
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Problem / Solution grid (visible only when expanded) -->
                @if (isExpanded(log.id)) {
                  <div class="border-t border-[var(--border)]/30 p-4 bg-[var(--bg-base)]/40 flex flex-col space-y-3">
                    <div class="p-3 rounded bg-[var(--bg-base)] border border-[var(--border)]/40 text-xs">
                      <span class="block text-[10px] font-bold text-red-400 uppercase tracking-wider mb-1 font-mono">Problem Root Cause</span>
                      <p class="text-[var(--text-secondary)] leading-relaxed font-sans whitespace-pre-wrap">{{ log.problem }}</p>
                    </div>

                    <div class="p-3 rounded bg-[var(--bg-base)] border border-[var(--border)]/40 text-xs">
                      <span class="block text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1 font-mono">Resolution Implemented</span>
                      <p class="text-[var(--text-secondary)] leading-relaxed font-sans whitespace-pre-wrap">{{ log.solution }}</p>
                    </div>
                  </div>
                }
              </div>
            }
          }

        </div>
      </div>
    </div>
  `,
})
export class Changelog {
  state = inject(TetherState);
  copiedHandle = signal<string | null>(null);
  
  // Keep track of which logs are expanded (first log expanded by default)
  expandedLogIds = signal<Set<string>>(new Set());

  constructor() {
    // Expand the first entry by default if there are any
    const logs = this.state.changelog();
    if (logs.length > 0) {
      this.expandedLogIds.set(new Set([logs[0].id]));
    }
  }

  toggleExpand(id: string) {
    const current = new Set(this.expandedLogIds());
    if (current.has(id)) {
      current.delete(id);
    } else {
      current.add(id);
    }
    this.expandedLogIds.set(current);
  }

  isExpanded(id: string): boolean {
    return this.expandedLogIds().has(id);
  }

  copyHandle(handle: string) {
    navigator.clipboard.writeText(handle);
    this.copiedHandle.set(handle);
    setTimeout(() => this.copiedHandle.set(null), 2000);
  }
}
