import {ChangeDetectionStrategy, Component, computed, input} from '@angular/core';

export interface IconPath {
  type: string;
  cx?: number;
  cy?: number;
  r?: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  rx?: number;
  d?: string;
  points?: string;
}

@Component({
  selector: 'lucide-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      [attr.width]="size()"
      [attr.height]="size()"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      [attr.stroke-width]="strokeWidth()"
      stroke-linecap="round"
      stroke-linejoin="round"
      [class]="class()"
    >
      @for (path of paths(); track path) {
        @if (path.type === 'circle') {
          <circle [attr.cx]="path.cx" [attr.cy]="path.cy" [attr.r]="path.r" />
        } @else if (path.type === 'line') {
          <line [attr.x1]="path.x1" [attr.y1]="path.y1" [attr.x2]="path.x2" [attr.y2]="path.y2" />
        } @else if (path.type === 'rect') {
          <rect [attr.x]="path.x" [attr.y]="path.y" [attr.width]="path.width" [attr.height]="path.height" [attr.rx]="path.rx" />
        } @else if (path.type === 'path') {
          <path [attr.d]="path.d" />
        } @else if (path.type === 'polyline') {
          <polyline [attr.points]="path.points" />
        }
      }
    </svg>
  `,
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
  `,
})
export class LucideIcon {
  name = input<string>('');
  size = input<number | string>(14);
  strokeWidth = input<number | string>(2);
  class = input<string>('');

