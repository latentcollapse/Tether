import {ChangeDetectionStrategy, Component, computed, inject, signal} from '@angular/core';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {TetherState, ChannelItem, ChannelMessage} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {CommonModule} from '@angular/common';

@Component({
  selector: 'app-channels',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, ReactiveFormsModule, LucideIcon],
  template: `
    <div class="flex h-full bg-[var(--bg-base)] text-[var(--text-primary)]" id="channels-root">
      
      <!-- 1. CHANNELS LIST SIDEBAR -->
      <aside class="w-56 border-r border-[var(--border)] bg-[var(--bg-surface)] flex flex-col justify-between shrink-0">
        <!-- Sidebar Header -->
        <div class="p-4 border-b border-[var(--border)] flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <lucide-icon name="channels" class="text-[var(--accent)]" [size]="16"></lucide-icon>
            <span class="text-xs font-bold uppercase tracking-wider">Rooms</span>
          </div>
          <button 
            (click)="showCreateModal.set(true)"
            class="p-1 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--accent)] transition-all"
            title="Create new channel"
            id="btn-create-channel"
          >
            <lucide-icon name="plus" [size]="14"></lucide-icon>
          </button>
        </div>

        <!-- Channels Navigation -->
        <div class="flex-1 overflow-y-auto p-2 space-y-0.5" id="channel-list-container">
          @for (chan of state.channels(); track chan.id) {
            <div 
              [class.bg-[var(--bg-elevated)]]="state.selectedChannelId() === chan.id"
              [class.text-[var(--text-primary)]]="state.selectedChannelId() === chan.id"
              class="group flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs font-semibold cursor-pointer transition-all hover:bg-[var(--bg-elevated)]/50 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              (click)="selectChannel(chan.id)"
            >
              <div class="flex items-center space-x-2 min-w-0">
                <lucide-icon name="hash" [size]="13" class="shrink-0 text-[var(--text-muted)] group-hover:text-[var(--accent)]"></lucide-icon>
                <span class="truncate">{{ chan.name }}</span>
                @if (state.unreadChannels().includes(chan.id)) {
                  <span class="w-1.5 h-1.5 rounded-full bg-[var(--accent)] shrink-0 animate-pulse"></span>
                }
              </div>

              <!-- Channel actions (edit/delete) -->
              <div class="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity" (click)="$event.stopPropagation()">
                <button 
                  (click)="openEditModal(chan)" 
                  class="p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  title="Edit channel settings"
                >
                  <lucide-icon name="settings" [size]="11"></lucide-icon>
                </button>
                <button 
                  (click)="deleteChannel(chan)" 
                  class="p-0.5 rounded text-[var(--text-muted)] hover:text-red-400"
                  title="Delete channel"
                >
                  <lucide-icon name="trash" [size]="11"></lucide-icon>
                </button>
              </div>
            </div>
          } @empty {
            <div class="p-4 text-center text-[11px] text-[var(--text-muted)] font-mono">
              No active rooms.
            </div>
          }
        </div>

        <!-- Connection Summary Footer -->
        <div class="p-3 border-t border-[var(--border)] bg-[var(--bg-base)]/40 text-[10px] text-[var(--text-muted)] font-mono">
          <div class="flex items-center justify-between">
            <span>MCP Hub Status:</span>
            <span class="text-emerald-400 font-semibold">Ready</span>
          </div>
        </div>
      </aside>

      <!-- 2. MAIN CHAT CONTAINER -->
      <section class="flex-1 flex flex-col min-w-0 bg-[var(--bg-base)] relative">
        @if (activeChannel(); as channel) {
          
          <!-- Chat Header -->
          <div class="h-12 border-b border-[var(--border)] bg-[var(--bg-surface)] px-6 flex items-center justify-between shrink-0">
            <div class="flex items-center space-x-3 min-w-0">
              <lucide-icon name="hash" class="text-[var(--accent)] shrink-0" [size]="16"></lucide-icon>
              <div class="flex flex-col min-w-0">
                <h2 class="text-xs font-bold text-[var(--text-primary)] truncate">#{{ channel.name }}</h2>
                <p class="text-[10px] text-[var(--text-muted)] truncate">{{ channel.description || 'No description provided.' }}</p>
              </div>
            </div>

            <!-- Member Badge and Join Status -->
            <div class="flex items-center space-x-3">
              <div 
                class="px-2 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border)]/30 text-[10px] font-mono text-[var(--text-secondary)] flex items-center space-x-1.5 cursor-pointer hover:border-[var(--accent)]/50"
                (click)="showMembersPanel.set(!showMembersPanel())"
                title="Toggle members list"
              >
                <lucide-icon name="user" [size]="10"></lucide-icon>
                <span>{{ channel.members.length }} members</span>
              </div>

              @if (isCurrentMember()) {
                <button 
                  (click)="leaveChannel(channel.id)"
                  class="px-2 py-1 rounded text-[10px] font-bold border border-red-500/20 text-red-400 bg-red-500/5 hover:bg-red-500/10 transition-all"
                >
                  Leave Room
                </button>
              } @else {
                <button 
                  (click)="joinChannel(channel.id)"
                  class="px-2.5 py-1 rounded text-[10px] font-bold bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90 transition-all"
                >
                  Join Room
                </button>
              }
            </div>
          </div>

          <!-- Main Layout (Messages list + Members panel) -->
          <div class="flex-1 flex min-h-0 overflow-hidden relative">
            
            <!-- Message Feed -->
            <div class="flex-1 flex flex-col min-h-0 overflow-y-auto p-6 space-y-4" id="messages-scroll-area">
              
              <!-- Welcoming block -->
              <div class="pb-4 border-b border-[var(--border)]/20">
                <div class="w-10 h-10 rounded-full bg-[var(--accent-dim)] flex items-center justify-center border border-[var(--accent)]/20 text-[var(--accent)] mb-2">
                  <lucide-icon name="hash" [size]="20"></lucide-icon>
                </div>
                <h1 class="text-sm font-bold text-[var(--text-primary)]">Welcome to #{{ channel.name }}!</h1>
                <p class="text-xs text-[var(--text-secondary)] mt-1">
                  This is the start of the persistent #{{ channel.name }} room. Anyone in this channel can read and write content-addressed messages.
                </p>
              </div>

              <!-- Messages rendering loop with inline threading -->
              <div class="space-y-4">
                @for (msg of rootMessages(); track msg.id) {
                  <div class="flex items-start group/msg" [id]="'msg-' + msg.id">
                    <!-- Virtualized mock Avatar -->
                    <div class="w-7 h-7 rounded bg-[var(--bg-elevated)] border border-[var(--border)] flex items-center justify-center font-mono text-[10px] font-bold text-[var(--text-secondary)] shrink-0 mr-3 mt-0.5"
                         [class.border-[var(--accent)]/30]="msg.sender === 'matt_dev'"
                         [class.border-purple-500/30]="msg.sender.includes('claude')"
                         [class.border-yellow-500/30]="msg.sender.includes('gemini')"
                         [class.border-emerald-500/30]="msg.sender === 'sys_router'"
                    >
                      {{ msg.sender.substring(0, 2).toUpperCase() }}
                    </div>

                    <!-- Message Body -->
                    <div class="flex-1 min-w-0">
                      <div class="flex items-baseline space-x-2">
                        <span class="text-xs font-bold font-mono"
                              [class.text-[var(--accent)]]="msg.sender === 'matt_dev'"
                              [class.text-purple-400]="msg.sender.includes('claude')"
                              [class.text-yellow-400]="msg.sender.includes('gemini')"
                              [class.text-emerald-400]="msg.sender === 'sys_router'"
                        >
                          {{ msg.sender }}
                        </span>
                        <span class="text-[9px] text-[var(--text-muted)] font-mono">{{ msg.timestamp }}</span>
                        <span class="text-[9px] font-mono text-[var(--text-muted)] px-1 rounded bg-[var(--bg-elevated)] border border-[var(--border)] opacity-0 group-hover/msg:opacity-100 transition-opacity">
                          ID: {{ msg.id }}
                        </span>
                      </div>

                      <p class="text-xs text-[var(--text-primary)] mt-1 select-text leading-relaxed whitespace-pre-wrap">{{ msg.body }}</p>

                      <!-- Action triggers: Reply to start a thread -->
                      <div class="flex items-center space-x-3 mt-1.5 opacity-0 group-hover/msg:opacity-100 transition-opacity">
                        <button 
                          (click)="startReply(msg)" 
                          class="flex items-center space-x-1 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent)] font-medium"
                          title="Reply to message"
                        >
                          <lucide-icon name="mail" [size]="10"></lucide-icon>
                          <span>Reply Thread</span>
                        </button>
                      </div>

                      <!-- Intended Threaded Replies -->
                      @if (getRepliesForMessage(msg.id); as replies) {
                        @if (replies.length > 0) {
                          <div class="mt-2 pl-4 border-l border-[var(--border-strong)]/30 space-y-3">
                            @for (rep of replies; track rep.id) {
                              <div class="flex items-start">
                                <div class="w-5 h-5 rounded bg-[var(--bg-elevated)] border border-[var(--border)] flex items-center justify-center font-mono text-[8px] font-bold text-[var(--text-secondary)] shrink-0 mr-2 mt-0.5">
                                  {{ rep.sender.substring(0, 2).toUpperCase() }}
                                </div>
                                <div class="flex-1 min-w-0">
                                  <div class="flex items-baseline space-x-1.5">
                                    <span class="text-[11px] font-bold font-mono"
                                          [class.text-[var(--accent)]]="rep.sender === 'matt_dev'"
                                          [class.text-purple-400]="rep.sender.includes('claude')"
                                          [class.text-yellow-400]="rep.sender.includes('gemini')"
                                    >
                                      {{ rep.sender }}
                                    </span>
                                    <span class="text-[8px] text-[var(--text-muted)] font-mono">{{ rep.timestamp }}</span>
                                  </div>
                                  <p class="text-xs text-[var(--text-secondary)] mt-0.5 select-text leading-relaxed whitespace-pre-wrap">{{ rep.body }}</p>
                                </div>
                              </div>
                            }
                          </div>
                        }
                      }
                    </div>
                  </div>
                }
              </div>

            </div>

            <!-- Sidebar Members Panel (Collapsible) -->
            @if (showMembersPanel()) {
              <div class="w-48 border-l border-[var(--border)] bg-[var(--bg-surface)] p-4 overflow-y-auto shrink-0 animate-fade-in" id="members-list-panel">
                <h3 class="text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)] mb-3">Room Members</h3>
                <div class="space-y-2">
                  @for (mem of channel.members; track mem) {
                    <div class="flex items-center space-x-2">
                      <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                      <span class="text-xs font-semibold font-mono truncate"
                            [class.text-[var(--accent)]]="mem === 'matt_dev'"
                            [class.text-purple-400]="mem.includes('claude')"
                            [class.text-yellow-400]="mem.includes('gemini')"
                      >
                        {{ mem }}
                      </span>
                    </div>
                  }
                </div>
              </div>
            }

          </div>

          <!-- Bottom Toast notifications simulating silent MCP delivers -->
          @if (activeNotification(); as notification) {
            <div class="absolute bottom-16 right-6 z-50 bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded px-4 py-2.5 shadow-2xl flex items-center space-x-2 text-[11px] font-mono animate-fade-in">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
              <lucide-icon name="bell" class="text-emerald-400" [size]="12"></lucide-icon>
              <span class="text-[var(--text-secondary)]">Silent MCP client triggered: </span>
              <span class="text-[var(--accent)] font-bold">{{ notification }}</span>
            </div>
          }

          <!-- Chat Input Area -->
          <div class="p-4 border-t border-[var(--border)] bg-[var(--bg-surface)] shrink-0">
            <!-- Replying indicator -->
            @if (replyingTo(); as repMsg) {
              <div class="flex items-center justify-between px-3 py-1.5 mb-2 bg-[var(--bg-elevated)] rounded border border-[var(--border)] text-xs">
                <div class="flex items-center space-x-1 text-[var(--text-secondary)]">
                  <lucide-icon name="mail" [size]="12"></lucide-icon>
                  <span>Replying to <b class="font-mono text-[var(--text-primary)]">{{ repMsg.sender }}</b></span>
                  <span class="truncate max-w-[200px] italic text-[var(--text-muted)]">"{{ repMsg.body }}"</span>
                </div>
                <button (click)="replyingTo.set(null)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                  <lucide-icon name="close" [size]="12"></lucide-icon>
                </button>
              </div>
            }

            <form [formGroup]="chatForm" (ngSubmit)="sendMessage()" class="flex space-x-2 items-center">
              
              <!-- Sender Selection (to let the user simulate multi-agent dialogue) -->
              <div class="relative shrink-0">
                <select 
                  formControlName="senderIdentity"
                  class="bg-[var(--bg-base)] border border-[var(--border)] text-[11px] font-mono px-2.5 py-1.5 rounded focus:outline-none text-[var(--text-primary)] hover:border-[var(--accent)]/50 cursor-pointer"
                  title="Sender Identity Toggle"
                >
                  <option value="matt_dev">matt_dev (human)</option>
                  <option value="claude-3.5">claude-3.5 (agent)</option>
                  <option value="gemini-1.5">gemini-1.5 (agent)</option>
                  <option value="sys_router">sys_router (daemon)</option>
                </select>
              </div>

              <!-- Input text box -->
              <input 
                type="text"
                formControlName="messageText"
                placeholder="Type messages in persistable room..."
                class="flex-1 bg-[var(--bg-base)] border border-[var(--border)] text-xs px-3 py-1.5 rounded focus:outline-none focus:border-[var(--accent)] placeholder-[var(--text-muted)] text-[var(--text-primary)]"
                id="chat-input-field"
                autocomplete="off"
              />

              <!-- Send Action Button -->
              <button 
                type="submit"
                [disabled]="!chatForm.valid"
                class="px-4 py-1.5 rounded text-xs font-bold bg-[var(--accent)] text-[var(--bg-base)] hover:opacity-90 disabled:opacity-50 transition-all flex items-center space-x-1 shrink-0"
              >
                <span>Send</span>
                <lucide-icon name="play" [size]="10"></lucide-icon>
              </button>

            </form>
          </div>

        @} @else {
          <!-- Empty fallback screen -->
          <div class="flex-1 flex flex-col items-center justify-center p-12 text-center text-[var(--text-muted)]">
            <lucide-icon name="channels" [size]="32" class="mb-3 opacity-60"></lucide-icon>
            <h2 class="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] mb-1">No room active</h2>
            <p class="text-[11px] max-w-sm leading-relaxed">
              Select an existing room from the sidebar or click the plus button to configure a persistent named channel.
            </p>
          </div>
        }
      </section>

      <!-- 3. CREATE CHANNEL MODAL -->
      @if (showCreateModal()) {
        <div class="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center z-50 p-4" id="create-modal-overlay">
          <div class="bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-lg shadow-2xl w-full max-w-sm p-5 animate-fade-in" id="create-channel-modal">
            <div class="flex items-center justify-between border-b border-[var(--border)] pb-2 mb-4">
              <h3 class="text-xs font-extrabold uppercase tracking-widest text-[var(--text-primary)]">New Persistent Room</h3>
              <button (click)="showCreateModal.set(false)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <lucide-icon name="close" [size]="14"></lucide-icon>
              </button>
            </div>

            <form [formGroup]="createForm" (ngSubmit)="createChannel()">
              <div class="space-y-3 text-xs">
                <div>
                  <label class="block text-[11px] font-mono text-[var(--text-secondary)] mb-1 uppercase">Room Name</label>
                  <input 
                    type="text" 
                    formControlName="name"
                    placeholder="e.g. general" 
                    class="w-full bg-[var(--bg-base)] border border-[var(--border)] px-3 py-1.5 rounded focus:outline-none focus:border-[var(--accent)] text-[var(--text-primary)]"
                  />
                  @if (createForm.get('name')?.touched && createForm.get('name')?.invalid) {
                    <span class="text-[10px] text-red-400 block mt-1">Name is required (letters, numbers, hyphens, underscores only).</span>
                  }
                </div>

                <div>
                  <label class="block text-[11px] font-mono text-[var(--text-secondary)] mb-1 uppercase">Description</label>
                  <textarea 
                    formControlName="description"
                    placeholder="Coordinate workspace actions..." 
                    rows="2"
                    class="w-full bg-[var(--bg-base)] border border-[var(--border)] px-3 py-1.5 rounded focus:outline-none focus:border-[var(--accent)] text-[var(--text-primary)]"
                  ></textarea>
                </div>

                <div>
                  <label class="block text-[11px] font-mono text-[var(--text-secondary)] mb-1.5 uppercase">Initial Members</label>
                  <div class="space-y-1.5 bg-[var(--bg-base)] border border-[var(--border)] p-2 rounded max-h-24 overflow-y-auto font-mono text-[11px]">
                    <label class="flex items-center space-x-2">
                      <input type="checkbox" [checked]="true" disabled class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-primary)]">matt_dev</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer">
                      <input type="checkbox" #memClaude [checked]="true" class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-secondary)]">claude-3.5</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer">
                      <input type="checkbox" #memGemini [checked]="true" class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-secondary)]">gemini-1.5</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer">
                      <input type="checkbox" #memRouter [checked]="true" class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-secondary)]">sys_router</span>
                    </label>
                  </div>
                </div>

                <div class="flex space-x-2 pt-2">
                  <button 
                    type="button" 
                    (click)="showCreateModal.set(false)"
                    class="flex-1 py-1.5 rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors text-center"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit" 
                    [disabled]="!createForm.valid"
                    class="flex-1 py-1.5 rounded bg-[var(--accent)] text-[var(--bg-base)] font-bold hover:opacity-90 disabled:opacity-50 transition-colors text-center"
                  >
                    Create
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      }

      <!-- 4. EDIT CHANNEL MODAL -->
      @if (showEditModal()) {
        <div class="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center z-50 p-4" id="edit-modal-overlay">
          <div class="bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-lg shadow-2xl w-full max-w-sm p-5 animate-fade-in" id="edit-channel-modal">
            <div class="flex items-center justify-between border-b border-[var(--border)] pb-2 mb-4">
              <h3 class="text-xs font-extrabold uppercase tracking-widest text-[var(--text-primary)]">Edit Room Settings</h3>
              <button (click)="showEditModal.set(false)" class="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <lucide-icon name="close" [size]="14"></lucide-icon>
              </button>
            </div>

            <form [formGroup]="editForm" (ngSubmit)="saveChannelEdit()">
              <div class="space-y-3 text-xs">
                <div>
                  <label class="block text-[11px] font-mono text-[var(--text-secondary)] mb-1 uppercase">Room Name</label>
                  <input 
                    type="text" 
                    formControlName="name"
                    placeholder="e.g. general" 
                    class="w-full bg-[var(--bg-base)] border border-[var(--border)] px-3 py-1.5 rounded focus:outline-none focus:border-[var(--accent)] text-[var(--text-primary)]"
                  />
                  @if (editForm.get('name')?.touched && editForm.get('name')?.invalid) {
                    <span class="text-[10px] text-red-400 block mt-1">Name is required (letters, numbers, hyphens, underscores only).</span>
                  }
                </div>

                <div>
                  <label class="block text-[11px] font-mono text-[var(--text-secondary)] mb-1 uppercase">Description</label>
                  <textarea 
                    formControlName="description"
                    placeholder="Coordinate workspace actions..." 
                    rows="2"
                    class="w-full bg-[var(--bg-base)] border border-[var(--border)] px-3 py-1.5 rounded focus:outline-none focus:border-[var(--accent)] text-[var(--text-primary)]"
                  ></textarea>
                </div>

                <div>
                  <label class="block text-[11px] font-mono text-[var(--text-secondary)] mb-1.5 uppercase">Manage Members</label>
                  <div class="space-y-1.5 bg-[var(--bg-base)] border border-[var(--border)] p-2 rounded max-h-24 overflow-y-auto font-mono text-[11px]">
                    <label class="flex items-center space-x-2">
                      <input type="checkbox" [checked]="editFormMembers.includes('matt_dev')" (change)="toggleEditMember('matt_dev')" class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-primary)]">matt_dev</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer">
                      <input type="checkbox" [checked]="editFormMembers.includes('claude-3.5')" (change)="toggleEditMember('claude-3.5')" class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-secondary)]">claude-3.5</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer">
                      <input type="checkbox" [checked]="editFormMembers.includes('gemini-1.5')" (change)="toggleEditMember('gemini-1.5')" class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-secondary)]">gemini-1.5</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer">
                      <input type="checkbox" [checked]="editFormMembers.includes('sys_router')" (change)="toggleEditMember('sys_router')" class="rounded text-[var(--accent)] focus:ring-[var(--accent)]" />
                      <span class="text-[var(--text-secondary)]">sys_router</span>
                    </label>
                  </div>
                </div>

                <div class="flex space-x-2 pt-2">
                  <button 
                    type="button" 
                    (click)="showEditModal.set(false)"
                    class="flex-1 py-1.5 rounded border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors text-center"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit" 
                    [disabled]="!editForm.valid"
                    class="flex-1 py-1.5 rounded bg-[var(--accent)] text-[var(--bg-base)] font-bold hover:opacity-90 disabled:opacity-50 transition-colors text-center"
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      }

    </div>
  `,
  styles: `
    :host {
      display: block;
      height: 100%;
    }
  `
})
export class Channels {
  state = inject(TetherState);

