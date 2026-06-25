import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {TetherState, ThemeColors} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';

@Component({
  selector: 'app-settings',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, LucideIcon],
  template: `
    <div class="flex flex-col h-full bg-[var(--bg-base)] text-[var(--text-primary)] font-sans" id="settings-root">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-3 bg-[var(--bg-surface)]">
        <div>
          <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">System Settings</h3>
          <p class="text-[11px] text-[var(--text-muted)] mt-0.5">Configure dashboard layout metrics, database hooks, and local theme profiles.</p>
        </div>

        <span class="text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-elevated)] px-2 py-0.5 rounded border border-[var(--border)]">
          admin_session: active
        </span>
      </div>

      <!-- Main Settings Panels -->
      <div class="flex-1 overflow-y-auto p-6 bg-[var(--bg-base)]">
        <div class="max-w-2xl mx-auto space-y-6">
          
          <!-- APPEARANCE SECTION -->
          <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] space-y-4">
            <h3 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] border-b border-[var(--border)]/30 pb-2 flex items-center space-x-1.5">
              <lucide-icon name="eye" [size]="14"></lucide-icon>
              <span>Appearance</span>
            </h3>

            <!-- Theme Selector -->
            <div>
              <label class="block text-[11px] text-[var(--text-secondary)] mb-1.5 font-medium">Active Color Scheme Theme</label>
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                @for (th of availableThemes; track th.id) {
                  <button 
                    (click)="changeTheme(th.id)"
                    [class]="state.activeThemeName() === th.id 
                      ? 'px-2.5 py-1.5 text-xs font-medium rounded bg-[var(--accent-dim)] text-[var(--accent)] border border-[var(--accent)] text-left flex flex-col justify-between h-14' 
                      : 'px-2.5 py-1.5 text-xs font-medium rounded bg-[var(--bg-elevated)]/50 hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border)] hover:text-[var(--text-primary)] text-left flex flex-col justify-between h-14'"
                  >
                    <span class="font-bold">{{ th.name }}</span>
                    <span class="text-[9px] text-[var(--text-muted)] truncate">{{ th.desc }}</span>
                  </button>
                }
              </div>
            </div>

            <!-- Custom Token Editor (Displays if custom is selected) -->
            @if (state.activeThemeName() === 'custom') {
              <div class="p-4 rounded-lg bg-[var(--bg-base)] border border-[var(--border)] space-y-3">
                <span class="block text-[10px] text-yellow-500 font-bold uppercase">Dynamic Token Configurator</span>
                <p class="text-[10px] text-[var(--text-secondary)] leading-relaxed">Modify active CSS color tokens in JSON layout below. Saved live to localStorage.</p>
                <textarea 
                  [(ngModel)]="customThemeJSON"
                  [ngModelOptions]="{standalone: true}"
                  rows="10"
                  class="w-full p-2 text-xs font-mono rounded border border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
                ></textarea>
                <div class="flex justify-end">
                  <button 
                    (click)="applyCustomThemeJSON()"
                    class="px-2.5 py-1 text-[11px] font-semibold rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90"
                  >
                    Apply JSON Tokens
                  </button>
                </div>
              </div>
            }

            <!-- UI Behavior preferences -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium font-sans">Left Sidebar default</label>
                <select 
                  [(ngModel)]="sidebarPreference"
                  (change)="updateSidebarPreference()"
                  class="w-full px-2.5 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                >
                  <option value="expanded">Expanded</option>
                  <option value="collapsed">Collapsed</option>
                </select>
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium font-sans">Real-time feed</label>
                <select 
                  [(ngModel)]="feedPreference"
                  (change)="updateFeedPreference()"
                  class="w-full px-2.5 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                >
                  <option value="visible">Visible by default</option>
                  <option value="hidden">Hidden by default</option>
                </select>
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium font-sans">Row Density spacing</label>
                <select 
                  [(ngModel)]="densityPreference"
                  (change)="updateDensityPreference()"
                  class="w-full px-2.5 py-1 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                >
                  <option value="comfortable">Comfortable</option>
                  <option value="compact">Compact</option>
                </select>
              </div>
            </div>
          </div>

          <!-- LANGUAGE & REGION SECTION -->
          <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] space-y-4">
            <h3 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] border-b border-[var(--border)]/30 pb-2 flex items-center space-x-1.5">
              <lucide-icon name="globe" [size]="14"></lucide-icon>
              <span>Language & Region</span>
            </h3>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium">Interface Language</label>
                <select 
                  [(ngModel)]="state.language"
                  [ngModelOptions]="{standalone: true}"
                  class="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                >
                  <option value="en">English (US)</option>
                  <option value="fr">French (Français)</option>
                  <option value="de">German (Deutsch)</option>
                  <option value="es">Spanish (Español)</option>
                  <option value="zh-cn">Chinese (Simplified)</option>
                  <option value="zh-tw">Chinese (Traditional)</option>
                  <option value="ja">Japanese (日本語)</option>
                  <option value="pt">Portuguese (Português)</option>
                  <option value="ko">Korean (한국어)</option>
                </select>
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium">Date Format</label>
                <select 
                  [(ngModel)]="state.dateFormat"
                  [ngModelOptions]="{standalone: true}"
                  class="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                >
                  <option value="ISO 8601">ISO 8601 (YYYY-MM-DD)</option>
                  <option value="US">US (MM/DD/YYYY)</option>
                  <option value="EU">EU (DD/MM/YYYY)</option>
                </select>
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium">Timezone offset</label>
                <select 
                  [(ngModel)]="state.timezone"
                  [ngModelOptions]="{standalone: true}"
                  class="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                >
                  <option value="auto">Auto-detect from System</option>
                  <option value="UTC">Coordinated Universal (UTC)</option>
                  <option value="PST">Pacific Standard (PST)</option>
                  <option value="EST">Eastern Standard (EST)</option>
                  <option value="GMT">Greenwich Mean Time (GMT)</option>
                </select>
              </div>
            </div>
          </div>

          <!-- NOTIFICATIONS & BEHAVIOR SECTION -->
          <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] space-y-4">
            <h3 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] border-b border-[var(--border)]/30 pb-2 flex items-center space-x-1.5">
              <lucide-icon name="bell" [size]="14"></lucide-icon>
              <span>Notifications & Behavior</span>
            </h3>

            <div class="space-y-3">
              <!-- Autonomous Mode Toggle -->
              <div class="flex items-center justify-between">
                <div>
                  <span class="block text-xs font-bold text-[var(--text-primary)] font-sans">Autonomous Routing Mode</span>
                  <p class="text-[11px] text-[var(--text-muted)]">Agents automatically invoke wakeup loops upon receiving unread thread payloads.</p>
                </div>
                <input 
                  type="checkbox"
                  [(ngModel)]="state.autonomousMode"
                  [ngModelOptions]="{standalone: true}"
                  class="rounded border-[var(--border)] text-[var(--accent)] focus:ring-[var(--accent)]"
                />
              </div>

              <!-- Message threshold slider -->
              <div class="space-y-1">
                <div class="flex justify-between text-xs font-semibold text-[var(--text-secondary)]">
                  <span>Stale block threshold hours</span>
                  <span class="font-mono text-[var(--text-primary)]">{{ state.staleHours() }}h</span>
                </div>
                <input 
                  type="range" 
                  min="4" 
                  max="168" 
                  [(ngModel)]="state.staleHours"
                  [ngModelOptions]="{standalone: true}"
                  class="w-full accent-[var(--accent)] cursor-pointer"
                />
              </div>

              <!-- Sounds/Desktop options -->
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div class="flex items-center justify-between p-2.5 rounded bg-[var(--bg-base)] border border-[var(--border)]/40">
                  <span class="text-[11px] font-medium">Desktop notifications</span>
                  <input 
                    type="checkbox"
                    [(ngModel)]="state.desktopNotifications"
                    [ngModelOptions]="{standalone: true}"
                    class="rounded"
                  />
                </div>
                <div class="flex items-center justify-between p-2.5 rounded bg-[var(--bg-base)] border border-[var(--border)]/40 font-sans">
                  <span class="text-[11px] font-medium">Audio alert sounds</span>
                  <input 
                    type="checkbox"
                    [(ngModel)]="state.soundOnNewMessage"
                    [ngModelOptions]="{standalone: true}"
                    class="rounded"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- SYSADMIN CONTROLS (Only visible in Local mode) -->
          <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] space-y-4">
            <h3 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] border-b border-[var(--border)]/30 pb-2 flex items-center space-x-1.5">
              <lucide-icon name="terminal" [size]="14"></lucide-icon>
              <span>Sysadmin Maintenance Controls</span>
            </h3>

            <div class="space-y-3.5 text-xs text-[var(--text-secondary)] leading-relaxed">
              <p>Execute low-level cleanup commands and SQLite backup operations on the active local database instance.</p>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                <!-- Purge handles -->
                <button 
                  (click)="purgeStale()"
                  class="p-2.5 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 font-medium border border-amber-500/20 text-left transition-colors flex justify-between items-center"
                >
                  <div>
                    <span class="block text-[11px] font-bold uppercase">Purge Stale Handles</span>
                    <span class="text-[9px] text-[var(--text-muted)]">Prunes yesterday's messages</span>
                  </div>
                  <lucide-icon name="trash" [size]="14"></lucide-icon>
                </button>

                <!-- Export database snapshot -->
                <button 
                  (click)="exportSnapshot()"
                  class="p-2.5 rounded bg-[var(--accent-dim)] hover:opacity-90 text-[var(--accent)] font-medium border border-[var(--accent)]/30 text-left transition-colors flex justify-between items-center"
                >
                  <div>
                    <span class="block text-[11px] font-bold uppercase">Export JSON Snapshot</span>
                    <span class="text-[9px] text-[var(--text-muted)]">Download schema copy</span>
                  </div>
                  <lucide-icon name="copy" [size]="14"></lucide-icon>
                </button>

                <!-- Import database snapshot -->
                <button 
                  (click)="triggerImportModal()"
                  class="p-2.5 rounded bg-[var(--accent-dim)] hover:opacity-90 text-[var(--accent)] font-medium border border-[var(--accent)]/30 text-left transition-colors flex justify-between items-center font-sans"
                >
                  <div>
                    <span class="block text-[11px] font-bold uppercase">Import JSON Snapshot</span>
                    <span class="text-[9px] text-[var(--text-muted)]">Upload snapshot file</span>
                  </div>
                  <lucide-icon name="plus" [size]="14"></lucide-icon>
                </button>

                <!-- Reset registrations -->
                <button 
                  (click)="resetRegistrations()"
                  class="p-2.5 rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 font-medium border border-red-500/20 text-left transition-colors flex justify-between items-center"
                >
                  <div>
                    <span class="block text-[11px] font-bold uppercase">Reset Registrations</span>
                    <span class="text-[9px] text-[var(--text-muted)]">Restores default node layout</span>
                  </div>
                  <lucide-icon name="revoke" [size]="14"></lucide-icon>
                </button>
              </div>

              <!-- View Server Logs Link -->
              <div class="pt-2 border-t border-[var(--border)]/20 text-[10px] flex items-center justify-between font-mono">
                <span>SQLite DB path: <code class="text-[var(--text-primary)]">~/.tether/database.sqlite</code></span>
                <button (click)="viewRawLogs()" class="text-[var(--accent)] hover:underline flex items-center space-x-1">
                  <span>Open raw daemon stdout</span>
                  <lucide-icon name="external-link" [size]="10"></lucide-icon>
                </button>
              </div>
            </div>
          </div>

          <!-- MODULE HOOKS SECTION -->
          <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] space-y-4">
            <h3 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] border-b border-[var(--border)]/30 pb-2 flex items-center space-x-1.5">
              <lucide-icon name="board" [size]="14"></lucide-icon>
              <span>Module Hooks</span>
            </h3>

            <div class="text-xs text-[var(--text-secondary)] space-y-3 leading-relaxed">
              <p>Extend Tether by installing modular agent scripts or background daemon pipelines. No modules are registered by default.</p>
              
              <div class="p-3 rounded border border-dashed border-[var(--border)]/30 text-center text-[var(--text-muted)] font-mono">
                No custom hooks registered.
              </div>

              <div class="flex justify-end pt-1">
                <button (click)="openAPI()" class="text-[10px] text-[var(--accent)] font-mono hover:underline flex items-center space-x-1">
                  <span>Tether Module API Specification</span>
                  <lucide-icon name="external-link" [size]="10"></lucide-icon>
                </button>
              </div>
            </div>
          </div>

          <!-- ABOUT SECTION -->
          <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] space-y-3">
            <h3 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] border-b border-[var(--border)]/30 pb-2">
              About
            </h3>

            <div class="grid grid-cols-2 gap-2 text-[11px] font-mono text-[var(--text-secondary)] leading-relaxed">
              <div>Tether Dashboard: <span class="text-[var(--text-primary)]">v2.0-spec</span></div>
              <div>Build Signature: <span class="text-[var(--text-primary)]">sh_c81f0b...91a2e4</span></div>
              <div>License: <span class="text-[var(--text-primary)] font-sans">Apache-2.0 (Custom Proprietary)</span></div>
              <div>Platform: <span class="text-[var(--text-primary)]">Google AI Studio (Gemini)</span></div>
            </div>
          </div>

        </div>
      </div>

      <!-- IMPORT MODAL -->
      @if (showImportModal()) {
        <div class="fixed inset-0 bg-black/60 backdrop-blur-xs z-[100] flex items-center justify-center p-4" id="import-db-modal">
          <div class="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl max-w-sm w-full p-5 shadow-2xl space-y-4">
            <div class="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
              <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">Import Snapshot JSON</h3>
              <button (click)="showImportModal.set(false)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <lucide-icon name="close" [size]="14"></lucide-icon>
              </button>
            </div>

            <div class="space-y-3">
              <label class="block text-[11px] text-[var(--text-secondary)]">Paste Export JSON String</label>
              <textarea 
                [(ngModel)]="importJSON"
                [ngModelOptions]="{standalone: true}"
                rows="8"
                class="w-full p-2 text-xs font-mono rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:outline-none"
                placeholder='{ "theme": "void" }'
              ></textarea>
            </div>

            <div class="flex justify-end space-x-2 pt-2">
              <button 
                (click)="showImportModal.set(false)"
                class="px-3 py-1.5 text-xs font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
              >
                Cancel
              </button>
              <button 
                (click)="applyImportJSON()"
                class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)]"
              >
                Restore Snapshot
              </button>
            </div>
          </div>
        </div>
      }

    </div>
  `,
})
export class Settings {
  state = inject(TetherState);