  paths = computed<IconPath[]>(() => {
    const iconName = this.name().toLowerCase().trim();
    switch (iconName) {
      case 'network':
      case 'graph':
        return [
          { type: 'circle', cx: 12, cy: 5, r: 3 },
          { type: 'circle', cx: 6, cy: 12, r: 3 },
          { type: 'circle', cx: 18, cy: 12, r: 3 },
          { type: 'circle', cx: 12, cy: 19, r: 3 },
          { type: 'line', x1: 9, y1: 7, x2: 6.5, y2: 10 },
          { type: 'line', x1: 15, y1: 7, x2: 17.5, y2: 10 },
          { type: 'line', x1: 12, y1: 8, x2: 12, y2: 16 },
          { type: 'line', x1: 7.5, y1: 14.5, x2: 10.5, y2: 17 },
          { type: 'line', x1: 16.5, y1: 14.5, x2: 13.5, y2: 17 },
        ];
      case 'messages':
      case 'mail':
        return [
          { type: 'rect', x: 2, y: 4, width: 20, height: 16, rx: 2 },
          { type: 'path', d: 'm22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7' },
        ];
      case 'channels':
      case 'channel':
      case 'hash':
        return [
          { type: 'line', x1: 4, y1: 9, x2: 20, y2: 9 },
          { type: 'line', x1: 4, y1: 15, x2: 20, y2: 15 },
          { type: 'line', x1: 10, y1: 3, x2: 8, y2: 21 },
          { type: 'line', x1: 16, y1: 3, x2: 14, y2: 21 },
        ];
      case 'connect':
      case 'link':
        return [
          { type: 'path', d: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71' },
          { type: 'path', d: 'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71' },
        ];
      case 'board':
      case 'kanban':
        return [
          { type: 'line', x1: 6, y1: 3, x2: 6, y2: 21 },
          { type: 'line', x1: 12, y1: 3, x2: 12, y2: 21 },
          { type: 'line', x1: 18, y1: 3, x2: 18, y2: 21 },
          { type: 'rect', x: 2, y: 5, width: 8, height: 4, rx: 1 },
          { type: 'rect', x: 8, y: 11, width: 8, height: 6, rx: 1 },
          { type: 'rect', x: 14, y: 5, width: 8, height: 5, rx: 1 },
        ];
      case 'changelog':
      case 'clock':
        return [
          { type: 'circle', cx: 12, cy: 12, r: 10 },
          { type: 'polyline', points: '12 6 12 12 16 14' },
        ];
      case 'usage':
      case 'chart':
        return [
          { type: 'path', d: 'M3 3v18h18' },
          { type: 'path', d: 'm19 9-5 5-4-4-3 3' },
        ];
      case 'settings':
      case 'gear':
        return [
          { type: 'circle', cx: 12, cy: 12, r: 3 },
          { type: 'path', d: 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' },
        ];
      case 'chevron-left':
        return [{ type: 'polyline', points: '15 18 9 12 15 6' }];
      case 'chevron-right':
        return [{ type: 'polyline', points: '9 18 15 12 9 6' }];
      case 'chevrons-left':
        return [
          { type: 'polyline', points: '11 17 6 12 11 7' },
          { type: 'polyline', points: '18 17 13 12 18 7' },
        ];
      case 'chevrons-right':
        return [
          { type: 'polyline', points: '13 17 18 12 13 7' },
          { type: 'polyline', points: '6 17 11 12 6 7' },
        ];
      case 'copy':
        return [
          { type: 'rect', x: 9, y: 9, width: 13, height: 13, rx: 2 },
          { type: 'path', d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' },
        ];
      case 'check':
        return [{ type: 'polyline', points: '20 6 9 17 4 12' }];
      case 'qr-code':
        return [
          { type: 'rect', x: 3, y: 3, width: 7, height: 7, rx: 1 },
          { type: 'rect', x: 14, y: 3, width: 7, height: 7, rx: 1 },
          { type: 'rect', x: 3, y: 14, width: 7, height: 7, rx: 1 },
          { type: 'line', x1: 14, y1: 14, x2: 14, y2: 14 },
          { type: 'line', x1: 18, y1: 14, x2: 21, y2: 14 },
          { type: 'line', x1: 14, y1: 18, x2: 14, y2: 21 },
          { type: 'line', x1: 18, y1: 18, x2: 18, y2: 21 },
          { type: 'line', x1: 21, y1: 17, x2: 21, y2: 20 },
        ];
      case 'rotate':
      case 'refresh-cw':
        return [
          { type: 'path', d: 'M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8' },
          { type: 'path', d: 'M3 3v5h5' },
          { type: 'path', d: 'M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16' },
          { type: 'path', d: 'M16 16h5v5' },
        ];
      case 'trash':
      case 'revoke':
        return [
          { type: 'polyline', points: '3 6 5 6 21 6' },
          { type: 'path', d: 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' },
          { type: 'line', x1: 10, y1: 11, x2: 10, y2: 17 },
          { type: 'line', x1: 14, y1: 11, x2: 14, y2: 17 },
        ];
      case 'alert-circle':
      case 'error':
        return [
          { type: 'circle', cx: 12, cy: 12, r: 10 },
          { type: 'line', x1: 12, y1: 8, x2: 12, y2: 12 },
          { type: 'line', x1: 12, y1: 16, x2: 12.01, y2: 16 },
        ];
      case 'help':
        return [
          { type: 'path', d: 'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3' },
          { type: 'line', x1: 12, y1: 17, x2: 12.01, y2: 17 },
          { type: 'circle', cx: 12, cy: 12, r: 10 },
        ];
      case 'plus':
        return [
          { type: 'line', x1: 12, y1: 5, x2: 12, y2: 19 },
          { type: 'line', x1: 5, y1: 12, x2: 19, y2: 12 },
        ];
      case 'user':
        return [
          { type: 'path', d: 'M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2' },
          { type: 'circle', cx: 12, cy: 7, r: 4 },
        ];
      case 'info':
        return [
          { type: 'circle', cx: 12, cy: 12, r: 10 },
          { type: 'line', x1: 12, y1: 16, x2: 12, y2: 12 },
          { type: 'line', x1: 12, y1: 8, x2: 12.01, y2: 8 },
        ];
      case 'git-branch':
        return [
          { type: 'line', x1: 6, y1: 3, x2: 6, y2: 15 },
          { type: 'circle', cx: 18, cy: 9, r: 3 },
          { type: 'circle', cx: 6, cy: 18, r: 3 },
          { type: 'path', d: 'M18 12a6 6 0 0 1-6 6H9' },
        ];
      case 'external-link':
        return [
          { type: 'path', d: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6' },
          { type: 'polyline', points: '15 3 21 3 21 9' },
          { type: 'line', x1: 10, y1: 14, x2: 21, y2: 3 },
        ];
      case 'terminal':
        return [
          { type: 'polyline', points: '4 17 10 11 4 5' },
          { type: 'line', x1: 12, y1: 19, x2: 20, y2: 19 },
        ];
      case 'volume-2':
        return [
          { type: 'path', d: 'M11 5 6 9H2v6h4l5 4V5z' },
          { type: 'path', d: 'M15.54 8.46a5 5 0 0 1 0 7.07' },
          { type: 'path', d: 'M19.07 4.93a10 10 0 0 1 0 14.14' },
        ];
      case 'bell':
        return [
          { type: 'path', d: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9' },
          { type: 'path', d: 'M13.73 21a2 2 0 0 1-3.46 0' },
        ];
      case 'globe':
        return [
          { type: 'circle', cx: 12, cy: 12, r: 10 },
          { type: 'line', x1: 2, y1: 12, x2: 22, y2: 12 },
          { type: 'path', d: 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' },
        ];
      case 'play':
        return [{ type: 'path', d: 'm5 3 14 9-14 9V3z' }];
      case 'pause':
        return [
          { type: 'rect', x: 6, y: 4, width: 4, height: 16 },
          { type: 'rect', x: 14, y: 4, width: 4, height: 16 },
        ];
      case 'refresh':
        return [
          { type: 'path', d: 'M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67' },
        ];
      case 'search':
        return [
          { type: 'circle', cx: 11, cy: 11, r: 8 },
          { type: 'line', x1: 21, y1: 21, x2: 16.65, y2: 16.65 },
        ];
      case 'shield':
        return [
          { type: 'path', d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
        ];
      case 'archive':
        return [
          { type: 'polyline', points: '21 8 21 21 3 21 3 8' },
          { type: 'rect', x: 1, y: 3, width: 22, height: 5, rx: 1 },
          { type: 'line', x1: 10, y1: 12, x2: 14, y2: 12 },
        ];
      case 'close':
      case 'x':
        return [
          { type: 'line', x1: 18, y1: 6, x2: 6, y2: 18 },
          { type: 'line', x1: 6, y1: 6, x2: 18, y2: 18 },
        ];
      case 'ticket':
        return [
          { type: 'path', d: 'M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v2Z' },
          { type: 'line', x1: 9, y1: 5, x2: 9, y2: 19 },
        ];
      case 'eye':
        return [
          { type: 'path', d: 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z' },
          { type: 'circle', cx: 12, cy: 12, r: 3 },
        ];
      default:
        // default to generic info icon
        return [
          { type: 'circle', cx: 12, cy: 12, r: 10 },
          { type: 'line', x1: 12, y1: 16, x2: 12, y2: 12 },
          { type: 'line', x1: 12, y1: 8, x2: 12.01, y2: 8 },
        ];
    }
  });
}
