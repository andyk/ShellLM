# Proposal: Agent-Native Documentation Conventions for ShellLM

**Status:** Draft
**Author:** Andy and Claude
**Date:** 2026-05-01

## Summary

The classic shell project documentation stack — man pages, READMEs, `info`, `docs/` — was designed for human readers. As LLM agents become primary consumers of project documentation, we need to rethink these conventions. This proposal outlines a documentation architecture for ShellLM (and ShellLM-managed projects) that serves both humans and agents without doubling the maintenance burden.

The core claim: **`SKILL.md` is to agents what `man` was to humans, but with procedural rather than reference framing.** ShellLM should adopt and extend this paradigm across its own project conventions.

## Background: what the classic stack assumes

Man pages, READMEs, and docs were designed around assumptions that don't hold for agent readers:

1. **The reader is a human with limited attention** — docs use hierarchy, overviews, and progressive detail
2. **The reader will actively explore** — `apropos`, `man -k`, `info` jumps, browsing
3. **The reader can infer context** — they understand shell conventions implicitly
4. **The reader needs to be convinced** — READMEs sell the project (badges, screenshots, "why use this")
5. **The reader will copy/paste examples** — examples are illustrative rather than complete

Each inverts when the reader is an agent:

1. **Attention is paid in tokens** — token efficiency dominates narrative pacing
2. **The agent reads what it's told to read** — exploration costs context window
3. **The agent has broad but shallow context** — it knows shell conventions but not your project's quirks
4. **The agent doesn't need selling** — it's already running because someone deployed it
5. **The agent will execute, not paste** — examples must be precise, runnable, unambiguous

The classic stack optimizes for the wrong reader.

## What `SKILL.md` already gets right

The Agent Skills format encodes the right shifts:

- **YAML frontmatter with `name` + `description`** — structured equivalent of `whatis`. The description is what gets matched against intent.
- **Markdown body in instruction style** — "when to use X, do Y" rather than "X takes the following arguments"
- **No SEE ALSO convention, but skills reference each other in practice** — and the agent follows references during execution, not just reading

The deep insight: **agents need procedural documentation, not reference documentation.** Man pages tell you what flags exist; skills tell you when and how to use them. That is the inversion.

## Proposal: documentation conventions for ShellLM projects

### File-level conventions

Every ShellLM project (including ShellLM itself) should adopt this layout:

```
project/
├── README.md              # humans: what, why, install
├── AGENTS.md              # agents: how to work in this repo
├── PHILOSOPHY.md          # humans: design principles (optional)
├── ROADMAP.md             # both: what's next
├── CHANGELOG.md           # both: what changed
├── skills/
│   └── <tool>/SKILL.md    # one per tool/capability the project provides
├── docs/
│   ├── human/             # narrative, philosophy, tutorials (optional)
│   └── agent/             # procedural, dense, machine-optimized (optional)
└── bin/
    └── <tool>             # --help for humans, SKILL.md for agents
```

Mapping to the classic stack:

| Classic | Agent-Native | Notes |
|---------|-------------|-------|
| `README.md` | `README.md` (humans) + `AGENTS.md` (agents) | Split entry points |
| `man <tool>` | `skills show <tool>` | SKILL.md is the new man page |
| `info` | Conversational exploration via `shelly send` | Generated on demand from primary sources |
| `--help` | `--help` (humans) + SKILL.md (agents) | Both audiences keep their interface |
| `docs/` | `docs/human/` + `docs/agent/` | Optional split for projects with deep docs |
| `CHANGELOG.md` | `CHANGELOG.md` | Format converges; both audiences benefit |

### `AGENTS.md` as the agent entry point

`AGENTS.md` answers the question: *"I'm an agent and I just `cd`'d into this directory. What do I need to know to work here?"*

The convention is already emerging in the wild — Cursor's `.cursorrules`, Continue's `.continuerules`, Claude Code's `CLAUDE.md`. `AGENTS.md` is the project-agnostic name and should be the ShellLM standard.

Recommended `AGENTS.md` structure:

```markdown
# Agent Guide

## Project layout
[where things live]

## Conventions
[invariants, naming, style]

## Available tools
[scripts, binaries, skills bundled with this project]

## State and config locations
[where data lives at runtime]

## Things not to do
[footguns, irreversible actions, sacred files]

## How to verify changes
[tests, lint, build]
```

### Skills as the new man pages

For each tool a project provides, ship a `SKILL.md` alongside it. The skill describes:

- **When to use it** (intent matching)
- **How to invoke it** (the common patterns, not exhaustive flags)
- **How it composes with other tools** (pipelines, follow-ups)
- **What to expect** (output format, side effects, exit codes when meaningful)

Skills are **denser than man pages and more composable**. A man page enumerates all flags; a skill curates the subset that matters and trusts the agent's training data for the rest. A skill can reference other skills, and the agent follows those references during execution.

The reformulation: **the skill is the man page rewritten for an audience with broader background knowledge and shorter attention.** Less reference, more guidance. Less complete, more useful in the moment.

### Self-describing tools via shipped skills

