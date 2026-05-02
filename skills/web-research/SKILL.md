---
name: web-research
description: Research topics using the web via curl. Use when the user asks to look something up, find current information, or research a topic online.
metadata:
  shelllm:
    requires:
      bins: ["curl", "jq"]
---

# web-research

## When to use

User asks to look something up, find current information, research a topic, or answer a question that requires up-to-date knowledge beyond what you have in context.

## Common operations

### Fetch a web page
```bash
curl -sL "https://example.com" | head -200
```

### Search via DuckDuckGo (HTML)
```bash
query="your search terms"
curl -sL "https://html.duckduckgo.com/html/?q=$(printf '%s' "$query" | jq -sRr @uri)" \
  | grep -oP 'href="https?://[^"]*"' | head -10
```

### Fetch and extract text from HTML
```bash
# Strip HTML tags for readable text
curl -sL "$url" | sed 's/<[^>]*>//g' | sed '/^$/d' | head -100
```

### Fetch JSON APIs
```bash
curl -s "https://api.example.com/endpoint" | jq '.results[]'
```

### Download a file
```bash
curl -sLO "https://example.com/file.txt"
```

## Tips

- Always use `-s` (silent) and `-L` (follow redirects) with curl
- Pipe HTML through `sed 's/<[^>]*>//g'` for rough text extraction
- Use `head` or `tail` to limit output — full web pages are huge
- For JavaScript-heavy sites, raw curl won't render dynamic content
- Rate-limit requests — don't hammer endpoints in tight loops
- Check robots.txt before scraping extensively
