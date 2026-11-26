#!/usr/bin/env bash
# One-command resume publisher:  ./publish.sh ["commit message"] [-y]
#   1. creates the local .venv on first run (PyYAML only, nothing global)
#   2. validates YAML, builds index.html + the 1-page PDF + sitemap.xml, and runs lint checks
#   3. shows what changed and asks for confirmation (skip with -y)
#   4. commits and pushes to main -> GitHub Pages redeploys in ~1 minute
set -euo pipefail
cd "$(dirname "$0")"

export PATH="/Library/TeX/texbin:$PATH"   # MacTeX location, so latexmk is found
MSG="${1:-Update resume $(date +%Y-%m-%d)}"
ASSUME_YES="no"
for arg in "$@"; do [[ "$arg" == "-y" ]] && ASSUME_YES="yes"; done
[[ "$MSG" == "-y" ]] && MSG="Update resume $(date +%Y-%m-%d)"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "main" ]]; then
  echo "Refusing to publish: you are on '$branch', GitHub Pages serves 'main'." >&2
  exit 1
fi

# One-time bootstrap of an isolated Python environment (git-ignored)
if [[ ! -x .venv/bin/python ]]; then
  echo "Setting up .venv (first run only)..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

.venv/bin/python build.py         # aborts here on invalid YAML, LaTeX errors, or a PDF over 1 page
.venv/bin/python build.py --lint  # advisory style & ATS checks (warnings only)

if [[ -z "$(git status --porcelain)" ]]; then
  echo "Nothing changed - the published site is already up to date."
  exit 0
fi

echo
git status --short
echo
git diff --stat
echo

if [[ "$ASSUME_YES" != "yes" ]]; then
  read -rp "Commit and push to main with message \"$MSG\"? [y/N] " answer
  [[ "$answer" == [yY] ]] || { echo "Cancelled. Nothing was committed or pushed."; exit 0; }
fi

git add -A
git commit -m "$MSG"
git push origin main
echo
echo "Pushed. GitHub Pages is rebuilding: https://gabriron01.github.io/ (live in ~1 minute)"