Every tool ShellLM ships should have a corresponding `SKILL.md` in `skills/`. This means `shelllm`, `shelly`, `mem`, and `skills` itself each have skill files that describe how an agent should use them.

```
shelllm/
└── skills/
    ├── shelllm/SKILL.md
    ├── shelly/SKILL.md
    ├── mem/SKILL.md
    └── skills/SKILL.md      # recursion: skills tool described as a skill
```

This is elegant because the same discovery and installation mechanism that surfaces third-party skills also surfaces the core tools. There is no special case for "built-in" capabilities — everything is a skill, and the agent uses the same lookup path to find any of them.

## Avoiding the maintenance trap

The naive split (separate human and agent docs) creates drift. To avoid it:

1. **One source of truth per concern.** README is authoritative for humans. AGENTS.md is authoritative for agents. Skills are authoritative for tool use. Where they overlap, one links to the other.
2. **Generate where possible.** A `housekeeping` skill (see below) can keep AGENTS.md in sync with the actual project layout.
3. **Code comments and docstrings serve both audiences** — no need to duplicate.

## Optional: agent-aware annotations in shared docs

For projects that don't want two files, embedded machine-readable hints in a single README is a more sophisticated alternative:

```markdown
# myproject

A tool that does X.

<!-- agent:skip -->
[![badges humans care about]]
<!-- /agent:skip -->

## What it does
...prose...

<!-- agent:start -->
## Quick reference
| Command | Effect |
|---------|--------|
| `myproject init` | ... |
| `myproject run` | ... |

State directory: `./.myproject/`
Config file: `./myproject.toml`
<!-- agent:end -->
```

The agent's reader strips `agent:skip` blocks and prioritizes `agent:start/end` blocks. Humans see the whole thing rendered.

This is probably over-engineered for now. The two-file approach (`README.md` + `AGENTS.md`) is simpler and the convention is already emerging. Worth keeping as a long-term option.

## The `housekeeping` skill (replacing the meta-agent idea)

Rather than a long-running self-improver daemon, ship a `housekeeping` skill that any shelly session can invoke:

```bash
shelly send "run housekeeping"
```

The skill instructs the agent to:

- Read the recent git log
- Read `AGENTS.md` and check it against the actual project layout
- Verify any new tools have corresponding `SKILL.md` files
- Flag stale skill files
- Check if `ROADMAP.md` needs updating based on completed work
- Propose changes via PR or direct edit

This is more Unix-y than a daemon:

- No long-running process to manage
- Composable with cron, git hooks, CI, manual invocation
- Same auth and permissions as everything else
- Watching can be event-driven (git pre-commit) or scheduled (`cron` calls `shelly send "run housekeeping"`) or manual

The "meta agent" exists, but it's just a shelly session running a skill — same architecture as everything else.

## Migration plan for ShellLM itself

Phase 1 — Foundation:

- [ ] Add `AGENTS.md` to the ShellLM repo
- [ ] Split current README into `README.md` (humans) and `AGENTS.md` (agents)
- [ ] Write `SKILL.md` for each of `shelllm`, `shelly`, `mem`, `skills`
- [ ] Place them in `skills/`

Phase 2 — Conventions doc:

- [ ] Write `docs/human/agent-native-docs.md` documenting these conventions for downstream projects
- [ ] Reference it in `AGENTS.md`

Phase 3 — Housekeeping skill:

- [ ] Write `skills/housekeeping/SKILL.md`
- [ ] Test by running `shelly send "run housekeeping"` against the repo
- [ ] Iterate on the skill until it produces useful audits

Phase 4 — Evangelism:

- [ ] Document the `AGENTS.md` + shipped-skills pattern as a recommended convention for ShellLM-friendly projects
- [ ] Submit upstream proposals to the Agent Skills standard if the patterns prove valuable

## Open questions

1. **Should `AGENTS.md` have a standardized schema?** A loose convention is more flexible; a schema makes tooling easier. Likely loose for now.
2. **Where do agent-specific examples live?** In SKILL.md? In `docs/agent/`? Probably SKILL.md, with `docs/agent/` reserved for cross-cutting concerns.
3. **How do skills version?** When a tool's interface changes, the skill needs to update. Should skills be versioned alongside the tool, or independently? Likely alongside, in the same repo.
4. **What's the right discovery story for `AGENTS.md` across nested directories?** Walk up the tree like git does for `.git/`? Concatenate? Override? Worth designing once a few projects have adopted it.

## Related work

- Agent Skills (Anthropic open standard)
- Cursor `.cursorrules`
- Continue `.continuerules`
- Claude Code `CLAUDE.md`
- OpenClaw shipped skills
- askill.sh / skills.sh registries

## Appendix: why not just better READMEs?

A common objection: "Just write better READMEs and agents will read them fine."

This misses two things:

1. **Token cost.** A 5,000-word README that sells the project, includes badges, and tells the agent's life story burns context window for nothing. Agents need a dense, instructional projection.
2. **Discovery.** The agent doesn't know which README to read among many. Skills have structured frontmatter precisely so an agent can match intent ("I need to search the web") to capability without reading every doc in the repo first.

The split is not about quality — it's about audience-appropriate density and machine-discoverable structure.
