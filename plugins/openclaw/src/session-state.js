export class SessionState {
  constructor() {
    this.current = null;
  }

  touch(payload) {
    if (!payload || typeof payload.sessionKey !== "string" || !payload.sessionKey.trim()) {
      return;
    }
    this.current = {
      sessionKey: payload.sessionKey.trim(),
      sessionId:
        typeof payload.sessionId === "string" && payload.sessionId.trim()
          ? payload.sessionId.trim()
          : undefined,
      agentId:
        typeof payload.agentId === "string" && payload.agentId.trim()
          ? payload.agentId.trim()
          : undefined
    };
  }

  clearIfMatches(sessionKey) {
    if (!this.current || typeof sessionKey !== "string" || !sessionKey.trim()) {
      return;
    }
    if (this.current.sessionKey === sessionKey.trim()) {
      this.current = null;
    }
  }

  resolve(fallbackSessionKey) {
    if (this.current?.sessionKey) {
      return this.current;
    }
    return {
      sessionKey: fallbackSessionKey
    };
  }

  peek() {
    return this.current;
  }
}
