import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {FormControl, FormGroup, FormsModule, ReactiveFormsModule, Validators} from '@angular/forms';
import {TetherState} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

@Component({
  selector: 'app-connect',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, LucideIcon],
  template: `
    <div class="flex flex-col h-full bg-[var(--bg-base)] text-[var(--text-primary)]" id="connect-root">
      <!-- Tabs Header -->
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-2 bg-[var(--bg-surface)]">
        <div class="flex space-x-2">
          <button
            id="tab-invite"
            (click)="activeSubTab.set('invite')"
            [class]="activeSubTab() === 'invite'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Invite Link
          </button>
          <button
            id="tab-pake"
            (click)="activeSubTab.set('pake')"
            [class]="activeSubTab() === 'pake'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            PAKE
          </button>
          <button
            id="tab-keys"
            (click)="activeSubTab.set('keys')"
            [class]="activeSubTab() === 'keys'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Network Keys
          </button>
        </div>

        @if (activeSubTab() === 'keys') {
          <button
            (click)="showIssueKeyModal.set(true)"
            class="px-2.5 py-1 text-[11px] font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90 flex items-center space-x-1"
          >
            <lucide-icon name="plus" [size]="12"></lucide-icon>
            <span>Issue New Key</span>
          </button>
        } @else {
          <div class="text-[11px] text-[var(--text-muted)] font-mono">
            Secure P2P channels active
          </div>
        }
      </div>

      <!-- Main Panel Viewport -->
      <div class="flex-1 overflow-y-auto p-6 bg-[var(--bg-base)]">
        
        <!-- INVITE LINK TAB -->
        @if (activeSubTab() === 'invite') {
          <div class="max-w-2xl mx-auto space-y-6" id="invite-pane">
            <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
              <h3 class="text-xs font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">
                Direct Node Handshake
              </h3>
              <p class="text-xs text-[var(--text-secondary)] mb-4">
                Linking two separate dashboards without a shared passphrase. Send this generated session payload to the other admin party via secure chats. Once they paste it, the link handshakes securely.
              </p>

              <!-- Generate Section (Step 1) -->
              <div class="p-4 rounded-lg bg-[var(--bg-base)] border border-[var(--border)]/60 mb-6">
                <div class="flex justify-between items-center mb-3">
                  <span class="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Step 1 — Generate Invite Token</span>
                  <span class="text-[10px] text-emerald-400 font-mono">Expires in: 24h</span>
                </div>

                @if (inviteToken()) {
                  <div class="space-y-3">
                    <div class="flex items-center space-x-2">
                      <div class="flex-1 px-3 py-1.5 text-xs font-mono rounded bg-[var(--bg-elevated)] text-[var(--accent)] border border-[var(--border)] select-all truncate">
                        {{ inviteToken() }}
                      </div>
                      <button 
                        (click)="copyToken()" 
                        class="px-3 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-95 flex items-center space-x-1 shrink-0"
                      >
                        @if (copiedToken()) {
                          <lucide-icon name="check" [size]="12"></lucide-icon>
                          <span>Copied</span>
                        } @else {
                          <lucide-icon name="copy" [size]="12"></lucide-icon>
                          <span>Copy</span>
                        }
                      </button>
                    </div>

                    <div class="flex items-center justify-between pt-1">
                      <button 
                        (click)="showQR.set(!showQR())"
                        class="text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center space-x-1"
                      >
                        <lucide-icon name="qr-code" [size]="12"></lucide-icon>
                        <span>{{ showQR() ? 'Hide QR Code' : 'Show Handshake QR Code' }}</span>
                      </button>

                      <button 
                        (click)="generateInvite()"
                        class="text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] font-mono underline"
                      >
                        Regenerate Token
                      </button>
                    </div>

                    <!-- Mock QR Code frame -->
                    @if (showQR()) {
                      <div class="flex justify-center p-4 border border-[var(--border)]/40 bg-white rounded-lg max-w-[160px] mx-auto mt-2">
                        <div class="relative w-28 h-28 bg-[url('https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=tether_handshake')] bg-cover"></div>
                      </div>
                    }
                  </div>
                } @else {
                  <button 
                    (click)="generateInvite()"
                    class="w-full py-2 text-xs font-bold uppercase tracking-wider rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90 transition-opacity"
                  >
                    Generate Invite Link
                  </button>
                }
              </div>

              <!-- Accept Section (Step 2) -->
              <div class="pt-2">
                <span class="block text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider mb-2">Step 2 — Accept & Link Invitation</span>
                <div class="flex items-center space-x-2">
                  <input 
                    type="text"
                    [(ngModel)]="pasteToken"
                    [ngModelOptions]="{standalone: true}"
                    placeholder="Paste tether://invite/abc123xyz... token here"
                    class="flex-1 px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--border-strong)] focus:outline-none"
                  />
                  <button 
                    (click)="acceptInvite()"
                    class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--border-strong)] text-[var(--bg-base)] hover:opacity-95 shrink-0"
                  >
                    Accept & Link
                  </button>
                </div>
              </div>
            </div>
          </div>
        }

        <!-- PAKE TAB -->
        @if (activeSubTab() === 'pake') {
          <div class="max-w-2xl mx-auto space-y-6" id="pake-pane">
            <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
              <h3 class="text-xs font-semibold text-[var(--text-primary)] mb-2 uppercase tracking-wider">
                Zero-Knowledge PAKE Handshake
              </h3>
              <p class="text-xs text-[var(--text-secondary)] mb-4">
                Establish client-to-agent secure sessions over local LAN discovery subnets. The handshake uses <strong>Password Authenticated Key Exchange</strong> to assert absolute encryption without sending the password to the daemon.
              </p>

              <div class="space-y-4">
                <div>
                  <label class="block text-[11px] text-[var(--text-secondary)] mb-1 font-medium">Shared LAN Passphrase</label>
                  <div class="relative">
                    <input 
                      [type]="showPass() ? 'text' : 'password'"
                      [(ngModel)]="passphrase"
                      [ngModelOptions]="{standalone: true}"
                      placeholder="e.g. quantum-tether-block-auth-token-18"
                      class="w-full pl-3 pr-10 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--border-strong)] focus:outline-none font-mono"
                    />
                    <button 
                      (click)="showPass.set(!showPass())"
                      class="absolute right-3 top-2.5 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    >
                      <lucide-icon [name]="showPass() ? 'x' : 'eye'" [size]="12"></lucide-icon>
                    </button>
                  </div>
                </div>

                <div class="flex items-center justify-between pt-2">
                  <div class="text-[10px] text-[var(--text-muted)] flex items-center space-x-1 group relative cursor-help">
                    <lucide-icon name="info" [size]="12"></lucide-icon>
                    <span class="underline decoration-dotted">LAN vs WAN Routing details</span>
                    
                    <!-- Hover Tooltip -->
                    <div class="absolute bottom-6 left-0 hidden group-hover:block bg-[var(--bg-surface)] border border-[var(--border)] rounded p-2.5 shadow-xl w-64 text-[10px] text-[var(--text-secondary)] leading-relaxed z-50">
                      <strong>LAN Discovery:</strong> Multicasts UDP packets on local loopbacks to discover active agents. <br class="my-1"/><strong>WAN Relays:</strong> Connects securely through the cloud broker if behind a NAT.
                    </div>
                  </div>

                  <button 
                    (click)="connectPAKE()"
                    class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90"
                    title="Initialize secure LAN subnet discovery"
                  >
                    Authenticate with PAKE
                  </button>
                </div>
              </div>
            </div>
          </div>
        }

        <!-- NETWORK KEYS TAB -->
        @if (activeSubTab() === 'keys') {
          <div class="space-y-4" id="keys-pane">
            <div class="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]/40">
              <div class="flex justify-between items-center">
                <div>
                  <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">Active Credentials</h3>
                  <p class="text-[11px] text-[var(--text-muted)] mt-0.5">Admin access credentials issued to background processes and team agents.</p>
                </div>
              </div>
            </div>

            <!-- Keys Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              @for (k of state.networkKeys(); track k.id) {
                <div class="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] flex flex-col justify-between">
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <div class="flex items-center space-x-2">
                        <span class="text-xs font-bold text-[var(--text-primary)] font-mono">{{ k.agentName }}</span>
                        <span 
                          class="px-1.5 py-0.2 text-[8px] uppercase tracking-wider font-semibold rounded"
                          [class.bg-emerald-500/10]="k.status === 'active'"
                          [class.text-emerald-400]="k.status === 'active'"
                          [class.bg-red-500/10]="k.status === 'revoked'"
                          [class.text-red-400]="k.status === 'revoked'"
                        >
                          {{ k.status }}
                        </span>
                      </div>
                      <span class="text-[10px] text-[var(--text-muted)] font-semibold uppercase">{{ k.tier }} tier</span>
                    </div>

                    <!-- Key details -->
                    <div class="space-y-1.5 text-[11px] text-[var(--text-secondary)] font-mono mb-4">
                      <div class="flex justify-between">
                        <span>API Token:</span>
                        <span class="text-[var(--text-primary)]">{{ k.key }}</span>
                      </div>
                      <div class="flex justify-between">
                        <span>Issued:</span>
                        <span>{{ k.issuedDate }}</span>
                      </div>
                      <div class="flex justify-between">
                        <span>Last Active:</span>
                        <span>{{ k.lastUsed }}</span>
                      </div>
                    </div>

                    <!-- Usage bar -->
                    @if (k.status === 'active') {
                      <div class="space-y-1 mb-4">
                        <div class="flex justify-between text-[10px] text-[var(--text-muted)] font-mono">
                          <span>Bandwidth Budget Used</span>
                          <span>{{ k.usagePercent }}%</span>
                        </div>
                        <div class="w-full bg-[var(--bg-base)] h-1 rounded-full overflow-hidden border border-[var(--border)]/30">
                          <div 
                            class="h-full bg-[var(--accent)] transition-all duration-300" 
                            [style.width.%]="k.usagePercent"
                          ></div>
                        </div>
                      </div>
                    }
                  </div>

                  <!-- Actions footer -->
                  <div class="flex justify-end space-x-2 pt-2 border-t border-[var(--border)]/20">
                    <button 
                      (click)="rotateKey(k.id)"
                      [disabled]="k.status === 'revoked'"
                      class="px-2 py-1 text-[10px] font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-40"
                    >
                      Rotate Key
                    </button>
                    <button 
                      (click)="revokeKey(k.id)"
                      [disabled]="k.status === 'revoked'"
                      class="px-2 py-1 text-[10px] font-medium rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 disabled:opacity-40"
                    >
                      Revoke Key
                    </button>
                  </div>
                </div>
              }
            </div>
          </div>
        }

      </div>

      <!-- ISSUE NEW KEY MODAL -->
      @if (showIssueKeyModal()) {
        <div class="fixed inset-0 bg-black/60 backdrop-blur-xs z-[100] flex items-center justify-center p-4" id="issue-key-modal">
          <div class="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl max-w-sm w-full p-5 shadow-2xl space-y-4">
            <div class="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
              <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">Issue Admin Key</h3>
              <button (click)="showIssueKeyModal.set(false)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <lucide-icon name="close" [size]="14"></lucide-icon>
              </button>
            </div>

            <form [formGroup]="keyForm" (ngSubmit)="onKeyFormSubmit()" class="space-y-3">
              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Target Agent Name</label>
                <input 
                  type="text"
                  formControlName="agentName"
                  placeholder="e.g. build-executor"
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>

              <div>
                <label class="block text-[11px] text-[var(--text-secondary)] mb-1">Billing Tier</label>
                <select 
                  formControlName="tier"
                  class="w-full px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none"
                >
                  <option value="local">local (LAN Loopbacks)</option>
                  <option value="relay">relay (Broker WAN)</option>
                  <option value="cloud">cloud (Unlimited Telemetry)</option>
                </select>
              </div>

              <div class="flex justify-end space-x-2 pt-2">
                <button 
                  type="button"
                  (click)="showIssueKeyModal.set(false)"
                  class="px-3 py-1.5 text-xs font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  [disabled]="keyForm.invalid"
                  class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] disabled:opacity-50"
                >
                  Confirm Issue
                </button>
              </div>
            </form>
          </div>
        </div>
      }

    </div>
  `,
})
export class Connect {
  state = inject(TetherState);
  activeSubTab = signal<'invite' | 'pake' | 'keys'>('invite');

