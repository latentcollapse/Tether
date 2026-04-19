import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolvePluginConfig } from "./src/config.js";
import { callTetherTool } from "./src/mcp-bridge.js";
import { createJsonResult, readJsonBody, sendJson } from "./src/http.js";
import { SessionState } from "./src/session-state.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SEND_TOOL_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    to: { type: "string", description: "Recipient agent name." },
    subject: { type: "string", description: "Message subject." },
    text: { type: "string", description: "Message body." },
    from_agent: { type: "string", description: "Sender agent name." },
    ticket_id: { type: "string", description: "Optional ticket id." },
    tags: { type: "array", items: { type: "string" }, description: "Optional tags." },
    ttl_seconds: { type: "integer", description: "Optional TTL in seconds." }
  },
  required: ["to", "subject", "text"]
};

const INBOX_TOOL_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    for_agent: { type: "string", description: "Agent name to inspect." },
    include_closed: {
      type: "boolean",
      description: "Include closed or stale messages."
    }
  }
};

const RECEIVE_TOOL_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    handle: { type: "string", description: "Tether message handle." },
    for_agent: { type: "string", description: "Agent receiving the message." }
  },
  required: ["handle"]
};

const COLLAPSE_TOOL_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    table: { type: "string", description: "Target table name." },
    data: { type: "object", description: "JSON value to collapse." },
    tags: { type: "array", items: { type: "string" }, description: "Optional tags." }
  },
  required: ["table", "data"]
};

const RESOLVE_TOOL_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    handle: { type: "string", description: "Tether handle to resolve." }
  },
  required: ["handle"]
};

export function buildInboundMessage(payload) {
  const from = typeof payload.from === "string" && payload.from.trim() ? payload.from.trim() : "?";
  const subject =
    typeof payload.subject === "string" && payload.subject.trim()
      ? payload.subject.trim()
      : "(no subject)";
  const handle =
    typeof payload.handle === "string" && payload.handle.trim() ? payload.handle.trim() : "";
  if (!handle) {
    throw new Error("handle required");
  }
  return {
    handle,
    from,
    subject,
    text: `[Tether] From agent: ${from}\nHandle: '${handle}'`
  };
}

function createTetherTool(params) {
  const { name, label, description, schema, pluginRoot, config, sessionState, transform, api } =
    params;
  return (ctx) => ({
    name,
    label,
    description,
    parameters: schema,
    async execute(_toolCallId, rawParams) {
      sessionState.touch({
        sessionKey: ctx?.sessionKey,
        sessionId: ctx?.sessionId,
        agentId: ctx?.agentId
      });
      const args = transform ? transform(rawParams, config) : rawParams;
      const result = await callTetherTool({
        pluginRoot,
        pluginConfig: config,
        toolName: name,
        args,
        logger: api.logger
      });
      return createJsonResult(result);
    }
  });
}

export async function registerPing(api, pluginRoot, config, invokeTetherTool = callTetherTool) {
  if (!config.autoRegisterPing || !config.notifyUrl) {
    api.logger.warn(
      "[tether] ping registration skipped; autoRegisterPing disabled or notify URL unresolved",
    );
    return;
  }
  try {
    const result = await invokeTetherTool({
      pluginRoot,
      pluginConfig: config,
      toolName: "tether_register_ping",
      args: {
        agent: config.agent,
        url: config.notifyUrl,
        enabled: true
      },
      logger: api.logger
    });
    api.logger.info(
      `[tether] registered ping endpoint for ${config.agent} at ${config.notifyUrl}: ${JSON.stringify(result)}`,
    );
  } catch (error) {
    api.logger.warn(`[tether] ping registration failed: ${String(error)}`);
  }
}

export function createInboundHandler(params) {
  const { api, config, sessionState } = params;
  return async (req, res) => {
    if ((req.method ?? "GET").toUpperCase() !== "POST") {
      res.statusCode = 405;
      res.setHeader("Allow", "POST");
      res.end("Method Not Allowed");
      return true;
    }

    let body;
    try {
      body = await readJsonBody(req, 64 * 1024);
    } catch (error) {
      sendJson(res, 400, { ok: false, error: String(error) });
      return true;
    }

    let inbound;
    try {
      inbound = buildInboundMessage(body);
    } catch (error) {
      sendJson(res, 400, { ok: false, error: String(error) });
      return true;
    }

    const target = sessionState.resolve(config.sessionKey);
    const idempotencyKey = `tether:${inbound.handle}`;
    try {
      const run = await api.runtime.subagent.run({
        sessionKey: target.sessionKey,
        message: inbound.text,
        lane: config.lane,
        deliver: false,
        idempotencyKey
      });
      sendJson(res, 202, {
        ok: true,
        queued: true,
        sessionKey: target.sessionKey,
        runId: run.runId,
        idempotencyKey
      });
      return true;
    } catch (error) {
      api.logger.warn(`[tether] inbound dispatch failed: ${String(error)}`);
      sendJson(res, 502, {
        ok: false,
        error: String(error),
        sessionKey: target.sessionKey,
        idempotencyKey
      });
      return true;
    }
  };
}

