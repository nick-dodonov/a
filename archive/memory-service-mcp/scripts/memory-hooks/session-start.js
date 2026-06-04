#!/usr/bin/env node

const {
  hookContinue,
  loadConfig,
  postJson,
  printJson,
  projectFromCwd,
  projectTag,
  readStdinJson,
  sessionStartOutput,
  truncate,
} = require("./lib");

async function run() {
  const input = await readStdinJson();
  const cwd = input.cwd || process.cwd();
  const config = loadConfig(cwd);
  const project = projectFromCwd(cwd);
  const projTag = projectTag(cwd, config.projectTagPrefix);

  const queries = (config.startQueries || []).map((q) => String(q).replaceAll("{project}", project));
  const byHash = new Map();

  for (const query of queries) {
    const result = await postJson(config, "/api/search", {
      query,
      limit: config.queryLimit || 4,
    });

    if (!result.ok || !result.body || !Array.isArray(result.body.results)) {
      continue;
    }

    for (const item of result.body.results) {
      const memory = item && item.memory;
      if (!memory || !memory.content_hash) {
        continue;
      }
      if (!byHash.has(memory.content_hash)) {
        byHash.set(memory.content_hash, {
          content: memory.content || "",
          tags: Array.isArray(memory.tags) ? memory.tags : [],
          score: typeof item.similarity_score === "number" ? item.similarity_score : 0,
        });
      }
    }
  }

  const selected = [...byHash.values()]
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);

  if (selected.length === 0) {
    printJson(hookContinue());
    return;
  }

  const bulletLines = selected.map((m, index) => {
    const score = Number.isFinite(m.score) ? m.score.toFixed(2) : "n/a";
    const tagHint = m.tags.length ? ` [tags: ${m.tags.slice(0, 4).join(", ")}]` : "";
    return `${index + 1}. ${truncate(m.content, 220)} (score ${score})${tagHint}`;
  });

  const additionalContext = [
    `Recovered memory context for ${project}.`,
    `Project tag: ${projTag}.`,
    ...bulletLines,
  ].join("\n");

  printJson(sessionStartOutput(additionalContext));
}

run().catch(() => {
  printJson(hookContinue());
});
