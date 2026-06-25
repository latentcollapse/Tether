import {ChangeDetectionStrategy, Component, computed, inject, signal} from '@angular/core';
import {RouterLink, RouterLinkActive, RouterOutlet} from '@angular/router';
import {CommonModule} from '@angular/common';
import {TetherState} from './tether-state';
import {LucideIcon} from './lucide-icon';
import {ThemeService} from './theme-service';
import {FeedService} from './feed-service';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, LucideIcon],
  template: `
    <!-- Host container styled dynamically via CSS variable mappings -->
    <div 
      class="flex flex-col h-screen w-screen overflow-hidden bg-[var(--bg-base)] text-[var(--text-primary)] select-none font-sans"
      id="app-shell"
    >
      
      <!-- 1. TOP BAR (Height: 48px / 12rem) -->
      <header class="h-12 border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 flex items-center justify-between shrink-0 z-50">
        <!-- Logo Cluster -->
        <div class="flex items-center space-x-3">
          <!-- Geometric stylized tension knot logo -->
          <div class="w-7 h-7 rounded bg-[var(--accent-dim)] flex items-center justify-center border border-[var(--border-strong)]/30 text-[var(--accent)]">
            <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2v20" />
              <path d="M17 5H9a4 4 0 0 0-4 4v6a4 4 0 0 0 4 4h8" />
              <circle cx="12" cy="12" r="2.5" fill="var(--bg-surface)" stroke="currentColor" stroke-width="2" />
            </svg>
          </div>
          
          <div class="flex flex-col">
            <span class="text-xs font-extrabold uppercase tracking-widest text-[var(--text-primary)] font-sans">
              Tether
            </span>
            <span class="text-[9px] text-[var(--text-muted)] font-semibold uppercase tracking-wider -mt-0.5 font-mono">
              Dashboard
            </span>
          </div>

          <!-- Mode badge (Pill shape, muted bg, no border) -->
          <div 
            (click)="toggleMode()" 
            class="px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] hover:bg-[var(--bg-elevated)]/80 text-[10px] font-semibold text-[var(--text-secondary)] flex items-center space-x-1.5 cursor-pointer"
            id="mode-badge"
          >
            <span 
              class="w-1.5 h-1.5 rounded-full"
              [class.bg-emerald-500]="isLocalMode()"
              [class.bg-blue-500]="!isLocalMode()"
            ></span>
            <span>{{ isLocalMode() ? 'Local' : 'Relay' }}</span>
          </div>
        </div>

        <!-- Search Bar / Mid Header -->
        <div class="hidden md:flex items-center space-x-2 bg-[var(--bg-base)] border border-[var(--border)] px-2.5 py-1 rounded max-w-xs w-64 text-[var(--text-secondary)]">
          <lucide-icon name="search" [size]="12" class="text-[var(--text-muted)]"></lucide-icon>
          <input 
            type="text" 
            placeholder="Quick search commands..." 
            class="bg-transparent text-xs w-full focus:outline-none placeholder-[var(--text-muted)] text-[var(--text-primary)]"
            (keyup.enter)="triggerCommandSearch($event)"
          />
          <span class="text-[10px] bg-[var(--bg-elevated)] px-1 py-0.2 rounded border border-[var(--border)] text-[var(--text-muted)] font-mono">⌘K</span>
        </div>

        <!-- Tier / Profile Elements -->
        <div class="flex items-center space-x-3">
          <span class="text-[10px] text-[var(--text-muted)] font-mono font-semibold uppercase shrink-0">
            tier: {{ isLocalMode() ? 'local' : 'relay' }}
          </span>

          <span class="h-4 w-px bg-[var(--border)] shrink-0"></span>

          <!-- User / Profile icon -->
          <div class="flex items-center space-x-1.5 cursor-pointer hover:opacity-85">
            <div class="w-6 h-6 rounded-full bg-[var(--bg-elevated)] border border-[var(--border)] flex items-center justify-center overflow-hidden">
              <lucide-icon name="user" [size]="12" class="text-[var(--text-secondary)]"></lucide-icon>
            </div>
            <span class="hidden sm:inline text-[11px] font-bold text-[var(--text-secondary)] font-mono">matt_dev</span>
          </div>
        </div>
      </header>

      <!-- MAIN MIDDLE BODY (Split into Navigation Sidebar & Content Outlet) -->
      <div class="flex-1 flex overflow-hidden min-h-0">
        
        <!-- 2. NAVIGATION (Left Sidebar: 180px fixed, collapsible to 48px) -->
        <aside 
          [class.w-[180px]]="!state.sidebarCollapsed()"
          [class.w-12]="state.sidebarCollapsed()"
          class="bg-[var(--bg-surface)] border-r border-[var(--border)] flex flex-col justify-between h-full shrink-0 transition-all duration-300 relative z-30"
          id="left-navigation-sidebar"
        >
          <!-- Navigation Links list -->
          <nav class="py-3 flex flex-col space-y-0.5">
            <!-- Nav 1: Network -->
            <a 
              routerLink="/network"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Network' : ''"
            >
              <lucide-icon name="network" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5">Network</span>
              }
            </a>

            <!-- Nav 2: Messages -->
            <a 
              routerLink="/messages"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Messages' : ''"
            >
              <lucide-icon name="mail" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5 flex-1">Messages</span>
                @if (unreadCount() > 0) {
                  <span class="px-1.5 py-0.2 text-[9px] font-bold rounded-full bg-[var(--accent)] text-[var(--bg-base)]">
                    {{ unreadCount() > 99 ? '99+' : unreadCount() }}
                  </span>
                }
              } @else {
                <!-- Tiny bubble dot when collapsed -->
                @if (unreadCount() > 0) {
                  <span class="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--accent)]"></span>
                }
              }
            </a>

            <!-- Nav 2.5: Channels -->
            <a 
              routerLink="/channels"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Channels' : ''"
            >
              <lucide-icon name="channels" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5 flex-1">Channels</span>
                @if (state.unreadChannels().length > 0) {
                  <span class="px-1.5 py-0.2 text-[9px] font-bold rounded-full bg-[var(--accent)] text-[var(--bg-base)]">
                    {{ state.unreadChannels().length }}
                  </span>
                }
              } @else {
                <!-- Tiny bubble dot when collapsed -->
                @if (state.unreadChannels().length > 0) {
                  <span class="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--accent)]"></span>
                }
              }
            </a>

            <!-- Nav 3: Connect -->
            <a 
              routerLink="/connect"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Connect' : ''"
            >
              <lucide-icon name="link" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5">Connect</span>
              }
            </a>

            <!-- Nav 4: Job Board -->
            <a 
              routerLink="/board"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Job Board' : ''"
            >
              <lucide-icon name="kanban" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5">Job Board</span>
              }
            </a>

            <!-- Nav 5: Changelog -->
            <a 
              routerLink="/changelog"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Changelog' : ''"
            >
              <lucide-icon name="clock" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5">Changelog</span>
              }
            </a>

            <!-- Nav 6: Usage -->
            <a 
              routerLink="/usage"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Usage' : ''"
            >
              <lucide-icon name="chart" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5">Usage</span>
              }
            </a>

            <!-- Nav 7: Settings -->
            <a 
              routerLink="/settings"
              routerLinkActive="active-nav"
              class="flex items-center px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all relative border-l-2 border-transparent"
              [title]="state.sidebarCollapsed() ? 'Settings' : ''"
            >
              <lucide-icon name="gear" [size]="14" class="shrink-0"></lucide-icon>
              @if (!state.sidebarCollapsed()) {
                <span class="ml-2.5">Settings</span>
              }
            </a>
          </nav>

          <!-- Collapse Toggle Control at Sidebar Bottom -->
          <div class="p-2 border-t border-[var(--border)]/20">
            <button 
              (click)="toggleSidebar()" 
              class="w-full py-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]/50 flex items-center justify-center transition-all"
              id="sidebar-collapse-btn"
              title="Toggle sidebar size"
            >
              <lucide-icon 
                [name]="state.sidebarCollapsed() ? 'chevron-right' : 'chevron-left'" 
                [size]="14"
              ></lucide-icon>
            </button>
          </div>
        </aside>

        <!-- 3. FLUID MAIN CONTENT WINDOW (Min width: 600px) -->
        <main class="flex-1 flex flex-col overflow-hidden min-w-[600px] bg-[var(--bg-base)]">
          <!-- Density compact adjustment classes wrapper -->
          <div 
            class="flex-1 flex flex-col min-h-0"
            [class.density-compact]="state.density() === 'compact'"
            [class.density-comfortable]="state.density() === 'comfortable'"
          >
            <router-outlet></router-outlet>
          </div>
        </main>
      </div>

      <!-- 4. UTILITY FOOTER GRID (Height: 24px) -->
      <footer class="h-6 bg-[var(--bg-surface)] border-t border-[var(--border)]/80 px-4 flex items-center justify-between text-[10px] text-[var(--text-muted)] font-mono shrink-0 z-40">
        <div class="flex items-center space-x-4">
          <span>Kernel version: <code class="text-[var(--text-secondary)]">tether_d_v2.0</code></span>
          <span class="hidden sm:inline">Region: <code class="text-[var(--text-secondary)]">eu-west-1</code></span>
        </div>

        <div class="flex items-center space-x-4">
          <span class="hidden md:inline">Session ID: <code class="text-[var(--text-secondary)]">session_tether_v8a2d1f93</code></span>
          <span class="flex items-center text-emerald-400">
            <span class="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1"></span>
            <span>Daemon connected</span>
          </span>
        </div>
      </footer>

    </div>
  `,
  styles: `
    :host {
      display: block;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
    }

    /* Active Left navigation item styling */
    .active-nav {
      color: var(--accent) !important;
      border-left-color: var(--accent) !important;
      background-color: var(--accent-dim) !important;
    }

    /* Compact density metrics spacing overrides */
    .density-compact ::ng-deep .py-3 {
      padding-top: 0.5rem !important;
      padding-bottom: 0.5rem !important;
    }
    .density-compact ::ng-deep .py-4 {
      padding-top: 0.75rem !important;
      padding-bottom: 0.75rem !important;
    }
    .density-compact ::ng-deep .p-6 {
      padding: 0.75rem !important;
    }
    .density-compact ::ng-deep .space-y-4 > :not([hidden]) ~ :not([hidden]) {
      --tw-space-y-reverse: 0;
      margin-top: calc(0.5rem * calc(1 - var(--tw-space-y-reverse))) !important;
      margin-bottom: calc(0.5rem * var(--tw-space-y-reverse)) !important;
    }
  `
})
export class App {
  state = inject(TetherState);
  themeService = inject(ThemeService);
  feedService = inject(FeedService);

  // Computed checks
  unreadCount = computed(() => {
    return this.state.messages().filter(m => !m.archived && !m.read).length;
  });

  isLocalMode = signal<boolean>(true);

  toggleMode() {
    this.isLocalMode.set(!this.isLocalMode());
  }

  toggleSidebar() {
    this.state.sidebarCollapsed.set(!this.state.sidebarCollapsed());
  }

  triggerCommandSearch(event: Event) {
    const target = event.target as HTMLInputElement;
    const cmd = target.value.trim();
    if (!cmd) return;

    // Output command event into the feed log
    const date = new Date();
    this.feedService.pushEvent({
      id: `f_${Date.now()}`,
      timestamp: date.toTimeString().split(' ')[0],
      route: `terminal-cli → sys_router`,
      handle: `h&l_cmd_${Math.random().toString(16).substring(2, 8)}`,
      type: 'whiteboard'
    });

    // Write a beautiful line into the whiteboard
    this.state.whiteboardText.update(text => 
      `${text}\n\n* **Command Logged**: \`${cmd}\` initiated at ${date.toLocaleTimeString()}`
    );

    target.value = '';
  }
}
