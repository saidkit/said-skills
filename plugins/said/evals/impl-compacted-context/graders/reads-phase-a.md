---
type: tool_used
tool: Read
input_match: "references/phase-a\\.md"
min: 1
---
The executor reads the Phase A procedure file from the skill's directory before producing Phase A output — the progressive-disclosure contract (`SKILL.md` Step 0 #12): after a compaction only the spine is re-attached, so the procedure must be read back from disk, never reconstructed from memory. (In an environment that steers agents to Bash for reads, pair this with `reads-phase-a-bash.md`.)
