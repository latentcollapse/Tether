import {ChangeDetectionStrategy, Component, ElementRef, ViewChild, computed, effect, inject, signal} from '@angular/core';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {TetherState, AgentNode, NetworkEdge} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

interface DiscoveredAgent {
  agent: string;
  source: 'tmux' | 'history' | 'presence';
  detail: string;
}

@Component({
  selector: 'app-network',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, ReactiveFormsModule, LucideIcon],
  template: `
    <div class="flex flex-col h-full bg-[var(--bg-base)] text-[var(--text-primary)]" id="network-root">
      <!-- Tabs header -->
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-2 bg-[var(--bg-surface)]">
        <div class="flex space-x-2">
          <button
            id="tab-graph"
            (click)="activeTab.set('graph')"
            [class]="activeTab() === 'graph' 
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]' 
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Network Graph
          </button>
          <button
            id="tab-register"
            (click)="activeTab.set('register')"
            [class]="activeTab() === 'register'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Register Node
          </button>
          <button
            id="tab-terminals"
            (click)="onTerminalsTab()"
            [class]="activeTab() === 'terminals'
              ? 'px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--bg-elevated)] border border-[var(--border-strong)] text-[var(--text-primary)]'
              : 'px-3 py-1.5 text-xs font-medium rounded-md text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]/50'"
          >
            Terminals
          </button>
        </div>

        <!-- Feed Control Indicator -->
        <div class="text-[11px] text-[var(--text-muted)] flex items-center space-x-2">
          <span class="inline-block w-2 h-2 rounded-full bg-[var(--semantic-ok)] animate-pulse"></span>
          <span>Feed Live: {{ state.feed().length }} routes active</span>
        </div>
      </div>

      <!-- Main Layout: Content and Real-time feed -->
      <div class="flex-1 flex overflow-hidden min-h-0">
        
        <!-- Tab Content -->
        <div class="flex-1 overflow-auto relative p-6">
          
          <!-- Graph View -->
          @if (activeTab() === 'graph') {
            <div class="w-full h-full min-h-[480px] relative rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] overflow-hidden" 
                 #canvasContainer
                 (mousemove)="onCanvasMouseMove($event)"
                 (mouseup)="onCanvasMouseUp()"
                 id="graph-viewport">

              <!-- Quick-add agent button + inline popover -->
              <div class="absolute top-3 right-3 z-30 flex flex-col items-end space-y-2">
                <button
                  (click)="showQuickAdd.set(!showQuickAdd())"
                  class="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-bold bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90 shadow-lg transition-all"
                  title="Add agent to graph"
                >
                  <lucide-icon name="plus" [size]="13"></lucide-icon>
                  <span>Add Agent</span>
                </button>

                @if (showQuickAdd()) {
                  <div class="bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-lg shadow-2xl p-3 w-64 animate-fade-in">
                    <div class="flex items-center justify-between mb-2">
                      <p class="text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">Add Agent</p>
                      <button (click)="refreshDiscovery()" class="text-[9px] text-[var(--text-muted)] hover:text-[var(--accent)] flex items-center space-x-1" title="Re-scan for agents">
                        <lucide-icon name="refresh-cw" [size]="10"></lucide-icon>
                      </button>
                    </div>

                    <!-- Discovered agents — one click adds + connects -->
                    @if (availableToAdd().length > 0) {
                      <div class="space-y-1 max-h-44 overflow-y-auto mb-2">
                        @for (a of availableToAdd(); track a.agent) {
                          <button
                            (click)="quickAddFromDropdown(a.agent)"
                            class="w-full flex items-center justify-between px-2.5 py-1.5 rounded text-xs text-[var(--text-primary)] hover:bg-[var(--accent-dim)] hover:text-[var(--accent)] transition-colors border border-transparent hover:border-[var(--accent)]/30 group"
                          >
                            <span class="font-mono">{{ a.agent }}</span>
                            <span class="text-[8px] px-1.5 py-0.5 rounded-full uppercase tracking-wide"
                                  [class.bg-emerald-500/15]="a.source === 'tmux'"
                                  [class.text-emerald-400]="a.source === 'tmux'"
                                  [class.bg-blue-500/10]="a.source === 'history'"
                                  [class.text-blue-400]="a.source === 'history'"
                                  [class.bg-purple-500/10]="a.source === 'presence'"
                                  [class.text-purple-400]="a.source === 'presence'"
                            >{{ sourceLabel(a.source) }}</span>
                          </button>
                        }
                      </div>
                    } @else {
                      <p class="text-[9px] text-[var(--text-muted)] mb-2 px-1">No new agents detected. Type a name to add one manually.</p>
                    }

                    <!-- Manual entry, always available -->
                    <form [formGroup]="quickAddForm" (ngSubmit)="submitQuickAdd()" class="border-t border-[var(--border)] pt-2 space-y-2">
                      <input
                        type="text"
                        formControlName="name"
                        placeholder="Agent name (e.g. gemini)"
                        class="w-full bg-[var(--bg-base)] border border-[var(--border)] text-xs px-2.5 py-1.5 rounded focus:outline-none focus:border-[var(--accent)] text-[var(--text-primary)] placeholder-[var(--text-muted)]"
                        autocomplete="off"
                      />
                      <div class="flex space-x-2">
                        <button type="button" (click)="showQuickAdd.set(false)" class="flex-1 py-1 rounded border border-[var(--border)] text-[10px] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]">Cancel</button>
                        <button type="submit" [disabled]="quickAddForm.invalid" class="flex-1 py-1 rounded bg-[var(--accent)] text-[var(--bg-base)] text-[10px] font-bold disabled:opacity-50 hover:opacity-90">Add &amp; Connect</button>
                      </div>
                    </form>
                  </div>
                }
              </div>

              <!-- Absolute layer for SVG connection lines -->
              <svg class="absolute inset-0 pointer-events-none w-full h-full z-10">
                @for (edge of state.edges(); track edge.id) {
                  @let fromNode = getNode(edge.from);
                  @let toNode = getNode(edge.to);
                  @if (fromNode && toNode) {
                    <!-- Line path -->
                    <line
                      [attr.x1]="fromNode.x + 80"
                      [attr.y1]="fromNode.y + 40"
                      [attr.x2]="toNode.x + 80"
                      [attr.y2]="toNode.y + 40"
                      [attr.stroke]="getEdgeColor(edge.status)"
                      [attr.stroke-dasharray]="edge.status === 'degraded' ? '4 4' : 'none'"
                      [attr.stroke-width]="getEdgeWidth(edge.status)"
                    />

                    <!-- Midpoint indicator click box (Interactive broken/degraded edge) -->
                    @let midX = (fromNode.x + toNode.x) / 2 + 80;
                    @let midY = (fromNode.y + toNode.y) / 2 + 40;
                    
                    <g class="pointer-events-auto cursor-pointer" (click)="selectEdge(edge, $event)">
                      <circle
                        [attr.cx]="midX"
                        [attr.cy]="midY"
                        r="12"
                        [attr.fill]="getEdgeBg(edge.status)"
                        [attr.stroke]="getEdgeColor(edge.status)"
                        stroke-width="1"
                      />
                      @if (edge.status === 'broken') {
                        <path [attr.d]="'M' + (midX - 4) + ',' + (midY - 4) + ' L' + (midX + 4) + ',' + (midY + 4) + ' M' + (midX + 4) + ',' + (midY - 4) + ' L' + (midX - 4) + ',' + (midY + 4)" stroke="white" stroke-width="1.5" />
                      } @else if (edge.status === 'degraded') {
                        <circle [attr.cx]="midX" [attr.cy]="midY" r="2" fill="white" />
                        <line [attr.x1]="midX" [attr.y1]="midY - 4" [attr.x2]="midX" [attr.y2]="midY + 1" stroke="white" stroke-width="1.5" />
                      } @else {
                        <circle [attr.cx]="midX" [attr.cy]="midY" r="2.5" fill="white" />
                      }
                    </g>
                  }
                }
              </svg>

              <!-- Routing overlay badge -->
              @if (selectedNodeForRouting(); as source) {
                <div class="absolute top-3 left-3 bg-[var(--bg-surface)] border border-[var(--accent)] rounded-lg px-3 py-1.5 text-xs flex items-center space-x-2.5 z-30 shadow-lg animate-pulse">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-[var(--accent)]"></span>
                  <span>Routing connection from <strong class="text-[var(--accent)] font-mono">{{ source.name }}</strong>. Click another node card to connect.</span>
                  <button (click)="cancelRouting()" class="px-2 py-0.5 rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 text-[10px]">Cancel</button>
                </div>
              }

              <!-- Node Cards layer -->
              @for (node of state.nodes(); track node.id) {
                <div
                  [id]="'node-' + node.id"
                  class="absolute p-3 rounded-lg border bg-[var(--bg-elevated)] z-20 select-none transition-shadow hover:shadow-md flex flex-col justify-between overflow-hidden"
                  [class.cursor-grab]="!selectedNodeForRouting()"
                  [class.active:cursor-grabbing]="!selectedNodeForRouting()"
                  [class.cursor-pointer]="selectedNodeForRouting()"
                  [class.ring-2]="selectedNodeForRouting()?.id === node.id"
                  [class.ring-[var(--accent)]]="selectedNodeForRouting()?.id === node.id"
                  [class.border-red-500]="node.status === 'offline' && selectedNodeForRouting()?.id !== node.id"
                  [class.border-yellow-500]="node.status === 'degraded' && selectedNodeForRouting()?.id !== node.id"
                  [class.border-[var(--border)]]="node.status === 'online' && selectedNodeForRouting()?.id !== node.id"
                  [class.hover:border-[var(--accent)]]="selectedNodeForRouting() && selectedNodeForRouting()?.id !== node.id"
                  [style.left.px]="node.x"
                  [style.top.px]="node.y"
                  [style.width.px]="node.width || 160"
                  [style.height.px]="node.height || 110"
                  (mousedown)="onNodeMouseDown($event, node)"
                >
                  <div>
                    <div class="flex items-center justify-between mb-1.5">
                      <span class="text-xs font-semibold text-[var(--text-primary)] truncate max-w-[105px]" [title]="node.name">
                        {{ node.name }}
                      </span>
                      <span 
                        class="w-2.5 h-2.5 rounded-full" 
                        [class.bg-[var(--semantic-ok)]]="node.status === 'online'"
                        [class.bg-[var(--semantic-warn)]]="node.status === 'degraded'"
                        [class.bg-[var(--semantic-err)]]="node.status === 'offline'"
                      ></span>
                    </div>

                    <div class="text-[10px] text-[var(--text-secondary)] space-y-0.5">
                      <div class="flex justify-between">
                        <span>Msgs Today:</span>
                        <span class="font-mono text-[var(--text-primary)]">{{ node.msgsToday }}</span>
                      </div>
                      <div class="flex justify-between">
                        <span>Seen:</span>
                        <span class="text-[var(--text-muted)]">{{ node.lastSeen }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Quick Actions -->
                  <div class="pt-1.5 border-t border-[var(--border)]/30 flex justify-between relative z-10">
                    <button
                      class="text-[9px] text-[var(--accent)] hover:bg-[var(--accent-dim)] px-1 py-0.5 rounded font-semibold"
                      (click)="startRouting(node, $event)"
                      title="Route connection from this node to another"
                    >
                      Route Link
                    </button>
                    @if (isNodeOnline(node.name)) {
                      <button
                        class="text-[9px] text-red-400/80 hover:text-red-400 hover:bg-red-500/10 px-1 py-0.5 rounded font-semibold"
                        (click)="disconnectNode(node.name, $event)"
                        title="Stop this agent's daemon"
                      >Disconnect</button>
                    } @else {
                      <button
                        class="text-[9px] text-emerald-400/80 hover:text-emerald-400 hover:bg-emerald-500/10 px-1 py-0.5 rounded font-semibold"
                        (click)="connectNode(node.name, $event)"
                        title="Start this agent's ping daemon"
                      >Connect</button>
                    }
                    <button
                      class="text-[9px] text-red-400/40 hover:text-red-400 hover:bg-red-500/10 px-1 py-0.5 rounded"
                      (click)="deleteNode(node.id, $event)"
                      title="De-register node from local dashboard"
                    >
                      Remove
                    </button>
                  </div>

                  <!-- Draggable Resize Handle -->
                  <div 
                    class="absolute bottom-0 right-0 w-3.5 h-3.5 cursor-se-resize flex items-end justify-end p-0.5 z-20"
                    (mousedown)="onResizeMouseDown($event, node)"
                    title="Drag to resize card"
                  >
                    <svg class="w-2.5 h-2.5 text-[var(--text-muted)] hover:text-[var(--accent)]" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5">
                      <line x1="8" y1="2" x2="2" y2="8" />
                      <line x1="8" y1="5" x2="5" y2="8" />
                    </svg>
                  </div>
                </div>
              }

              <!-- Inline Diagnostic / Connection Control Panel -->
              @if (state.activeDiagnosticEdge(); as activeEdge) {
                <div 
                  class="absolute z-40 bg-[var(--bg-surface)] rounded-lg p-4 shadow-xl max-w-[340px] border"
                  [class.border-red-500]="activeEdge.status === 'broken'"
                  [class.border-yellow-500]="activeEdge.status === 'degraded'"
                  [class.border-[var(--accent)]]="activeEdge.status === 'healthy'"
                  [style.left.px]="getPanelX()"
                  [style.top.px]="getPanelY()"
                  id="diagnostic-popup"
                >
                  <div class="flex items-center justify-between mb-2 pb-1 border-b border-[var(--border)]">
                    <div class="flex items-center space-x-1.5 text-xs font-semibold"
                         [class.text-red-400]="activeEdge.status === 'broken'"
                         [class.text-yellow-400]="activeEdge.status === 'degraded'"
                         [class.text-[var(--accent)]]="activeEdge.status === 'healthy'"
                    >
                      @if (activeEdge.status === 'healthy') {
                        <lucide-icon name="check-circle" [size]="14"></lucide-icon>
                        <span>Active Connection</span>
                      } @else {
                        <lucide-icon name="error" [size]="14"></lucide-icon>
                        <span>Degraded/Broken Link</span>
                      }
                    </div>
                    <button (click)="state.activeDiagnosticEdge.set(null)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-0.5">
                      <lucide-icon name="close" [size]="12"></lucide-icon>
                    </button>
                  </div>

                  <div class="space-y-2 text-xs">
                    <div class="flex justify-between text-[11px] font-mono mb-1 text-[var(--text-primary)]">
                      <span>{{ activeEdge.from }}</span>
                      <span>→</span>
                      <span>{{ activeEdge.to }}</span>
                    </div>

                    <div class="flex justify-between text-[11px]">
                      <span class="text-[var(--text-secondary)]">Status:</span>
                      <span class="font-bold uppercase"
                            [class.text-emerald-500]="activeEdge.status === 'healthy'"
                            [class.text-yellow-500]="activeEdge.status === 'degraded'"
                            [class.text-red-500]="activeEdge.status === 'broken'"
                      >
                        {{ activeEdge.status }}
                      </span>
                    </div>

                    @if (activeEdge.status !== 'healthy') {
                      <div class="flex justify-between text-[11px]">
                        <span class="text-[var(--text-secondary)]">Last Successful:</span>
                        <span class="font-mono text-[var(--text-primary)]">{{ activeEdge.lastSeen || 'Unknown' }}</span>
                      </div>
                      <div class="p-2 rounded bg-[var(--bg-base)] text-[11px] font-mono text-[var(--text-secondary)] break-all border border-[var(--border)]">
                        <span class="text-red-400 font-semibold block mb-0.5">Diagnostic Error:</span>
                        {{ activeEdge.error }}
                      </div>
                    } @else {
                      <div class="p-2 rounded bg-[var(--bg-base)] text-[11px] text-[var(--text-secondary)] border border-[var(--border)]">
                        This peer-to-peer data channel is fully operational. Bidirectional packets are flowing under the current cryptographic handshake protocol.
                      </div>
                    }

                    <div class="flex space-x-2 pt-1">
                      @if (activeEdge.status === 'healthy') {
                        <button 
                          (click)="killConnection(activeEdge.id)"
                          class="flex-1 py-1.5 text-center text-[11px] font-medium rounded bg-red-600 hover:bg-red-500 text-white transition-colors flex items-center justify-center space-x-1"
                        >
                          <lucide-icon name="trash" [size]="12"></lucide-icon>
                          <span>Kill Connection</span>
                        </button>
                      } @else {
                        <button 
                          (click)="retryConnection(activeEdge.id)"
                          class="flex-1 py-1.5 text-center text-[11px] font-medium rounded bg-emerald-600 hover:bg-emerald-500 text-white transition-colors"
                        >
                          @if (isRetrying()) {
                            Handshaking...
                          } @else {
                            Retry Connection
                          }
                        </button>
                        <button 
                          (click)="viewLogs(activeEdge)"
                          class="px-2.5 py-1.5 text-[11px] font-medium rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                        >
                          View Logs
                        </button>
                      }
                    </div>
                  </div>
                </div>
              }
            </div>
          }

          <!-- Register Node Tab -->
          @if (activeTab() === 'register') {
            <div class="max-w-2xl mx-auto space-y-6" id="register-pane">

              <!-- Live discovery -->
              <div class="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5">
                <div class="flex items-start space-x-3">
                  <div class="p-2 rounded-lg bg-emerald-500/15 text-emerald-400 mt-0.5">
                    <lucide-icon name="terminal" [size]="16"></lucide-icon>
                  </div>
                  <div class="flex-1">
                    <div class="flex items-center justify-between">
                      <h4 class="text-xs font-semibold text-emerald-400">Detected Agents</h4>
                      <button (click)="refreshDiscovery()" class="text-[10px] text-[var(--text-muted)] hover:text-emerald-400 flex items-center space-x-1">
                        <lucide-icon name="refresh-cw" [size]="11"></lucide-icon>
                        <span>Rescan</span>
                      </button>
                    </div>
                    <p class="text-[11px] text-[var(--text-secondary)] mt-0.5">
                      Live tmux panes, recent message senders, and registered daemons. One click adds and connects — no port needed.
                    </p>

                    @if (availableToAdd().length > 0) {
                      <div class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        @for (agent of availableToAdd(); track agent.agent) {
                          <div class="p-2.5 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] flex items-center justify-between">
                            <div>
                              <div class="text-xs font-bold font-mono">{{ agent.agent }}</div>
                              <div class="text-[9px] text-[var(--text-muted)]">{{ sourceLabel(agent.source) }} · {{ agent.detail }}</div>
                            </div>
                            <button
                              (click)="quickAddFromDropdown(agent.agent)"
                              class="px-2 py-1 text-[10px] font-medium rounded bg-[var(--accent)] hover:opacity-90 text-[var(--bg-base)] whitespace-nowrap"
                            >
                              Add &amp; Connect
                            </button>
                          </div>
                        }
                      </div>
                    } @else {
                      <p class="mt-3 text-[11px] text-[var(--text-muted)] font-mono">
                        No new agents detected. Add one manually below.
                      </p>
                    }
                  </div>
                </div>
              </div>

              <!-- Manual Registration — name only -->
              <div class="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]">
                <h3 class="text-xs font-semibold text-[var(--text-primary)] mb-2 uppercase tracking-wider">
                  Add by Name
                </h3>
                <p class="text-[11px] text-[var(--text-secondary)] mb-4">
                  Just type the agent's name. Tether spawns a delivery daemon, finds the right pane automatically, and assigns a port for you.
                </p>

                <form [formGroup]="registerForm" (ngSubmit)="onRegisterSubmit()" class="flex items-start space-x-3">
                  <div class="flex-1">
                    <input
                      type="text"
                      formControlName="agentName"
                      placeholder="e.g. gemini"
                      class="w-full px-3 py-2 text-sm rounded border border-[var(--border)] bg-[var(--bg-base)] text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none font-mono"
                    />
                    @if (registerForm.get('agentName')?.invalid && registerForm.get('agentName')?.touched) {
                      <span class="text-[9px] text-red-400 mt-1 block">Name required (letters, numbers, hyphens, underscores).</span>
                    }
                  </div>
                  <button
                    type="submit"
                    [disabled]="registerForm.invalid"
                    class="px-4 py-2 text-xs font-bold rounded bg-[var(--accent)] text-[var(--bg-base)] disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity whitespace-nowrap"
                  >
                    Register &amp; Connect
                  </button>
                </form>
              </div>

            </div>
          }

          <!-- Terminals Tab — live Konsole tabs, one-click bind (KDE) -->
          @if (activeTab() === 'terminals') {
            <div class="max-w-3xl mx-auto space-y-4" id="terminals-pane">
              <div class="flex items-center justify-between">
                <div>
                  <h3 class="text-xs font-semibold text-[var(--text-primary)] uppercase tracking-wider">Live Terminal Tabs</h3>
                  <p class="text-[11px] text-[var(--text-secondary)] mt-0.5">
                    Detected Konsole tabs. Bind one to an agent and tmails autofire into it — no tmux, no port.
                  </p>
                </div>
                <button (click)="state.loadKonsoleSessions()" class="text-[10px] text-[var(--text-muted)] hover:text-[var(--accent)] flex items-center space-x-1">
                  <lucide-icon name="refresh-cw" [size]="12"></lucide-icon><span>Rescan</span>
                </button>
              </div>

              @if (!state.konsoleAvailable()) {
                <div class="p-4 rounded-xl border border-yellow-500/30 bg-yellow-500/5 text-[11px] text-yellow-300">
                  Konsole D-Bus not detected on this host. Terminal auto-wire is KDE/Konsole-only for now
                  (kitty / WezTerm / Windows Terminal drivers planned). Use Register Node in the meantime.
                </div>
              } @else if (state.konsoleSessions().length === 0) {
                <div class="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] text-[11px] text-[var(--text-muted)] font-mono">
                  No Konsole tabs detected. Open a tab and launch an agent in it, then Rescan.
                </div>
              } @else {
                <div class="space-y-2">
                  @for (s of state.konsoleSessions(); track s.session) {
                    <div class="p-3 rounded-lg border border-[var(--border)] bg-[var(--bg-surface)] flex items-center justify-between">
                      <div class="min-w-0 flex-1">
                        <div class="flex items-center space-x-2">
                          <span class="text-xs font-mono font-bold text-[var(--text-primary)]">{{ s.session }}</span>
                          @if (s.boundAgent) {
                            <span class="text-[8px] px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 uppercase tracking-wide">bound → {{ s.boundAgent }}</span>
                          } @else if (s.ambiguous) {
                            <span class="text-[8px] px-1.5 py-0.5 rounded-full bg-yellow-500/15 text-yellow-400 uppercase tracking-wide">tmux-nested</span>
                          } @else if (s.guessedAgent) {
                            <span class="text-[8px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 uppercase tracking-wide">looks like {{ s.guessedAgent }}</span>
                          }
                        </div>
                        <div class="text-[10px] text-[var(--text-muted)] font-mono truncate mt-0.5">{{ s.proc }} · {{ s.cmdline }}</div>
                      </div>

                      <div class="flex items-center space-x-2 ml-3">
                        @if (s.boundAgent) {
                          <button (click)="state.unbindKonsole(s.boundAgent!)" class="px-2 py-1 text-[10px] rounded border border-[var(--border)] text-red-400/80 hover:text-red-400 hover:bg-red-500/10">Unbind</button>
                        } @else {
                          <select #sel class="bg-[var(--bg-base)] border border-[var(--border)] text-[11px] px-2 py-1 rounded text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]">
                            <option value="">bind to…</option>
                            @for (a of state.registryAgents(); track a.id) {
                              <option [value]="a.id" [selected]="a.id === s.guessedAgent">{{ a.id }}</option>
                            }
                          </select>
                          <button
                            (click)="bindSelected(s, sel.value)"
                            [disabled]="s.ambiguous"
                            class="px-2 py-1 text-[10px] font-bold rounded bg-[var(--accent)] text-[var(--bg-base)] disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90"
                            [title]="s.ambiguous ? 'Run the agent directly in the tab (not inside tmux) to bind' : 'Bind this tab to the selected agent'"
                          >Bind</button>
                        }
                      </div>
                    </div>
                  }
                </div>
              }
            </div>
          }

        </div>

        <!-- Real-Time Feed (Right Sidebar) -->
        @if (state.feedVisible()) {
          <div 
            class="w-[280px] border-l border-[var(--border)] bg-[var(--bg-surface)] flex flex-col h-full overflow-hidden transition-all duration-300"
            (mouseenter)="onFeedMouseEnter()"
            (mouseleave)="onFeedMouseLeave()"
            id="realtime-feed-sidebar"
          >
            <!-- Sidebar Header -->
            <div class="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
              <div class="flex items-center space-x-2">
                <span class="inline-block w-2 h-2 rounded-full bg-emerald-500" [class.animate-pulse]="!state.feedPaused()"></span>
                <h3 class="text-xs font-semibold uppercase tracking-wider text-[var(--text-primary)]">Real-time Feed</h3>
              </div>
              <button 
                (click)="state.feedVisible.set(false)" 
                class="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
                title="Collapse feed"
              >
                <lucide-icon name="chevrons-right" [size]="14"></lucide-icon>
              </button>
            </div>

            <!-- Feed Content -->
            <div class="flex-1 overflow-y-auto p-3 space-y-2 min-h-0" #feedScrollContainer>
              @for (item of state.feed(); track item.id) {
                <div class="p-2 rounded bg-[var(--bg-base)] border border-[var(--border)]/40 hover:border-[var(--border)] transition-all">
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-[9px] font-mono text-[var(--text-muted)]">{{ item.timestamp }}</span>
                    <span 
                      class="px-1 py-0.2 rounded text-[8px] font-medium"
                      [class.bg-blue-500/10]="item.type === 'board'"
                      [class.text-blue-400]="item.type === 'board'"
                      [class.bg-[var(--accent-dim)]]="item.type === 'messages'"
                      [class.text-[var(--accent)]]="item.type === 'messages'"
                      [class.bg-purple-500/10]="item.type === 'task'"
                      [class.text-purple-400]="item.type === 'task'"
                      [class.bg-yellow-500/10]="item.type === 'whiteboard'"
                      [class.text-yellow-400]="item.type === 'whiteboard'"
                    >
                      {{ item.type }}
                    </span>
                  </div>

                  <div class="text-[11px] font-medium text-[var(--text-secondary)] break-all mb-0.5">
                    {{ item.route }}
                  </div>

                  <div class="flex items-center justify-between mt-1 text-[10px] text-[var(--text-muted)] font-mono">
                    <span class="truncate max-w-[150px]">{{ item.handle }}</span>
                    <button 
                      (click)="copyHandle(item.handle)" 
                      class="hover:text-[var(--text-primary)] p-0.5"
                      title="Copy handle code"
                    >
                      @if (copiedHandleId() === item.handle) {
                        <lucide-icon name="check" [size]="10" class="text-emerald-500"></lucide-icon>
                      } @else {
                        <lucide-icon name="copy" [size]="10"></lucide-icon>
                      }
                    </button>
                  </div>
                </div>
              }
            </div>

            <!-- Pause status indicator -->
            @if (state.feedPaused()) {
              <div class="p-2 text-center text-[10px] bg-yellow-500/10 text-yellow-500 border-t border-[var(--border)]">
                Feed updates paused (Hovering)
              </div>
            }
          </div>
        } @else {
          <!-- Tiny collapsed strip that pulses on update -->
          <div 
            (click)="state.feedVisible.set(true)"
            class="w-3 bg-[var(--bg-surface)] border-l border-[var(--border)] hover:bg-[var(--bg-elevated)] cursor-pointer flex flex-col items-center justify-center relative group"
            title="Expand real-time feed"
          >
            <div class="absolute w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            <div class="text-[9px] text-[var(--text-muted)] select-none font-semibold uppercase tracking-widest writing-vertical absolute top-12 opacity-0 group-hover:opacity-100 transition-opacity">
              EXPAND FEED
            </div>
          </div>
        }

      </div>
    </div>
  `,
  styles: `
    .writing-vertical {
      writing-mode: vertical-rl;
    }
  `
})
export class Network {
  state = inject(TetherState);
  activeTab = signal<'graph' | 'register' | 'terminals'>('graph');
  // Agents discoverable right now (tmux/history/presence) not yet on the graph
  discovered = signal<DiscoveredAgent[]>([]);
  showQuickAdd = signal<boolean>(false);
  quickAddForm = new FormGroup({
    name: new FormControl('', [Validators.required, Validators.pattern(/^[a-zA-Z0-9_-]+$/)]),
  });