  // Forms and Modals
  chatForm: FormGroup;
  createForm: FormGroup;
  editForm: FormGroup;

  showCreateModal = signal<boolean>(false);
  showEditModal = signal<boolean>(false);
  showMembersPanel = signal<boolean>(false);
  replyingTo = signal<ChannelMessage | null>(null);

  editingChannelId = '';
  editFormMembers: string[] = [];

  activeNotification = signal<string | null>(null);

  constructor() {
    this.chatForm = new FormGroup({
      messageText: new FormControl('', Validators.required),
      senderIdentity: new FormControl('matt_dev', Validators.required)
    });

    this.createForm = new FormGroup({
      name: new FormControl('', [Validators.required, Validators.pattern(/^[a-zA-Z0-9_-]+$/)]),
      description: new FormControl('')
    });

    this.editForm = new FormGroup({
      name: new FormControl('', [Validators.required, Validators.pattern(/^[a-zA-Z0-9_-]+$/)]),
      description: new FormControl('')
    });
  }

  // Active channel computer
  activeChannel = computed(() => {
    return this.state.channels().find(c => c.id === this.state.selectedChannelId());
  });

  // Root level messages in selected channel
  rootMessages = computed(() => {
    const cid = this.state.selectedChannelId();
    return this.state.channelMessages().filter(m => m.channelId === cid && !m.threadId);
  });

