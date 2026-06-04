#!/usr/bin/env node

const {
  collectTranscriptMessages,
  hookContinue,
  loadConfig,
  postJson,
  printJson,
  projectTag,
  readSessionOverride,
  readStdinJson,
  truncate,
} = require("./lib");

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

  const messages = collectTranscriptMessages(input.transcript_path, config.sessionSummaryMaxTurns || 8);
  if (override.mode !== "remember" && messages.length === 0) {
    printJson(hookContinue());
    return;
  }

  const transcriptExcerpt = messages
    .map((m) => `${m.role}: ${truncate(m.content, 240)}`)
    .join("\n");

  const content = [
    "Copilot session summary (auto-captured at Stop hook):",
    transcriptExcerpt || "No transcript content was available, but capture was forced by #remember.",
  ].join("\n");

  const tags = [
    projectTag(cwd, config.projectTagPrefix),
    "agent:copilot",
    "source:hook",
    "type:session",
    override.mode === "remember" ? "override:remember" : "",
  ].filter(Boolean);

  await postJson(config, "/api/memories", {
    content,
    tags,
    memory_type: "session",
    metadata: {
      source_hook: "Stop",
      session_id: sessionId,
      message_count: messages.length,
      override_mode: override.mode || "default",
    },
  });

  printJson(hookContinue());
}

run().catch(() => {
  printJson(hookContinue());
});