  // Candidates not already placed on the graph
  availableToAdd = computed<DiscoveredAgent[]>(() => {
    const graphNames = new Set(this.state.nodes().map(n => n.name));
    return this.discovered().filter(d => !graphNames.has(d.agent));
  });

  // Connection routing signals and methods
  selectedNodeForRouting = signal<AgentNode | null>(null);

  startRouting(node: AgentNode, event: MouseEvent) {
    event.stopPropagation();
    this.selectedNodeForRouting.set(node);
  }

  cancelRouting() {
    this.selectedNodeForRouting.set(null);
  }

  completeManualRoute(targetNode: AgentNode) {
    const sourceNode = this.selectedNodeForRouting();
    if (!sourceNode || sourceNode.id === targetNode.id) {
      this.selectedNodeForRouting.set(null);
      return;
    }
    // createRoute persists to DB and adds the edge to state
    this.state.createRoute(sourceNode.name, targetNode.name);
    this.selectedNodeForRouting.set(null);
  }

  // Dragging & Resizing signals
  draggingNode = signal<AgentNode | null>(null);
  dragOffset = { x: 0, y: 0 };
  resizingNode = signal<AgentNode | null>(null);
  resizeStartSize = { w: 160, h: 110 };
  resizeStartMouse = { x: 0, y: 0 };

