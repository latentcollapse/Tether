import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {TetherState} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

@Component({
  selector: 'app-usage',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, LucideIcon],
  template: `
    <div class="flex flex-col h-full bg-[var(--bg-base)] text-[var(--text-primary)]" id="usage-root">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-3 bg-[var(--bg-surface)]">
        <div>
          <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">Usage Telemetry</h3>
          <p class="text-[11px] text-[var(--text-muted)] mt-0.5">Live monitoring of system memory, loopback queues, and API limits.</p>
        </div>

        <div class="flex gap-1.5 shrink-0">
          <button 
            (click)="timeRange.set('24h')" 
            [class]="timeRange() === '24h' ? 'px-2 py-0.5 text-[10px] font-medium rounded bg-[var(--accent)] text-[var(--bg-base)]' : 'px-2 py-0.5 text-[10px] text-[var(--text-secondary)]'"
          >
            24h
          </button>
          <button 
            (click)="timeRange.set('7d')" 
            [class]="timeRange() === '7d' ? 'px-2 py-0.5 text-[10px] font-medium rounded bg-[var(--accent)] text-[var(--bg-base)]' : 'px-2 py-0.5 text-[10px] text-[var(--text-secondary)]'"
          >
            7d
          </button>
        </div>
      </div>

      <!-- Main container grid -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        
        <!-- Stats cards row -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <!-- Card 1 -->
          <div class="bg-[var(--bg-surface)] p-4 rounded-xl border border-[var(--border)] shadow-xs">
            <p class="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-1">Total Network Throughput</p>
            <h2 class="text-2xl font-bold text-[var(--text-primary)] font-mono">
              {{ formatThroughput() }} <span class="text-xs font-medium text-[var(--text-muted)]">msgs/s</span>
            </h2>
            <div class="mt-3 flex items-center text-[10px] text-emerald-400 font-semibold">
              <lucide-icon name="chart" [size]="10" class="mr-1"></lucide-icon>
              <span>+14.2% traffic change vs yesterday</span>
            </div>
          </div>

          <!-- Card 2 -->
          <div class="bg-[var(--bg-surface)] p-4 rounded-xl border border-[var(--border)] shadow-xs">
            <p class="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-1">Avg API Gateway Latency</p>
            <h2 class="text-2xl font-bold text-[var(--text-primary)] font-mono">
              42 <span class="text-xs font-medium text-[var(--text-muted)]">ms</span>
            </h2>
            <div class="mt-3">
              <div class="w-full bg-[var(--bg-base)] h-1 rounded-full overflow-hidden border border-[var(--border)]/40">
                <div class="bg-blue-500 h-full w-2/3"></div>
              </div>
            </div>
          </div>

          <!-- Card 3 -->
          <div class="bg-[var(--bg-surface)] p-4 rounded-xl border border-[var(--border)] shadow-xs">
            <p class="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-1">Active Client Sessions</p>
            <h2 class="text-2xl font-bold text-[var(--text-primary)] font-mono">
              {{ activeConnectionsCount() }} <span class="text-xs font-medium text-[var(--text-muted)]">nodes</span>
            </h2>
            <div class="mt-3 text-[10px] text-[var(--text-secondary)] font-mono">
              Peak concurrently logged: 12
            </div>
          </div>

          <!-- Card 4 -->
          <div class="bg-[var(--bg-surface)] p-4 rounded-xl border border-[var(--border)] shadow-xs">
            <p class="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-1">Channel Error Rate</p>
            <h2 class="text-2xl font-bold text-emerald-400 font-mono">
              0.04<span class="text-xs font-medium text-[var(--text-muted)]">%</span>
            </h2>
            <div class="mt-3 text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">
              Within normal threshold
            </div>
          </div>
        </div>

        <!-- Chart Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Resource utilization chart (Mock SVG bars for supreme look) -->
          <div class="lg:col-span-2 p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] flex flex-col justify-between h-[300px]">
            <div class="flex justify-between items-center pb-2 border-b border-[var(--border)]/20 mb-4">
              <span class="text-[10px] uppercase font-bold text-[var(--text-secondary)] tracking-wider">Active Resource Utilization</span>
              <span class="text-[9px] font-mono text-[var(--text-muted)]">CPU (green) vs memory (blue)</span>
            </div>

            <!-- SVG Bar chart mimicking D3 graphs -->
            <div class="flex-1 flex items-end justify-between space-x-1.5 h-full relative px-2">
              <div class="absolute inset-x-0 top-1/2 border-t border-[var(--border)]/20 pointer-events-none"></div>
              <div class="absolute inset-x-0 top-1/4 border-t border-[var(--border)]/10 pointer-events-none"></div>

              @for (h of mockBarHeights; track $index) {
                <div class="flex-1 flex flex-col justify-end h-full">
                  <div 
                    class="w-full bg-[var(--accent)] rounded-t transition-all duration-500" 
                    [style.height.%]="h"
                    [style.opacity]="$index === 5 ? '1' : '0.6'"
                  ></div>
                </div>
              }
            </div>

            <!-- Chart labels -->
            <div class="flex justify-between text-[9px] text-[var(--text-muted)] font-mono mt-4 pt-1 border-t border-[var(--border)]/20">
              <span>10:00 AM</span>
              <span>10:15 AM</span>
              <span>10:30 AM</span>
              <span>10:45 AM</span>
              <span>11:00 AM</span>
            </div>
          </div>

          <!-- SQLite Queue database statistics -->
          <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] flex flex-col h-[300px]" id="sqlite-metrics">
            <span class="text-[10px] uppercase font-bold text-[var(--text-secondary)] tracking-wider pb-2 border-b border-[var(--border)]/20 mb-4">Database Cache Logs</span>
            
            <div class="flex-1 space-y-4">
              <div class="space-y-1">
                <div class="flex justify-between text-[11px] text-[var(--text-secondary)] font-mono">
                  <span>SQLite DB size</span>
                  <span class="text-[var(--text-primary)]">14.2 MB</span>
                </div>
                <div class="w-full bg-[var(--bg-base)] h-1.5 rounded-full overflow-hidden border border-[var(--border)]/30">
                  <div class="bg-blue-500 h-full w-1/4"></div>
                </div>
              </div>

              <div class="space-y-1">
                <div class="flex justify-between text-[11px] text-[var(--text-secondary)] font-mono">
                  <span>SQLite index cache efficiency</span>
                  <span class="text-[var(--text-primary)]">99.8%</span>
                </div>
                <div class="w-full bg-[var(--bg-base)] h-1.5 rounded-full overflow-hidden border border-[var(--border)]/30">
                  <div class="bg-emerald-500 h-full w-[99.8%]"></div>
                </div>
              </div>

              <div class="space-y-1">
                <div class="flex justify-between text-[11px] text-[var(--text-secondary)] font-mono">
                  <span>PAKE authentication key buffer pool</span>
                  <span class="text-[var(--text-primary)]">4 / 10 active</span>
                </div>
                <div class="w-full bg-[var(--bg-base)] h-1.5 rounded-full overflow-hidden border border-[var(--border)]/30">
                  <div class="bg-purple-500 h-full w-[40%]"></div>
                </div>
              </div>
            </div>

            <div class="pt-4 border-t border-[var(--border)]/20 mt-auto">
              <div class="text-[10px] text-[var(--text-muted)] font-mono flex items-center space-x-1 justify-between">
                <span>SQL Engine version:</span>
                <span class="text-[var(--text-secondary)]">SQLite 3.42 (Drizzle ORM)</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  `,
})
export class Usage {
  state = inject(TetherState);
  timeRange = signal<'24h' | '7d'>('24h');

  mockBarHeights = [35, 45, 55, 30, 48, 72, 90, 68, 52, 40, 62, 55, 65, 42];

  formatThroughput() {
    const list = this.state.nodes();
    const sum = list.reduce((acc, curr) => acc + curr.msgsToday, 0);
    // Dynamic rate based on total messages
    return (sum / 400).toFixed(1);
  }

  activeConnectionsCount() {
    return this.state.nodes().filter(n => n.status === 'online').length;
  }
}
