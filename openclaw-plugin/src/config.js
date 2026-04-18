import fs from "node:fs";
import path from "node:path";

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function readTrimmedString(source, key) {
  const value = source[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function readPositiveNumber(source, key) {
  const value = source[key];
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value.trim());
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return undefined;
}

function fileExists(filePath) {
  try {
    return fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function normalizePathValue(value) {
  if (!value) {
    return undefined;
  }
  return value.startsWith("/") ? value : `/${value}`;
}

function resolveHooksBasePath(gatewayConfig) {
  const hooks = asObject(gatewayConfig?.hooks);
  if (hooks.enabled !== true) {
    return undefined;
  }
  const raw = readTrimmedString(hooks, "path") ?? "/hooks";
  if (raw === "/") {
    return "/hooks";
  }
  return raw.startsWith("/") ? raw.replace(/\/+$/, "") : `/${raw.replace(/\/+$/, "")}`;
}

function resolveDefaultNotifyPath(gatewayConfig) {
  const hooksBasePath = resolveHooksBasePath(gatewayConfig);
  if (hooksBasePath === "/hooks") {
    return "/plugins/tether/notify";
  }
  return "/hooks/tether";
}

function resolveHooksAliasPath(gatewayConfig) {
  const hooksBasePath = resolveHooksBasePath(gatewayConfig);
  if (hooksBasePath === "/hooks") {
    return undefined;
  }
  return "/hooks/tether";
}

function resolveMcpPath(pluginRoot, pluginConfig, processEnv) {
  const rawOverride =
    readTrimmedString(pluginConfig, "mcpPath") ?? readTrimmedString(processEnv, "TETHER_MCP_PATH");
  if (rawOverride) {
    return path.isAbsolute(rawOverride) ? rawOverride : path.resolve(pluginRoot, rawOverride);
  }

  const candidates = [
    path.resolve(pluginRoot, "..", "tether", "mcp_server.py"),
    path.resolve(pluginRoot, "..", "..", "tether", "mcp_server.py"),
    path.resolve(process.cwd(), "tether", "mcp_server.py")
  ];
  for (const candidate of candidates) {
    if (fileExists(candidate)) {
      return candidate;
    }
  }
  return candidates[0];
}

export function resolvePluginConfig(params) {
  const pluginConfig = asObject(params.pluginConfig);
  const processEnv = asObject(params.processEnv);
  const notifyPath =
    normalizePathValue(readTrimmedString(pluginConfig, "notifyPath")) ??
    resolveDefaultNotifyPath(params.gatewayConfig);
  const hooksAliasPath = resolveHooksAliasPath(params.gatewayConfig);
  const notifyUrl =
    readTrimmedString(pluginConfig, "notifyUrl") ??
    readTrimmedString(processEnv, "TETHER_NOTIFY_URL") ??
    `http://127.0.0.1:${readTrimmedString(processEnv, "TETHER_NOTIFY_PORT") ?? "7705"}${notifyPath}`;

  return {
    agent:
      readTrimmedString(pluginConfig, "agent") ??
      readTrimmedString(processEnv, "TETHER_AGENT") ??
      "openclaw",
    sessionKey:
      readTrimmedString(pluginConfig, "sessionKey") ??
      readTrimmedString(processEnv, "TETHER_SESSION_KEY") ??
      "hook:tether",
    lane:
      readTrimmedString(pluginConfig, "lane") ??
      readTrimmedString(processEnv, "TETHER_LANE") ??
      "tether",
    notifyPath,
    hooksAliasPath,
    notifyUrl,
    autoRegisterPing:
      typeof pluginConfig.autoRegisterPing === "boolean" ? pluginConfig.autoRegisterPing : true,
    mcpPath: resolveMcpPath(params.pluginRoot, pluginConfig, processEnv),
    dbPath:
      readTrimmedString(pluginConfig, "dbPath") ?? readTrimmedString(processEnv, "TETHER_DB"),
    mcpTimeoutMs:
      readPositiveNumber(pluginConfig, "mcpTimeoutMs") ??
      readPositiveNumber(processEnv, "TETHER_MCP_TIMEOUT_MS") ??
      20_000
  };
}