  // Invite state
  inviteToken = signal<string>('tether://invite/token_a19d28f3e4c85d7b001a18bc9e73b2a59f8c4ea78e');
  copiedToken = signal<boolean>(false);
  showQR = signal<boolean>(false);
  pasteToken = '';

  // PAKE state
  passphrase = '';
  showPass = signal<boolean>(false);

  // Issue key modal state
  showIssueKeyModal = signal<boolean>(false);

  keyForm = new FormGroup({
    agentName: new FormControl('', [Validators.required, Validators.pattern(/^[a-zA-Z0-9_-]+$/)]),
    tier: new FormControl<'local' | 'relay' | 'cloud'>('local', [Validators.required]),
  });

  generateInvite() {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let token = '';
    for (let i = 0; i < 40; i++) {
      token += chars[Math.floor(Math.random() * chars.length)];
    }
    this.inviteToken.set(`tether://invite/${token}`);
    this.copiedToken.set(false);
  }

  copyToken() {
    navigator.clipboard.writeText(this.inviteToken());
    this.copiedToken.set(true);
    setTimeout(() => this.copiedToken.set(false), 2000);
  }

  acceptInvite() {
    if (!this.pasteToken) {
      alert('Please paste a valid invite token before handshaking.');
      return;
    }
    alert(`Handshake initiated with token: ${this.pasteToken.substring(0, 24)}...\nLinked node connection has been committed to SQLite db state. status: healthy.`);
    this.pasteToken = '';
  }

  connectPAKE() {
    if (!this.passphrase) {
      alert('Please enter a shared LAN passphrase to start PAKE.');
      return;
    }
    alert(`PAKE handshake sequence initialized.\nNegotiating secure session key over local subnet loopbacks...\nHandshake SUCCESS.\nAdded secure tunnel link in network state.`);
    this.passphrase = '';
  }

  rotateKey(id: string) {
    this.state.rotateKey(id);
    alert('Admin key rotated. All background processes will need to re-authenticate with the updated credential.');
  }

  revokeKey(id: string) {
    if (confirm('Revoke this admin credential permanently? All linked background integrations using this key will immediately be blocked.')) {
      this.state.revokeKey(id);
    }
  }

  onKeyFormSubmit() {
    if (this.keyForm.invalid) return;
    const name = this.keyForm.value.agentName || '';
    const tier = this.keyForm.value.tier || 'local';

    this.state.issueKey(name, tier);
    this.keyForm.reset({ agentName: '', tier: 'local' });
    this.showIssueKeyModal.set(false);
  }
}