  onResizeMouseDown(event: MouseEvent, node: AgentNode) {
    event.stopPropagation();
    event.preventDefault();
    this.resizingNode.set(node);
    this.resizeStartSize = {
      w: node.width || 160,
      h: node.height || 110
    };
    this.resizeStartMouse = {
      x: event.clientX,
      y: event.clientY
    };
  }

  // Retrying signals
  isRetrying = signal<boolean>(false);
  copiedHandleId = signal<string | null>(null);

  // Manual registration — name only; the dashboard handles port + delivery
  registerForm = new FormGroup({
    agentName: new FormControl('', [Validators.required, Validators.pattern(/^[a-zA-Z0-9_-]+$/)]),
  });

  @ViewChild('feedScrollContainer') feedScrollContainer!: ElementRef<HTMLDivElement>;

  // Auto-scroll logic for real-time feed
  constructor() {
    effect(() => {
      this.state.feed();
      setTimeout(() => {
        if (this.feedScrollContainer && !this.state.feedPaused()) {
          const el = this.feedScrollContainer.nativeElement;
          el.scrollTop = el.scrollHeight;
        }
      }, 50);
    });

    // Discover agents available to register (tmux + history + presence)
    if (typeof window !== 'undefined') {
      this.refreshDiscovery();
      // Re-scan periodically so newly-launched agents appear without a reload
      setInterval(() => this.refreshDiscovery(), 10000);
    }
  }

