---
name: verify-containment
description: Prove that nothing leaves the premises - no default route, tripwire blocked, gateway permits one destination. Use before a demo, after changing docker-compose.yml, egress/proxy.conf or app/egress.py, or when containment status looks wrong.
---

Follow `docs/playbooks/verify-containment.md` exactly. It is the source of truth, shared with
every other agent and tool; this skill only points to it.

Read `AGENTS.md` first if you have not this session, and check
`docs/DECISIONS.md` before changing any behaviour it describes.
