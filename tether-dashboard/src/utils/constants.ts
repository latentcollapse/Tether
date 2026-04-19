const relayOrigin = (
  import.meta.env.VITE_TETHER_RELAY_URL?.replace(/\/$/, '') || ''
);

export const RELAY_BASE_URL = relayOrigin;
export const HEALTH_URL = `${RELAY_BASE_URL}/health`;
export const API_BASE_URL = `${RELAY_BASE_URL}/api`;
export const WS_URL = `${RELAY_BASE_URL.replace(/^http/, 'ws')}/api/feed`;

export const UI_STRINGS = {
  TAGLINE: "Agent coordination infrastructure",
  NO_KEY_HINT: "Don't have a key? Self-host TetherLite →",
  CONNECT: "Connect",
  DISCONNECTED_BANNER: "Disconnected — reconnecting...",
  INVALID_KEY: "Invalid key — check and try again",
  HANDLE_NOT_FOUND: "Handle not found or expired",
  RATE_LIMIT: "Rate limit reached",
  SESSION_ENDED: "Session ended — key was revoked",
  REQUEST_TIMEOUT: "Request timed out",
  REVOKE_CONFIRM_TITLE: "Revoke Key",
  REVOKE_CONFIRM_BODY: "This will immediately disconnect the agent. Continue?",
  ONE_TIME_KEY_PROMPT: "This is the only time you'll see this key. Please copy it now."
};
