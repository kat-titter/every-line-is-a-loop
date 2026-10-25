#!/bin/sh
# Publish the current branch's tree to the public repository as one new commit on its main branch, leaving out
# working notes (HANDOFF.md, the share assets in x-pack/). The private history stays here; the public history is
# the linear series of published states on the local branch `public`.
#   sh tools/publish.sh "message"
set -e
cd "$(dirname "$0")/.."
REMOTE=${REMOTE:-https://github.com/kat-titter/every-line-is-a-loop.git}
MSG=${1:-"Publish $(git rev-parse --short HEAD)"}
TMP=$(mktemp -d)
git archive HEAD | tar -x -C "$TMP"
rm -rf "$TMP/HANDOFF.md" "$TMP/x-pack"
IDX=$(mktemp -u)
GIT_INDEX_FILE="$IDX" git --work-tree="$TMP" add -A
TREE=$(GIT_INDEX_FILE="$IDX" git write-tree)
PARENT=$(git rev-parse -q --verify refs/heads/public || true)
if [ -n "$PARENT" ]; then COMMIT=$(git commit-tree "$TREE" -p "$PARENT" -m "$MSG"); else COMMIT=$(git commit-tree "$TREE" -m "$MSG"); fi
git update-ref refs/heads/public "$COMMIT"
rm -rf "$TMP" "$IDX"
git remote get-url public >/dev/null 2>&1 || git remote add public "$REMOTE"
git push public public:main
echo "published $COMMIT"
