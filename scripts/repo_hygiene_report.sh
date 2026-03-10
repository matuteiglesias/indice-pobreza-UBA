#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

echo "# Repo hygiene report"
echo "generated: $(date -Iseconds)"
echo

echo "## Branch and remotes"
echo "branch: $(git branch --show-current)"
if git remote | grep -q .; then
  git remote -v
else
  echo "(no remotes configured)"
fi
echo

echo "## Upstream divergence"
if git remote | grep -q .; then
  git fetch --all --prune >/dev/null 2>&1 || true
  current_branch="$(git branch --show-current)"
  upstream_ref=""
  if upstream_ref=$(git rev-parse --abbrev-ref --symbolic-full-name "${current_branch}@{upstream}" 2>/dev/null); then
    read -r behind ahead < <(git rev-list --left-right --count "${upstream_ref}...HEAD")
    echo "upstream: ${upstream_ref}"
    echo "ahead: ${ahead}"
    echo "behind: ${behind}"
  else
    echo "(no upstream tracking branch configured)"
  fi
else
  echo "(skipped: no remotes configured)"
fi
echo

echo "## Working tree summary"
status_output="$(git status --porcelain)"
if [[ -z "$status_output" ]]; then
  echo "clean working tree"
else
  echo "$status_output" | awk '
    BEGIN {m=0;a=0;d=0;r=0;u=0;o=0}
    {
      x=substr($0,1,1); y=substr($0,2,1);
      if (x=="?" && y=="?") {u++; next}
      if (x=="A" || y=="A") a++;
      if (x=="M" || y=="M") m++;
      if (x=="D" || y=="D") d++;
      if (x=="R" || y=="R") r++;
      if (!(x ~ /[AMDR?]/ || y ~ /[AMDR?]/)) o++;
    }
    END {
      printf "added: %d\nmodified: %d\ndeleted: %d\nrenamed: %d\nuntracked: %d\nother: %d\n", a,m,d,r,u,o
    }'
  echo
  git status --short
fi
echo

echo "## Largest tracked files (top 20)"
git ls-files -z | xargs -0 du -h 2>/dev/null | sort -hr | head -n 20
