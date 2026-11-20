#!/bin/sh
# Publish the current branch's tree to the public repository as one new commit on its main branch, leaving out
# working notes (HANDOFF.md, the share assets in x-pack/). The private history stays here; the public history is
# the linear series of published states on the local branch `public`.
#   sh tools/publish.sh "message"
# If the public main branch has moved on without this checkout (a pull request merged on GitHub), the local `public`
# branch first follows it, so the push never needs force; port that change into this branch before publishing, or
# the new commit's tree would undo it. If the two have diverged, nothing is published. Then tools/publish_gate.sh
# checks that every outside change on public main (a GitHub merge, another checkout's publish) is in HEAD.
set -e
cd "$(dirname "$0")/.."
REMOTE=${REMOTE:-https://github.com/kat-titter/every-line-is-a-loop.git}
MSG=${1:-"Publish $(git rev-parse --short HEAD)"}
git remote get-url public >/dev/null 2>&1 || git remote add public "$REMOTE"
git fetch -q public main
LOCAL=$(git rev-parse -q --verify refs/heads/public || true)
UPSTREAM=$(git rev-parse refs/remotes/public/main)
if [ -z "$LOCAL" ] || git merge-base --is-ancestor "$LOCAL" "$UPSTREAM"; then
  git update-ref refs/heads/public "$UPSTREAM"  # behind or equal: follow public/main
elif ! git merge-base --is-ancestor "$UPSTREAM" "$LOCAL"; then
  echo "stop: local public ($(git rev-parse --short "$LOCAL")) and public/main ($(git rev-parse --short "$UPSTREAM")) have diverged; nothing published" >&2
  exit 1
fi  # otherwise ahead: local export commits not yet pushed, kept
sh tools/publish_gate.sh HEAD
TMP=$(mktemp -d)
git archive HEAD | tar -x -C "$TMP"
rm -rf "$TMP/HANDOFF.md" "$TMP/x-pack"
IDX=$(mktemp -u)
GIT_INDEX_FILE="$IDX" git --work-tree="$TMP" add -A
TREE=$(GIT_INDEX_FILE="$IDX" git write-tree)
COMMIT=$(git commit-tree "$TREE" -p "$(git rev-parse refs/heads/public)" -m "$MSG")
git update-ref refs/heads/public "$COMMIT"
rm -rf "$TMP" "$IDX"
git push public public:main
echo "published $COMMIT"
