import { Injectable, inject, effect } from '@angular/core';
import { TetherState, THEMES, ThemeColors } from './tether-state';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private state = inject(TetherState);

  constructor() {
    // Synchronize active theme and wallpaper changes directly to root CSS custom properties
    effect(() => {
      const themeName = this.state.activeThemeName();
      const customTokens = this.state.customThemeTokens();
      const wallpaper = this.state.wallpaperUrl();

      if (typeof document !== 'undefined') {
        const root = document.documentElement;
        document.body.setAttribute('data-theme', themeName);

        // Retrieve proper colors based on selection
        let colors: ThemeColors;
        if (themeName === 'custom' && customTokens) {
          colors = customTokens;
        } else {
          colors = THEMES[themeName] || THEMES['void'];
        }

        // Apply all variables dynamically to root styling
        Object.entries(colors).forEach(([property, value]) => {
          root.style.setProperty(property, value);
        });

        // Set custom wallpaper properties if specified
        if (wallpaper && wallpaper.trim().length > 0) {
          root.style.setProperty('--bg-wallpaper', `url("${wallpaper.trim()}")`);
        } else {
          root.style.setProperty('--bg-wallpaper', 'none');
        }
      }
    });
  }
}
