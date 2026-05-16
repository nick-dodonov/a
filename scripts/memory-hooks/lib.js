const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_CONFIG = {
  endpoint: "http://127.0.0.1:8000",
  apiKey: "your-secure-api-key-here",
  userOverrides: {
    forceRemember: "#remember",
    forceSkip: "#skip",
    skipWins: true,
  },
  projectTagPrefix: "proj",
  queryLimit: 4,
  startQueries: [
    "{project} architecture decisions",
    "{project} recent work",
    "{project} open issues",
  ],
  captureTools: [
    "create_file",
    "apply_patch",
    "run_in_terminal",
    "replace_string_in_file",
    "insert_edit_into_file",
    "delete_file",
    "create_directory",
  ],
  maxToolInputChars: 500,
  maxToolResponseChars: 500,
  sessionSummaryMaxTurns: 8,
  requestTimeoutMs: 4000,
};

function safeJsonParse(text, fallback) {
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

function readStdinJson() {
  return new Promise((resolve) => {
    let raw = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      raw += chunk;
    });
    process.stdin.on("end", () => {
      resolve(safeJsonParse(raw.trim(), {}));
    });
    process.stdin.on("error", () => resolve({}));
  });
}

function loadConfig(cwd) {
  const defaultPath = path.join(cwd || process.cwd(), ".github", "hooks", "memory-hooks.config.json");
  const configPath = process.env.MEMORY_HOOKS_CONFIG || defaultPath;
  let diskConfig = {};

  if (fs.existsSync(configPath)) {
    diskConfig = safeJsonParse(fs.readFileSync(configPath, "utf8"), {});
  }

  const endpoint = process.env.MCP_MEMORY_ENDPOINT || process.env.MEMORY_HOOKS_ENDPOINT || diskConfig.endpoint || DEFAULT_CONFIG.endpoint;
  const apiKey = process.env.MCP_MEMORY_API_KEY || process.env.MEMORY_HOOKS_API_KEY || diskConfig.apiKey || DEFAULT_CONFIG.apiKey;

  return {
    ...DEFAULT_CONFIG,
    ...diskConfig,
    endpoint,
    apiKey,
  };
}

function sanitizeTagValue(value) {
  return String(value || "workspace")
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "workspace";
}

function projectFromCwd(cwd) {
  const base = path.basename(cwd || process.cwd());
  return sanitizeTagValue(base);
}

function projectTag(cwd, prefix = "proj") {
  return `${prefix}:${projectFromCwd(cwd)}`;
}

function truncate(text, maxChars) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  if (!maxChars || value.length <= maxChars) {
    return value;
  }
  return `${value.slice(0, maxChars - 3)}...`;
}

function toPlainText(value, maxChars) {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return truncate(value, maxChars);
  }
  try {
    return truncate(JSON.stringify(value), maxChars);
  } catch {
    return "";
  }
}

async function postJson(config, apiPath, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.requestTimeoutMs || 4000);

  try {
    const headers = { "Content-Type": "application/json" };
    if (config.apiKey) {
      headers.Authorization = `Bearer ${config.apiKey}`;
    }

    const response = await fetch(`${config.endpoint}${apiPath}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const bodyText = await response.text();
    return {
      ok: response.ok,
      status: response.status,
      body: safeJsonParse(bodyText, bodyText),
    };
  } catch (error) {
    return { ok: false, status: 0, body: String(error && error.message ? error.message : error) };
  } finally {
    clearTimeout(timeout);
  }
}

function printJson(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function hookContinue() {
  return { continue: true };
}

function sessionStartOutput(additionalContext) {
  return {
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext,
    },
  };
}

function collectTranscriptMessages(transcriptPath, maxTurns) {
  if (!transcriptPath || !fs.existsSync(transcriptPath)) {
    return [];
  }

  const raw = fs.readFileSync(transcriptPath, "utf8");
  const messages = [];

  const addMessage = (role, content) => {
    const text = truncate(content, 320);
    if (!text) {
      return;
    }
    messages.push({ role: String(role || "unknown"), content: text });
  };

  const parsedArray = safeJsonParse(raw, null);
  if (Array.isArray(parsedArray)) {
    for (const item of parsedArray) {
      if (!item || typeof item !== "object") {
        continue;
      }
      addMessage(item.role || item.type, item.content || item.text || "");
    }
  } else {
    const lines = raw.split(/\r?\n/);
    for (const line of lines) {
      const parsed = safeJsonParse(line, null);
      if (!parsed || typeof parsed !== "object") {
        continue;
      }
      addMessage(parsed.role || parsed.type, parsed.content || parsed.text || parsed.message || "");
    }
  }

  if (!maxTurns || messages.length <= maxTurns) {
    return messages;
  }
  return messages.slice(-maxTurns);
}

function stateDir(cwd) {
  return path.join(cwd || process.cwd(), ".github", "hooks", ".memory-hook-state");
}

function ensureStateDir(cwd) {
  const dir = stateDir(cwd);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return dir;
}

function sessionStateFile(cwd, sessionId) {
  const safeSessionId = sanitizeTagValue(sessionId || "session");
  return path.join(ensureStateDir(cwd), `${safeSessionId}.json`);
}

function readSessionOverride(cwd, sessionId) {
  if (!sessionId) {
    return { mode: "default", updatedAt: 0 };
  }

  const filePath = sessionStateFile(cwd, sessionId);
  if (!fs.existsSync(filePath)) {
    return { mode: "default", updatedAt: 0 };
  }

  return safeJsonParse(fs.readFileSync(filePath, "utf8"), { mode: "default", updatedAt: 0 });
}

function writeSessionOverride(cwd, sessionId, mode, sourcePrompt) {
  if (!sessionId) {
    return;
  }

  const payload = {
    mode: mode || "default",
    updatedAt: Date.now(),
    sourcePrompt: truncate(sourcePrompt || "", 200),
  };

  fs.writeFileSync(sessionStateFile(cwd, sessionId), `${JSON.stringify(payload)}\n`, "utf8");
}

function detectOverrideMode(promptText, overrideConfig) {
  const prompt = String(promptText || "");
  const forceRemember = String(overrideConfig && overrideConfig.forceRemember ? overrideConfig.forceRemember : "#remember");
  const forceSkip = String(overrideConfig && overrideConfig.forceSkip ? overrideConfig.forceSkip : "#skip");
  const skipWins = overrideConfig && Object.prototype.hasOwnProperty.call(overrideConfig, "skipWins")
    ? Boolean(overrideConfig.skipWins)
    : true;

  const hasRemember = forceRemember && prompt.includes(forceRemember);
  const hasSkip = forceSkip && prompt.includes(forceSkip);

  if (hasSkip && hasRemember) {
    return skipWins ? "skip" : "remember";
  }
  if (hasSkip) {
    return "skip";
  }
  if (hasRemember) {
    return "remember";
  }
  return "default";
}

module.exports = {
  collectTranscriptMessages,
  detectOverrideMode,
  ensureStateDir,
  hookContinue,
  loadConfig,
  postJson,
  printJson,
  projectFromCwd,
  projectTag,
  readSessionOverride,
  readStdinJson,
  sessionStartOutput,
  writeSessionOverride,
  toPlainText,
  truncate,
};