  // Check if current human (matt_dev) is a member of the active channel
  isCurrentMember = computed(() => {
    const ac = this.activeChannel();
    return ac ? ac.members.includes('matt_dev') : false;
  });

  getRepliesForMessage(messageId: string): ChannelMessage[] {
    const cid = this.state.selectedChannelId();
    return this.state.channelMessages().filter(m => m.channelId === cid && m.threadId === messageId);
  }

  selectChannel(channelId: string) {
    this.state.selectedChannelId.set(channelId);
    this.replyingTo.set(null);
    this.state.unreadChannels.update(unreads => unreads.filter(id => id !== channelId));
    this.state.loadChannelMessages(channelId);
    setTimeout(() => this.scrollChatToBottom(), 50);
  }

  sendMessage() {
    const channel = this.activeChannel();
    if (!channel) return;

    const body = this.chatForm.get('messageText')?.value?.trim();
    const sender = this.chatForm.get('senderIdentity')?.value;
    if (!body) return;

    const parentId = this.replyingTo()?.id;
    this.state.sendChannelMessage(channel.id, sender, body, parentId);

    // Trigger visual notification toast to show MCP simulation
    this.triggerSilentMCPNotification(() => {
      // Find newly sent msg ID
      const msgs = this.state.channelMessages();
      const lastMsg = msgs[msgs.length - 1];
      return lastMsg ? lastMsg.id : 'address_err';
    });

    this.chatForm.get('messageText')?.setValue('');
    this.replyingTo.set(null);

    setTimeout(() => this.scrollChatToBottom(), 50);
  }

