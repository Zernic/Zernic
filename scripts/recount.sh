#!/usr/bin/env bash
# Refresh the commit and line counts in scripts/langs-snapshot.json.
# Clones every repo I own, counts commits that are mine and lines of real
# source, and prints the two numbers. node_modules, lockfiles, binaries and
# generated folders are excluded, and so is utopia (vendored node_modules).
set -euo pipefail
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
C=0; L=0
for r in $(gh repo list "$(gh api user --jq .login)" --limit 100 --no-archived \
           --json name,isFork --jq '.[] | select(.isFork|not) | .name'); do
  [ "$r" = utopia ] && continue
  git clone -q "https://$(gh auth token)@github.com/$(gh api user --jq .login)/$r.git" "$D/$r" 2>/dev/null || continue
  c=$(git -C "$D/$r" log --all --format='%ae' 2>/dev/null | grep -vc 'noreply@anthropic.com' || true)
  l=$(git -C "$D/$r" ls-files | \
      grep -Ev '(^|/)(node_modules|vendor|dist|build|\.venv|previews|vault|data)/' | \
      grep -Ev '\.(lock|png|jpg|jpeg|gif|svg|ico|webp|pdf|woff2?|ttf|zip|db|sqlite3?|jsonl)$' | \
      grep -Ev '(package-lock\.json|yarn\.lock|poetry\.lock)$' | \
      sed "s|^|$D/$r/|" | tr '\n' '\0' | xargs -0 -r cat 2>/dev/null | wc -l)
  printf '%-24s %5s commits %8s lines\n' "$r" "$c" "$l"
  C=$((C+c)); L=$((L+l))
done
echo "---"; echo "commits: $C   lines: $L   (paste into scripts/langs-snapshot.json)"