  refreshDiscovery() {
    fetch('/api/discover')
      .then(r => r.json())
      .then((data: { agents: DiscoveredAgent[] }) => this.discovered.set(data.agents || []))
      .catch(() => this.discovered.set([]));
  }

  onTerminalsTab() {
    this.activeTab.set('terminals');
    this.state.loadKonsoleSessions();
  }

  bindSelected(session: any, agentId: string) {
    if (!agentId || session.ambiguous) return;
    this.state.bindKonsole(agentId, session.service, session.session);
  }

  sourceLabel(source: string): string {
    return source === 'tmux' ? 'live · tmux'
      : source === 'presence' ? 'registered'
      : 'recent';
  }

  // One-click add from the discovery dropdown: register + spawn daemon
  quickAddFromDropdown(name: string) {
    this.state.registerAndConnect(name);
    this.showQuickAdd.set(false);
    this.refreshDiscovery();
  }

  // Manual name entry (fresh agent not yet discoverable)
  submitQuickAdd() {
    if (this.quickAddForm.invalid) return;
    const name = this.quickAddForm.value.name?.trim() || '';
    if (!name) return;
    this.state.registerAndConnect(name);
    this.quickAddForm.reset();
    this.showQuickAdd.set(false);
  }

  isNodeOnline(agentName: string): boolean {
    return this.state.presenceMap()[agentName]?.status === 'online';
  }

