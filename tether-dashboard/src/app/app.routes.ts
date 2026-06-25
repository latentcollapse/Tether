import {Routes} from '@angular/router';
import {Network} from './network';
import {Messages} from './messages';
import {Channels} from './channels';
import {Connect} from './connect';
import {Board} from './board';
import {Changelog} from './changelog';
import {Usage} from './usage';
import {Settings} from './settings';

export const routes: Routes = [
  { path: 'network', component: Network },
  { path: 'messages', component: Messages },
  { path: 'channels', component: Channels },
  { path: 'connect', component: Connect },
  { path: 'board', component: Board },
  { path: 'changelog', component: Changelog },
  { path: 'usage', component: Usage },
  { path: 'settings', component: Settings },
  { path: '', redirectTo: 'network', pathMatch: 'full' },
  { path: '**', redirectTo: 'network' }
];