  availableThemes = [
    { id: 'void', name: 'Void', desc: 'Deep black base, single cyan accent' },
    { id: 'cyberpunk', name: 'Cyberpunk', desc: 'Near-black with neon yellow primary' },
    { id: 'synthwave', name: 'Synthwave', desc: 'Dark purple, hot pink retro-futuristic' },
    { id: 'classic', name: 'Classic', desc: 'Fluent-inspired light mode grays' },
    { id: 'terminal', name: 'Terminal', desc: 'Green on black monospace aesthetic' },
    { id: 'arctic', name: 'Arctic', desc: 'Cool blues and minimal whites' },
    { id: 'ember', name: 'Ember', desc: 'Warm dark with amber accents' },
    { id: 'custom', name: 'Custom Theme', desc: 'Full token overrides JSON configuration' },
  ];

  // Preference models for instant settings toggles
  sidebarPreference = this.state.sidebarCollapsed() ? 'collapsed' : 'expanded';
  feedPreference = this.state.feedVisible() ? 'visible' : 'hidden';
  densityPreference = this.state.density();

  // Custom theme json signal
  customThemeJSON = '';
  importJSON = '';
  showImportModal = signal<boolean>(false);

  constructor() {
    const custom = this.state.customThemeTokens();
    if (custom) {
      this.customThemeJSON = JSON.stringify(custom, null, 2);
    } else {
      this.customThemeJSON = JSON.stringify(this.state.themeVariables(), null, 2);
    }
  }

