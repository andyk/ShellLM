---
name: obsidian
description: Read, write, search, and manage notes in an Obsidian vault
metadata:
  shelllm:
    requires:
      env: ["OBSIDIAN_VAULT"]
---

# obsidian — Obsidian vault management

## Overview

An Obsidian vault is a folder of markdown files with a `.obsidian/` config directory. The `OBSIDIAN_VAULT` environment variable must point to the vault root. All operations are filesystem-based — Obsidian detects changes automatically when running.

## Obsidian Sync

Obsidian watches the vault directory for filesystem changes. When Obsidian is running, any file you create, edit, or delete is picked up and synced automatically (if Obsidian Sync or a sync plugin is configured). Never modify anything inside `.obsidian/` directly.

## Filesystem operations

### Read a note
```bash
cat "$OBSIDIAN_VAULT/path/to/note.md"
```

### List notes
```bash
# All notes
find "$OBSIDIAN_VAULT" -name '*.md' -not -path '*/.obsidian/*'

# Notes in a specific folder
ls "$OBSIDIAN_VAULT/folder/"*.md
```

### Create a note
```bash
cat > "$OBSIDIAN_VAULT/path/to/note.md" << 'EOF'
---
tags: [topic]
---

Note content here.
EOF
```

### Edit a note (append)
```bash
echo "New content" >> "$OBSIDIAN_VAULT/path/to/note.md"
```

### Edit a note (overwrite)
```bash
cat > "$OBSIDIAN_VAULT/path/to/note.md" << 'EOF'
Replacement content.
EOF
```

### Search by content
```bash
grep -rl "search term" "$OBSIDIAN_VAULT" --include='*.md' | grep -v '.obsidian/'
```

### Search by filename
```bash
find "$OBSIDIAN_VAULT" -name '*keyword*' -name '*.md' -not -path '*/.obsidian/*'
```

### Move / rename
```bash
mv "$OBSIDIAN_VAULT/old/path.md" "$OBSIDIAN_VAULT/new/path.md"
```
Note: Moving or renaming files does not automatically update `[[wikilinks]]` pointing to that note. If the note is linked from others, update those references manually or rely on Obsidian's built-in rename refactoring (which only works when Obsidian performs the rename via its UI).

### Delete a note
```bash
rm "$OBSIDIAN_VAULT/path/to/note.md"
```

### Manage folders
```bash
mkdir -p "$OBSIDIAN_VAULT/new/folder"
rmdir "$OBSIDIAN_VAULT/empty/folder"
```

## Tags, links, and metadata

### Find notes with a tag
```bash
grep -rl '#tagname' "$OBSIDIAN_VAULT" --include='*.md' | grep -v '.obsidian/'
```

### Find notes linking to a page
```bash
grep -rl '\[\[Page Name\]\]' "$OBSIDIAN_VAULT" --include='*.md' | grep -v '.obsidian/'
```

### Find backlinks to a note
```bash
# Find all notes that link to "My Note"
grep -rl '\[\[My Note\]\]' "$OBSIDIAN_VAULT" --include='*.md' | grep -v '.obsidian/'
```

### Read frontmatter
```bash
sed -n '/^---$/,/^---$/p' "$OBSIDIAN_VAULT/path/to/note.md"
```

### Write frontmatter
When creating notes, include YAML frontmatter between `---` markers at the top of the file:
```yaml
---
tags: [tag1, tag2]
aliases: [alternate-name]
date: 2024-01-15
---
```

## Conventions

- **Wikilinks**: Use `[[Note Name]]` to link between notes. For sections: `[[Note Name#Section]]`.
- **Tags**: Use `#tag` inline or in frontmatter `tags: [tag1, tag2]`.
- **Frontmatter**: YAML between `---` markers at the top of each file. Used for tags, aliases, dates, and custom metadata.
- **Daily notes**: Typically stored in a `daily/` or `Daily Notes/` folder with `YYYY-MM-DD.md` naming.
- **Attachments**: Images and files typically go in an `attachments/` or `assets/` folder.
- **Never touch `.obsidian/`**: This directory contains Obsidian's configuration, plugins, and theme data. Modifying it directly can corrupt settings.
