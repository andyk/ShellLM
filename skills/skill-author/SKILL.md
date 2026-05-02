---
name: skill-author
description: Create new ShellLM skills. Use when the user asks to write, author, build, or scaffold a new skill, or when an agent needs to extend its own capabilities by creating a new SKILL.md file.
---

# skill-author

## When to use

The user asks to create, write, author, build, or scaffold a new skill. Or you (the agent) need to extend your own capabilities by writing a new SKILL.md.

## What a skill is

A skill is a directory containing a `SKILL.md` file. It tells an agent *when* to use a capability and *how* to invoke it. Skills are procedural documentation, not reference docs. The agent reads a skill on demand via `skills show <name>`.

## Directory structure

```
skills/<skill-name>/
├── SKILL.md           # required: the skill definition
├── README.md          # optional: human-facing notes
└── <other files>      # optional: scripts, templates, data
```

## Frontmatter spec

```yaml
---
name: my-skill
description: One or two sentences. Be specific about WHEN to use the skill.
metadata:
  shelllm:
    requires:
      env: ["API_KEY"]           # all must be set
      bins: ["curl", "jq"]      # all must exist on PATH
      anyBins: ["gh", "hub"]    # at least one must exist
      os: ["darwin", "linux"]   # current OS must be in list
---
```

**Required:** `name` (kebab-case, matches directory name), `description`.

**Description matters.** It's matched against user intent. Bad: "manages files." Good: "Read, write, search, and append notes in an Obsidian vault. Use when the user mentions Obsidian or asks to interact with markdown notes."

**Requirements are optional.** Only declare `metadata.shelllm` if the skill needs env vars, binaries, or a specific OS. Skills with unmet requirements are filtered from `skills list`.

## Writing the body

Write for an agent reader, not a human:
- Skip marketing language and "why use this"
- Lead with concrete commands, not prose
- Use tables for command references when they fit
- Keep it under 1,000 tokens -- agent context is precious
- Examples should be copy-pasteable shell commands, not pseudocode
- Don't enumerate all flags -- teach the patterns specific to this tool

### Recommended structure

```markdown
## When to use
[Concrete intent triggers]

## Setup
[One-time prerequisites: env vars, services to enable]

## Common operations

### Operation 1
\`\`\`bash
exact command here
\`\`\`
One sentence on when/why.

### Operation 2
\`\`\`bash
exact command here
\`\`\`

## Tips
[Edge cases, gotchas, composition with other skills]
```

## Prefer curl + REST APIs over CLIs

Where possible, write skills that use `curl` against a REST API rather than wrapping a CLI tool. ShellLM minimizes installed dependencies. The SKILL.md *is* the abstraction layer.

Worth a CLI dependency when:
- Auth flows require complex local state (OAuth, multi-step token exchange)
- Significant client-side computation (signing, encryption)
- The API has bizarre quirks the CLI smooths over

## Declare requirements, don't manage secrets

If a skill needs an API key, declare it in `requires.env`. Do NOT prompt the user for the key or store it in a file. The user manages secrets via their shell environment or a secret manager.

## Self-contained and composable

A good skill teaches the agent enough to use a tool without external docs. It should also compose -- if your skill produces JSON, the agent can pipe it to `jq`, etc.

## Example: minimal skill

```yaml
---
name: cowsay
description: Generate ASCII cow art with messages. Use when the user asks for cowsay or fun ASCII art.
metadata:
  shelllm:
    requires:
      bins: ["cowsay"]
---
```

```markdown
# cowsay

## When to use
User asks for cowsay, ASCII art with a message, or fun text formatting.

## Common operations

### Say something
\`\`\`bash
cowsay "Hello, world!"
\`\`\`

### Use a different character
\`\`\`bash
cowsay -f tux "Linux rules"
\`\`\`

### List available figures
\`\`\`bash
cowsay -l
\`\`\`

### Pipe input
\`\`\`bash
echo "piped message" | cowsay
\`\`\`
```

## Testing a skill

After writing, validate:
1. `skills check <name>` -- requirements parse correctly
2. `skills show <name>` -- content renders correctly
3. Try a real prompt: `shelly send "use the X skill to do Y"` and watch what the agent does
4. Iterate based on whether the agent uses the skill correctly

## Common mistakes

- **Description too vague** -- skill never gets matched to user intent
- **Body too long** -- wastes context window; keep under 1,000 tokens
- **Missing `requires.env`** -- skill silently fails when API key isn't set
- **Writing for humans** -- marketing language, badges, "why use this" sections
- **Hardcoding paths** -- don't assume specific shell setup or directory structure
- **Not testing** -- always verify what the agent actually does with the skill

After writing a new skill, place it in the skills directory and run `skills check <name>` to verify it parses and that requirements resolve correctly. If the skill needs to be available to other agents and users, propose adding it to the project's bundled skills or publishing it to a skills registry.
