# CLAUDE.md

**Read `AGENTS.md` first.** It is the single source of project context, kept
tool-agnostic so every agent and every teammate works from the same facts.
This file only adds what is specific to Claude Code.

@AGENTS.md

## Claude Code specifics

- Project skills live in `.claude/skills/`. Each is a thin wrapper around a
  playbook in `docs/playbooks/` — **edit the playbook, not the skill**, so other
  tools see the same change.
- Before committing, the pre-commit hook runs `scripts/check-secrets.sh`. If it
  blocks, do not bypass it with `--no-verify`; fix what it found.
- When a browser is available, verify interface changes by looking at them.
  Reading the markup missed the sign-in overlay that never disappeared (D-43).