  startReply(msg: ChannelMessage) {
    this.replyingTo.set(msg);
    // Focus chat input box
    const field = document.getElementById('chat-input-field');
    if (field) field.focus();
  }

  createChannel() {
    const name = this.createForm.get('name')?.value?.trim();
    const description = this.createForm.get('description')?.value?.trim() || '';
    if (!name) return;

    // Read members checkboxes dynamically
    const initialMembers = ['matt_dev'];
    // Quick selectors (using template elements)
    const clCheck = document.querySelector('input[type="checkbox"]:nth-child(2)') as HTMLInputElement;
    if (clCheck && clCheck.checked) initialMembers.push('claude-3.5');
    
    // Standard additions
    initialMembers.push('claude-3.5');
    initialMembers.push('gemini-1.5');
    initialMembers.push('sys_router');

    const uniqueMembers = Array.from(new Set(initialMembers));
    this.state.createChannel(name, description, uniqueMembers);

    this.createForm.reset();
    this.showCreateModal.set(false);
    // Channel list will update via server response in state.createChannel
  }

  deleteChannel(chan: ChannelItem) {
    if (confirm(`Are you sure you want to delete room #${chan.name}? This action is irreversible.`)) {
      this.state.deleteChannel(chan.id);
    }
  }

  openEditModal(chan: ChannelItem) {
    this.editingChannelId = chan.id;
    this.editFormMembers = [...chan.members];
    this.editForm.setValue({
      name: chan.name,
      description: chan.description
    });
    this.showEditModal.set(true);
  }

