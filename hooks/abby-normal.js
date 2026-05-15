/**
 * Abby-Normal memory plugin for OpenCode.
 *
 * - Injects relevant memories into the first user message of each session
 *   (equivalent to Claude Code's SessionStart additionalContext hook)
 * - Re-injects at compaction so memories survive context compression
 * - Exposes abby_recall and abby_save tools for explicit memory operations
 */

import { tool } from "@opencode-ai/plugin"
import path from "path"

const SENTINEL = "<!-- abby-normal -->"

export const AbbyNormalPlugin = async ({ $, directory }) => {
  const dirname = path.basename(directory)
  let project = dirname
  try {
    const resolved = await $`memory-query resolve-project ${dirname}`.text()
    if (resolved.trim()) project = resolved.trim()
  } catch (_) {}

  async function queryMemories(query, limit = 5) {
    const result = await $`memory-query search ${query} --limit=${String(limit)}`.text()
    return result.trim()
  }

  return {
    tool: {
      abby_recall: tool({
        description: "Search abby-normal for memories relevant to the current work. Use at session start with the project name or a relevant keyword.",
        args: {
          query: tool.schema.string(),
        },
        async execute(args) {
          try {
            const memories = await queryMemories(args.query)
            return memories || "No relevant memories found."
          } catch (e) {
            return `Memory query failed: ${e.message}`
          }
        },
      }),

      abby_save: tool({
        description: "Save a memory to abby-normal. Use for decisions, gotchas, and patterns worth keeping across sessions.",
        args: {
          title: tool.schema.string(),
          content: tool.schema.string(),
          project: tool.schema.string(),
        },
        async execute(args) {
          try {
            await $`memory-query add --title=${args.title} --content=${args.content} --project=${args.project}`
            return `Saved: ${args.title}`
          } catch (e) {
            return `Save failed: ${e.message}`
          }
        },
      }),
    },

    // Inject memories into the first user message of each session.
    // Sentinel prevents re-injection on subsequent turns within the same session.
    "experimental.chat.messages.transform": async (_input, output) => {
      if (!output.messages?.length) return
      const firstUser = output.messages.find(m => m.info?.role === "user")
      if (!firstUser?.parts?.length) return
      if (firstUser.parts.some(p => p.type === "text" && p.text?.includes(SENTINEL))) return

      try {
        const memories = await queryMemories(project)
        if (!memories) return
        const ref = firstUser.parts[0]
        firstUser.parts.unshift({
          ...ref,
          type: "text",
          text: `${SENTINEL}\n## Memories relevant to: ${project}\n\n${memories}\n<!-- /abby-normal -->`,
        })
      } catch (_) {}
    },

    // Re-inject memories at compaction so they survive context compression.
    "experimental.session.compacting": async (_input, output) => {
      try {
        const memories = await queryMemories(project)
        if (memories) {
          output.context.push(`## Memories (${project})\n\n${memories}`)
        }
      } catch (_) {}
    },
  }
}