  connectNode(agentName: string, event: MouseEvent) {
    event.stopPropagation();
    this.state.connectAgent(agentName);
  }

  disconnectNode(agentName: string, event: MouseEvent) {
    event.stopPropagation();
    this.state.disconnectAgent(agentName);
  }

  onRegisterSubmit() {
    if (this.registerForm.invalid) return;
    const name = (this.registerForm.value.agentName || '').trim();
    if (!name) return;
    this.state.registerAndConnect(name);
    this.registerForm.reset();
    this.refreshDiscovery();
    this.activeTab.set('graph');
  }

  getNode(name: string): AgentNode | undefined {
    return this.state.nodes().find(n => n.name === name || n.id === name);
  }

  // Visual helper tokens mapping
  getEdgeColor(status: 'healthy' | 'degraded' | 'broken'): string {
    const vars = this.state.themeVariables();
    return status === 'healthy' ? vars['--semantic-ok'] : status === 'degraded' ? vars['--semantic-warn'] : vars['--semantic-err'];
  }

  getEdgeBg(status: 'healthy' | 'degraded' | 'broken'): string {
    const vars = this.state.themeVariables();
    return status === 'healthy' ? vars['--bg-surface'] : status === 'degraded' ? vars['--bg-elevated'] : vars['--bg-base'];
  }

