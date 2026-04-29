#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local/bin}"
SYMLINKS="${SYMLINKS:-0}"
TOOLS=(shellm shellm-docker shellm-docker-broker shelly skills mem llm shellm-explore context traj)

while [[ $# -gt 0 ]]; do
    case "$1" in
        --symlinks) SYMLINKS=1; shift ;;
        --prefix)   PREFIX="${2:?--prefix requires a path}"; shift 2 ;;
        --help|-h)
            cat <<'EOF'
Usage: ./install.sh [options]

Installs shellm tools from bin/ to a directory on your PATH.

Options:
  --prefix DIR   Install directory (default: ~/.local/bin)
  --symlinks     Create symlinks instead of copies (edits take effect without reinstalling)
  -h, --help     Show this help

Environment variables:
  PREFIX         Same as --prefix
  SYMLINKS=1     Same as --symlinks

Examples:
  ./install.sh                          # copy to ~/.local/bin
  ./install.sh --symlinks               # symlink to ~/.local/bin
  ./install.sh --prefix /usr/local/bin  # copy to /usr/local/bin (may need sudo)
  PREFIX=~/bin SYMLINKS=1 ./install.sh  # symlink to ~/bin
EOF
            exit 0
            ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
    esac
done

mkdir -p "$PREFIX"

for tool in "${TOOLS[@]}"; do
    if [[ "$SYMLINKS" -eq 1 ]]; then
        ln -sf "$(pwd)/bin/$tool" "$PREFIX/$tool"
        echo "Linked $tool → $PREFIX/$tool"
    else
        cp "bin/$tool" "$PREFIX/$tool"
        chmod +x "$PREFIX/$tool"
        echo "Installed $tool → $PREFIX/$tool"
    fi
done

case ":$PATH:" in
    *":$PREFIX:"*) ;;
    *)
        echo
        echo "Warning: $PREFIX is not on your PATH."
        echo "Add this line to your shell rc (~/.zshrc, ~/.bashrc, etc.):"
        echo "  export PATH=\"$PREFIX:\$PATH\""
        ;;
esac
