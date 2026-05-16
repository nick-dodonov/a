#!/usr/bin/env node

const {
  detectOverrideMode,
  hookContinue,
  loadConfig,
  printJson,
  readStdinJson,
  writeSessionOverride,
} = require("./lib");

async function run() {
  const input = await readStdinJson();
  const cwd = input.cwd || process.cwd();
  const config = loadConfig(cwd);

  const sessionId = input.sessionId || "";
  const prompt = String(input.prompt || "");
  const mode = detectOverrideMode(prompt, config.userOverrides || {});

  writeSessionOverride(cwd, sessionId, mode, prompt);

  printJson(hookContinue());
}

run().catch(() => {
  printJson(hookContinue());
});