  getEdgeWidth(status: 'healthy' | 'degraded' | 'broken'): string {
    return status === 'broken' ? '2' : status === 'degraded' ? '1.5' : '1.5';
  }

  // Select a diagnostic broken edge
  selectEdge(edge: NetworkEdge, event: MouseEvent) {
    event.stopPropagation();
    this.state.activeDiagnosticEdge.set(edge);
  }

  // Diagnostic offsets inside viewport boundaries
  getPanelX(): number {
    const active = this.state.activeDiagnosticEdge();
    if (!active) return 0;
    const from = this.getNode(active.from);
    const to = this.getNode(active.to);
    if (!from || !to) return 0;
    return Math.max(10, Math.min(600, (from.x + to.x) / 2 - 80));
  }

  getPanelY(): number {
    const active = this.state.activeDiagnosticEdge();
    if (!active) return 0;
    const from = this.getNode(active.from);
    const to = this.getNode(active.to);
    if (!from || !to) return 0;
    return Math.max(10, Math.min(400, (from.y + to.y) / 2 + 10));
  }

  killConnection(edgeId: string) {
    if (confirm('Are you sure you want to kill this agent connection?')) {
      this.state.edges.update(edges => edges.filter(e => e.id !== edgeId));
      this.state.activeDiagnosticEdge.set(null);
    }
  }