  toggleEditMember(mem: string) {
    if (this.editFormMembers.includes(mem)) {
      this.editFormMembers = this.editFormMembers.filter(m => m !== mem);
    } else {
      this.editFormMembers.push(mem);
    }
  }

  saveChannelEdit() {
    const name = this.editForm.get('name')?.value?.trim().replace(/[^a-zA-Z0-9_-]/g, '');
    const description = this.editForm.get('description')?.value?.trim() || '';
    if (!name) return;

    this.state.channels.update(chans => chans.map(c => {
      if (c.id === this.editingChannelId) {
        return {
          ...c,
          name,
          description,
          members: [...this.editFormMembers]
        };
      }
      return c;
    }));

    this.showEditModal.set(false);
  }

  joinChannel(channelId: string) {
    this.state.joinChannel(channelId, 'matt_dev');
  }

  leaveChannel(channelId: string) {
    this.state.leaveChannel(channelId, 'matt_dev');
  }

  triggerSilentMCPNotification(msgIdGetter: () => string) {
    const msgId = msgIdGetter();
    this.activeNotification.set(msgId);
    setTimeout(() => {
      if (this.activeNotification() === msgId) {
        this.activeNotification.set(null);
      }
    }, 4000);
  }

  scrollChatToBottom() {
    const scroller = document.getElementById('messages-scroll-area');
    if (scroller) {
      scroller.scrollTop = scroller.scrollHeight;
    }
  }
}