function createHealthHandler(config, sessionState) {
  return async (req, res) => {
    const method = (req.method ?? "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
      res.statusCode = 405;
      res.setHeader("Allow", "GET, HEAD");
      res.end("Method Not Allowed");
      return true;
    }
    const body = {
      ok: true,
      plugin: "tether",
      agent: config.agent,
      notifyUrl: config.notifyUrl,
      notifyPath: config.notifyPath,
      hooksAliasPath: config.hooksAliasPath,
      fallbackSessionKey: config.sessionKey,
      lane: config.lane,
      activeSession: sessionState.peek(),
      mcpPath: config.mcpPath,
      dbPath: config.dbPath
    };
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(method === "HEAD" ? undefined : JSON.stringify(body));
    return true;
  };
}

const plugin = {
  id: "tether",
  name: "Tether",
  description: "Inbound Tether delivery for OpenClaw plus outbound Tether MCP tools.",
  register(api) {
    const config = resolvePluginConfig({
      pluginRoot: __dirname,
      pluginConfig: api.pluginConfig,
      processEnv: process.env,
      gatewayConfig: api.config
    });
    const sessionState = new SessionState();

    api.on("session_start", (event, ctx) => {
      sessionState.touch({
        sessionKey: event?.sessionKey ?? ctx?.sessionKey,
        sessionId: event?.sessionId ?? ctx?.sessionId,
        agentId: ctx?.agentId
      });
    });

    api.on("session_end", (event) => {
      sessionState.clearIfMatches(event?.sessionKey);
    });

    const inboundHandler = createInboundHandler({ api, config, sessionState });
    api.registerHttpRoute({
      path: config.notifyPath,
      auth: "plugin",
      match: "exact",
      handler: inboundHandler
    });
    if (config.hooksAliasPath && config.hooksAliasPath !== config.notifyPath) {
      api.registerHttpRoute({
        path: config.hooksAliasPath,
        auth: "plugin",
        match: "exact",
        handler: inboundHandler
      });
    }
    api.registerHttpRoute({
      path: "/plugins/tether/health",
      auth: "gateway",
      match: "exact",
      handler: createHealthHandler(config, sessionState)
    });

    api.registerTool(
      createTetherTool({
        api,
        pluginRoot: __dirname,
        config,
        sessionState,
        name: "tether_send",
        label: "Tether Send",
        description: "Send a Tether message to another agent.",
        schema: SEND_TOOL_SCHEMA,
        transform: (args, resolvedConfig) => ({
          ...args,
          from_agent:
            typeof args?.from_agent === "string" && args.from_agent.trim()
              ? args.from_agent.trim()
              : resolvedConfig.agent
        })
      }),
    );

    api.registerTool(
      createTetherTool({
        api,
        pluginRoot: __dirname,
        config,
        sessionState,
        name: "tether_inbox",
        label: "Tether Inbox",
        description: "Read pending Tether message handles for an agent.",
        schema: INBOX_TOOL_SCHEMA,
        transform: (args, resolvedConfig) => ({
          ...args,
          for_agent:
            typeof args?.for_agent === "string" && args.for_agent.trim()
              ? args.for_agent.trim()
              : resolvedConfig.agent
        })
      }),
    );

    api.registerTool(
      createTetherTool({
        api,
        pluginRoot: __dirname,
        config,
        sessionState,
        name: "tether_receive",
        label: "Tether Receive",
        description: "Resolve a Tether message handle to its full message content.",
        schema: RECEIVE_TOOL_SCHEMA,
        transform: (args, resolvedConfig) => ({
          ...args,
          for_agent:
            typeof args?.for_agent === "string" && args.for_agent.trim()
              ? args.for_agent.trim()
              : resolvedConfig.agent
        })
      }),
    );

    api.registerTool(
      createTetherTool({
        api,
        pluginRoot: __dirname,
        config,
        sessionState,
        name: "tether_collapse",
        label: "Tether Collapse",
        description: "Collapse a JSON value into a deterministic Tether handle.",
        schema: COLLAPSE_TOOL_SCHEMA
      }),
    );

    api.registerTool(
      createTetherTool({
        api,
        pluginRoot: __dirname,
        config,
        sessionState,
        name: "tether_resolve",
        label: "Tether Resolve",
        description: "Resolve a deterministic Tether handle back to its JSON value.",
        schema: RESOLVE_TOOL_SCHEMA
      }),
    );

    api.logger.info(
      `[tether] inbound route ${config.notifyPath} (alias: ${config.hooksAliasPath ?? "none"}), notify URL ${config.notifyUrl ?? "unresolved"}`,
    );
    void registerPing(api, __dirname, config);
  }
};

export default plugin;
