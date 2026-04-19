import test from "node:test";
import assert from "node:assert/strict";
import { Readable, Writable } from "node:stream";

import plugin, {
  buildInboundMessage,
  createInboundHandler,
  registerPing,
} from "../index.js";

class FakeResponse extends Writable {
  constructor() {
    super();
    this.statusCode = 200;
    this.headers = {};
    this.body = "";
  }

  setHeader(name, value) {
    this.headers[name.toLowerCase()] = value;
  }

  _write(chunk, _encoding, callback) {
    this.body += chunk.toString("utf8");
    callback();
  }
}

function makeJsonRequest(payload, method = "POST") {
  const body = Buffer.from(JSON.stringify(payload), "utf8");
  const req = new Readable({
    read() {
      this.push(body);
      this.push(null);
    },
  });
  req.method = method;
  req.url = "/plugins/tether/notify";
  req.headers = { "content-length": String(body.length) };
  return req;
}

test("buildInboundMessage uses native OpenClaw notification format", () => {
  assert.deepEqual(buildInboundMessage({
    from: "claude",
    handle: "h&l_messages_deadbeef",
    subject: "T-055 done",
  }), {
    from: "claude",
    handle: "h&l_messages_deadbeef",
    subject: "T-055 done",
    text: "[Tether] From agent: claude\nHandle: 'h&l_messages_deadbeef'",
  });
});

test("createInboundHandler dispatches inbound Tether mail into the session lane", async () => {
  const calls = [];
  const api = {
    runtime: {
      subagent: {
        async run(params) {
          calls.push(params);
          return { runId: "run-123" };
        },
      },
    },
    logger: {
      warn() {},
      info() {},
    },
  };
  const config = {
    sessionKey: "hook:tether",
    lane: "tether",
  };
  const sessionState = {
    resolve() {
      return { sessionKey: "agent:main:webchat:dm:user-1" };
    },
  };
  const handler = createInboundHandler({ api, config, sessionState });
  const req = makeJsonRequest({
    from: "claude",
    handle: "h&l_messages_deadbeef",
    subject: "hello",
  });
  const res = new FakeResponse();

  const handled = await handler(req, res);

  assert.equal(handled, true);
  assert.equal(res.statusCode, 202);
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], {
    sessionKey: "agent:main:webchat:dm:user-1",
    message: "[Tether] From agent: claude\nHandle: 'h&l_messages_deadbeef'",
    lane: "tether",
    deliver: false,
    idempotencyKey: "tether:h&l_messages_deadbeef",
  });
});

test("plugin register wires native HTTP routes and tools without deprecated hooks api", async () => {
  const routes = [];
  const tools = [];
  const events = [];
  const api = {
    pluginConfig: {
      autoRegisterPing: false,
    },
    config: {
      hooks: {
        enabled: true,
        path: "/hooks",
      },
    },
    logger: {
      info() {},
      warn() {},
      error() {},
    },
    on(name, handler) {
      events.push({ name, handler });
    },
    registerHttpRoute(route) {
      routes.push(route);
    },
    registerTool(tool) {
      tools.push(tool);
    },
    runtime: {
      subagent: {
        async run() {
          return { runId: "noop" };
        },
      },
    },
  };

  await plugin.register(api);

  assert.equal(routes.length, 2);
  assert.deepEqual(routes.map((route) => route.path), [
    "/plugins/tether/notify",
    "/plugins/tether/health",
  ]);
  assert.deepEqual(events.map((event) => event.name), ["session_start", "session_end"]);
  assert.equal(tools.length, 5);
});

test("registerPing calls tether_register_ping with the resolved notify URL", async () => {
  const invocations = [];
  const api = {
    logger: {
      info() {},
      warn() {},
    },
  };
  await registerPing(
    api,
    "/tmp/openclaw-plugin",
    {
      autoRegisterPing: true,
      notifyUrl: "http://127.0.0.1:7705/plugins/tether/notify",
      agent: "openclaw",
    },
    async (params) => {
      invocations.push(params);
      return { ok: true };
    },
  );

  assert.equal(invocations.length, 1);
  assert.equal(invocations[0].toolName, "tether_register_ping");
  assert.deepEqual(invocations[0].args, {
    agent: "openclaw",
    url: "http://127.0.0.1:7705/plugins/tether/notify",
    enabled: true,
  });
});
