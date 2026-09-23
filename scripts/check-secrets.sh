#!/usr/bin/env bash
# Refuse to commit anything that looks like a credential.
#
# Written after data/secret.key -- the token signing key -- was committed and
# pushed. The previous check grepped staged diffs for "nvapi-", which a binary
# key file does not contain. This checks by *path* as well as by content, and
# treats anything under data/ that is not on the allowlist as suspect.
#
#   scripts/check-secrets.sh            check what is staged
#   scripts/check-secrets.sh --all      check every tracked file
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if [[ "${1:-}" == "--all" ]]; then
  files=$(git ls-files)
else
  files=$(git diff --cached --name-only --diff-filter=ACMR)
fi
[[ -z "$files" ]] && { echo "  secrets: nothing staged"; exit 0; }

bad=0
flag() { echo "  BLOCKED  $1  -- $2" >&2; bad=1; }

# Only these may live under data/. Everything else there is runtime state.
DATA_ALLOW='^data/(kb/[^/]+\.md|uploads/(Inspection_Report_P-204\.pdf|PID_CDU_P-204\.png)|[a-z]+/\.gitkeep)$'

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  case "$f" in
    .env|.env.*) [[ "$f" == ".env.example" ]] || flag "$f" "environment file" ;;
    *.key|*.pem|*.p12|*.pfx|*id_rsa*|*id_ed25519*) flag "$f" "key material" ;;
    data/*) [[ "$f" =~ $DATA_ALLOW ]] || flag "$f" "runtime state under data/" ;;
  esac
  # Content checks, text files only.
  if [[ -f "$f" ]] && grep -Iq . "$f" 2>/dev/null; then
    grep -nE 'nvapi-[A-Za-z0-9_-]{20,}' "$f" >/dev/null && flag "$f" "NVIDIA API key"
    grep -nE 'sk-[A-Za-z0-9]{32,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}' "$f" >/dev/null \
      && flag "$f" "API token"
    grep -nE -e '-----BEGIN [A-Z ]*PRIVATE KEY-----' "$f" >/dev/null && flag "$f" "private key"
    grep -nE 'pbkdf2_sha256\$[0-9]+\$[0-9a-f]{16,}\$' "$f" >/dev/null && flag "$f" "password hash"
  fi
done <<< "$files"

if (( bad )); then
  echo "  secrets: refusing. Unstage with: git restore --staged <file>" >&2
  exit 1
fi
echo "  secrets: clean ($(wc -l <<< "$files") files)"