  retryConnection(edgeId: string) {
    if (this.isRetrying()) return;
    this.isRetrying.set(true);
    setTimeout(() => {
      this.state.retryDiagnosticConnection(edgeId);
      this.isRetrying.set(false);
    }, 1500);
  }

  viewLogs(edge: NetworkEdge) {
    alert(`Streaming agent logs for: ${edge.from} -> ${edge.to}\nLast state: ${edge.status.toUpperCase()}\nConnection sequence handshake completed via dynamic relay.`);
  }

  deleteNode(id: string, event: MouseEvent) {
    event.stopPropagation();
    if (confirm('De-register this agent from current diagnostic session? All related link channels will be pruned.')) {
      this.state.deleteAgent(id);
    }
  }

  copyHandle(handle: string) {
    navigator.clipboard.writeText(handle);
    this.copiedHandleId.set(handle);
    setTimeout(() => this.copiedHandleId.set(null), 2000);
  }

  // Draggable Node implementation
  onNodeMouseDown(event: MouseEvent, node: AgentNode) {
    if (this.selectedNodeForRouting()) {
      event.preventDefault();
      event.stopPropagation();
      this.completeManualRoute(node);
      return;
    }
    // Only drag with left click
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    // Don't drag if clicking buttons
    if (target.tagName.toLowerCase() === 'button') return;

    this.draggingNode.set(node);
    this.dragOffset = {
      x: event.clientX - node.x,
      y: event.clientY - node.y,
    };
    event.preventDefault();
  }

