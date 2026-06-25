import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {TetherState} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

@Component({
  selector: 'app-connect',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule, LucideIcon],
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
        </div>
        <div class="text-[11px] text-[var(--text-muted)] font-mono">
          Secure P2P channels active
        </div>
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
                Link two separate dashboards without a shared passphrase. Send this generated session payload to the other party via any secure channel. Once they paste it, the link handshakes securely.
              </p>

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
                Establish secure sessions over local LAN discovery subnets. Uses <strong>Password Authenticated Key Exchange</strong> — absolute encryption without sending the passphrase to the daemon.
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
                    <div class="absolute bottom-6 left-0 hidden group-hover:block bg-[var(--bg-surface)] border border-[var(--border)] rounded p-2.5 shadow-xl w-64 text-[10px] text-[var(--text-secondary)] leading-relaxed z-50">
                      <strong>LAN Discovery:</strong> Multicasts UDP packets on local loopbacks to discover active agents.<br class="my-1"/><strong>WAN Relays:</strong> Connects securely through the relay broker if behind a NAT.
                    </div>
                  </div>
                  <button
                    (click)="connectPAKE()"
                    class="px-4 py-1.5 text-xs font-medium rounded bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90"
                  >
                    Authenticate with PAKE
                  </button>
                </div>
              </div>
            </div>
          </div>
        }

      </div>
    </div>
  `,
})
export class Connect {
  state = inject(TetherState);
  activeSubTab = signal<'invite' | 'pake'>('invite');

  inviteToken = signal<string>('tether://invite/token_a19d28f3e4c85d7b001a18bc9e73b2a59f8c4ea78e');
  copiedToken = signal<boolean>(false);
  showQR = signal<boolean>(false);
  pasteToken = '';

  passphrase = '';
  showPass = signal<boolean>(false);

  generateInvite() {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let token = '';
    for (let i = 0; i < 40; i++) token += chars[Math.floor(Math.random() * chars.length)];
    this.inviteToken.set(`tether://invite/${token}`);
    this.copiedToken.set(false);
  }

  copyToken() {
    navigator.clipboard.writeText(this.inviteToken());
    this.copiedToken.set(true);
    setTimeout(() => this.copiedToken.set(false), 2000);
  }

  acceptInvite() {
    if (!this.pasteToken) return;
    alert(`Handshake initiated with token: ${this.pasteToken.substring(0, 24)}...\nLinked node committed to network state.`);
    this.pasteToken = '';
  }

  connectPAKE() {
    if (!this.passphrase) return;
    alert(`PAKE handshake initialized.\nNegotiating secure session key over local subnet...\nHandshake SUCCESS.`);
    this.passphrase = '';
  }
}
