#!/usr/bin/env node

const {
  hookContinue,
  loadConfig,
  postJson,
  printJson,
  projectTag,
  readSessionOverride,
  readStdinJson,
  toPlainText,
  truncate,
} = require("./lib");

function shouldCapture(toolName, captureTools) {
  if (!toolName) {
    return false;
  }
  return (captureTools || []).includes(toolName);
}

async function run() {
  const input = await readStdinJson();
  const cwd = input.cwd || process.cwd();
  const config = loadConfig(cwd);
  const sessionId = input.sessionId || "";
  const override = readSessionOverride(cwd, sessionId);

  if (override.mode === "skip") {
    printJson(hookContinue());
    return;
  }

  const toolName = String(input.tool_name || "");
  const forcedRemember = override.mode === "remember";
  if (!forcedRemember && !shouldCapture(toolName, config.captureTools)) {
    printJson(hookContinue());
    return;
  }

  const inputText = toPlainText(input.tool_input, config.maxToolInputChars || 500);
  const responseText = toPlainText(input.tool_response, config.maxToolResponseChars || 500);

  const content = [
    `Copilot tool event: ${toolName}.`,
    inputText ? `Input: ${truncate(inputText, config.maxToolInputChars || 500)}.` : "",
    responseText ? `Result: ${truncate(responseText, config.maxToolResponseChars || 500)}.` : "",
  ]
    .filter(Boolean)
    .join(" ");

  if (!forcedRemember && (!content || content.length < 48)) {
    printJson(hookContinue());
    return;
  }

  const tags = [
    projectTag(cwd, config.projectTagPrefix),
    "agent:copilot",
    "source:hook",
    "type:action",
    `tool:${toolName}`,
    override.mode === "remember" ? "override:remember" : "",
  ].filter(Boolean);

  await postJson(config, "/api/memories", {
    content,
    tags,
    memory_type: "note",
    metadata: {
      source_hook: "PostToolUse",
      tool_name: toolName,
      session_id: sessionId,
      override_mode: override.mode || "default",
    },
  });

  printJson(hookContinue());
}

run().catch(() => {
  printJson(hookContinue());
});
