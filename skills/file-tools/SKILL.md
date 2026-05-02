---
name: file-tools
description: Read, write, edit, and search files using view, put, sub, and glob
metadata:
  shelllm:
    requires:
      bins: ["view", "put", "sub", "glob"]
---

# file-tools

## Instructions

You have four file tools available. Prefer these over raw shell equivalents.

### view -- Read files
- Outputs with line numbers (like cat -n). Use line numbers from view output
  as the exact strings for sub.
- Range selection: `view file 10:20` or `view file --offset 10 --limit 5`
- Detects and refuses binary files.

### sub -- Edit files
- Exact literal string match (not regex). Copy-paste from view output.
- Fails if match is not unique (use --replace-all for multiple).
- For multi-line edits, use --old-file / --new-file.
- Atomic write (temp + mv).

### put -- Write files
- Reads stdin: `echo "content" | put file`
- Refuses to overwrite unless --force. Creates dirs with --parents.
- Atomic write.

### glob -- Find files
- Git-aware: respects .gitignore in git repos.
- Results sorted newest-first by mtime.
- `glob '**/*.py'` for recursive, `glob '*.sh' src/` for scoped.

### Workflow
1. glob to find files
2. view to read them
3. sub to edit, put to create new files