  onCanvasMouseMove(event: MouseEvent) {
    const resNode = this.resizingNode();
    if (resNode) {
      const deltaX = event.clientX - this.resizeStartMouse.x;
      const deltaY = event.clientY - this.resizeStartMouse.y;
      const newWidth = Math.max(130, Math.min(400, this.resizeStartSize.w + deltaX));
      const newHeight = Math.max(90, Math.min(300, this.resizeStartSize.h + deltaY));
      
      this.state.nodes.update(nodesList => {
        return nodesList.map(n => n.id === resNode.id ? { ...n, width: newWidth, height: newHeight } : n);
      });
      return;
    }

    const node = this.draggingNode();
    if (!node) return;

    // Calculate new position
    const newX = Math.max(10, Math.min(800, event.clientX - this.dragOffset.x));
    const newY = Math.max(10, Math.min(600, event.clientY - this.dragOffset.y));

    // Update coordinates in the state list
    this.state.nodes.update(nodesList => {
      return nodesList.map(n => n.id === node.id ? { ...n, x: newX, y: newY } : n);
    });
  }

  onCanvasMouseUp() {
    this.draggingNode.set(null);
    this.resizingNode.set(null);
  }

  onFeedMouseEnter() {
    this.state.feedPaused.set(true);
  }

  onFeedMouseLeave() {
    this.state.feedPaused.set(false);
  }
}