  changeTheme(id: string) {
    this.state.activeThemeName.set(id);
    if (id !== 'custom') {
      this.customThemeJSON = JSON.stringify(this.state.themeVariables(), null, 2);
    }
  }

  applyCustomThemeJSON() {
    try {
      const parsed = JSON.parse(this.customThemeJSON);
      this.state.customThemeTokens.set(parsed as ThemeColors);
      alert('Custom theme token payload committed successfully.');
    } catch {
      alert('Invalid JSON schema. Ensure all color tokens are properly formatted hex coordinates.');
    }
  }

  updateSidebarPreference() {
    this.state.sidebarCollapsed.set(this.sidebarPreference === 'collapsed');
  }

  updateFeedPreference() {
    this.state.feedVisible.set(this.feedPreference === 'visible');
  }

  updateDensityPreference() {
    this.state.density.set(this.densityPreference as 'comfortable' | 'compact');
  }

  purgeStale() {
    if (confirm('Permanently purge all messages from yesterday to clean SQLite cache buffers? This operation is irreversible.')) {
      this.state.purgeStaleHandles();
      alert('Stale records successfully purged.');
    }
  }

  exportSnapshot() {
    const json = this.state.exportDatabaseSnapshot();
    navigator.clipboard.writeText(json);
    alert('JSON Database Snapshot copied to clipboard. You can save this text as a local config backup.');
  }

  triggerImportModal() {
    this.importJSON = '';
    this.showImportModal.set(true);
  }

  applyImportJSON() {
    if (!this.importJSON) return;
    this.state.importDatabaseSnapshot(this.importJSON);
    this.showImportModal.set(false);
    alert('Database successfully restored from JSON snapshot.');
  }

  resetRegistrations() {
    if (confirm('Restoring default agent registrations? This will reset your network coordinate graph to initial coordinates.')) {
      this.state.resetAllAgentRegistrations();
      alert('Network coordinates restored to original specification defaults.');
    }
  }

  viewRawLogs() {
    alert('Local system is not connected to any live backend proxy.\nStreaming development container logs through loopback dashboard logs buffer...');
  }

  openAPI() {
    alert('Redirecting to: https://tether.network/docs/api/modules\nExplore developer hooks for zero-knowledge node extensions.');
  }
}
