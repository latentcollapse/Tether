import { spawn } from "node:child_process";
import path from "node:path";

function resolvePythonCommand() {
  if (typeof process.env.PYTHON === "string" && process.env.PYTHON.trim()) {
    return process.env.PYTHON.trim();
  }
  return process.platform === "win32" ? "python" : "python3";
}

function parseJsonEnvelope(stdout, stderr) {
  const trimmed = stdout.trim();
  if (!trimmed) {
    throw new Error(`empty helper output${stderr.trim() ? `: ${stderr.trim()}` : ""}`);
  }
  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch (error) {
    throw new Error(
      `invalid helper JSON: ${String(error)}${stderr.trim() ? `; stderr: ${stderr.trim()}` : ""}`,
    );
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error("invalid helper envelope");
  }
  if (parsed.ok !== true) {
    throw new Error(
      typeof parsed.error === "string"
        ? parsed.error
        : `helper failed${stderr.trim() ? `: ${stderr.trim()}` : ""}`,
    );
  }
  return parsed.result;
}

export async function callTetherTool(params) {
  const helperPath = path.join(params.pluginRoot, "scripts", "tether_mcp_call.py");
  const pythonCommand = resolvePythonCommand();
  const args = [
    helperPath,
    "--mcp-path",
    params.pluginConfig.mcpPath,
    "--tool",
    params.toolName,
    "--args-json",
    JSON.stringify(params.args ?? {})
  ];
  const env = {
    ...process.env,
    ...(params.pluginConfig.dbPath ? { TETHER_DB: params.pluginConfig.dbPath } : {})
  };

  return await new Promise((resolve, reject) => {
    const child = spawn(pythonCommand, args, {
      cwd: params.pluginRoot,
      env,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true
    });
    let stdout = "";
    let stderr = "";
    let settled = false;

    const finish = (handler) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      handler();
    };

    const timer = setTimeout(() => {
      try {
        child.kill("SIGKILL");
      } catch {
        // ignore
      }
      finish(() => reject(new Error(`tether MCP call timed out (${params.toolName})`)));
    }, params.pluginConfig.mcpTimeoutMs);

    child.stdout?.setEncoding("utf8");
    child.stderr?.setEncoding("utf8");
    child.stdout?.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr?.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.once("error", (error) => finish(() => reject(error)));
    child.once("exit", (code) => {
      finish(() => {
        if (code !== 0) {
          try {
            parseJsonEnvelope(stdout, stderr);
          } catch (error) {
            reject(error);
            return;
          }
          reject(new Error(`tether MCP helper exited ${code ?? "?"}`));
          return;
        }
        try {
          resolve(parseJsonEnvelope(stdout, stderr));
        } catch (error) {
          reject(error);
        }
      });
    });
  });
}
