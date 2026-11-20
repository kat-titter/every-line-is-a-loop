#!/bin/sh
# Stops a publish that would undo work already on the public main branch. tools/publish.sh replaces the whole public
# tree with this checkout's, so a pull request merged on GitHub, or another session's publish, vanishes unless the
# commit being published already holds it.
#   sh tools/publish_gate.sh [commit]        (default HEAD; tools/publish.sh runs it before pushing)
# Each public commit since SINCE that is not the export of an ancestor of the candidate (a GitHub merge, or a publish
# from elsewhere) must be contained: a 3-way merge of its change, with its parent as the base, into the candidate or
# into an ancestor of it (the port) gives back that commit's own tree. Edits after the port are the branch's own work,
# but a file the outside commit touched that is now nearer its old version than its new one fails as a rollback.
# A port that needed a hand merge (the same lines edited on both sides) never merges cleanly; once someone has read it,
# its line in tools/publish_reviewed.txt ("<sha> <who checked what>") stands in for the clean merge.
set -e
cd "$(dirname "$0")/.."
SINCE=${SINCE:-69af9f1}  # first publish holding PR #1's port; older public commits were superseded on purpose
C=$(git rev-parse "${1:-HEAD}^{commit}")
CT=$(git rev-parse "$C^{tree}")
git remote get-url public >/dev/null 2>&1 || git remote add public https://github.com/kat-titter/every-line-is-a-loop.git
git fetch -q public main
UP=$(git rev-parse refs/remotes/public/main)
sig() { git ls-tree -r "$1" | grep -v -e '	HANDOFF.md$' -e '	x-pack/' | shasum | cut -c1-40; }
OURS=$(mktemp)
for a in $(git rev-list --max-count=300 "$C"); do sig "$a"; done | sort -u > "$OURS"
FAIL=0; N=0
for p in $(git rev-list "$SINCE..$UP"); do
  grep -qx "$(sig "$p")" "$OURS" && continue  # an export of the candidate's own history
  N=$((N + 1)); NAME=$(git log -1 --format='%h %s' "$p" | cut -c1-90)
  PORT=""
  for a in $(git rev-list --since="$(git log -1 --format=%ct "$p" | awk '{print $1 - 86400}')" "$C"); do
    T=$(git merge-tree --write-tree --merge-base="$p^" "$a" "$p" 2>/dev/null | head -1) || continue
    [ "$T" = "$(git rev-parse "$a^{tree}")" ] && { PORT=$a; break; }
  done
  if [ -z "$PORT" ] && grep -q "^$(git rev-parse --short=7 "$p")" tools/publish_reviewed.txt 2>/dev/null; then PORT=reviewed; fi
  if [ -z "$PORT" ]; then echo "FAIL missing (or hand-merged and not yet in tools/publish_reviewed.txt): $NAME"
    for f in $(git diff --name-only "$p^" "$p"); do
      echo "       $f: $(git diff --numstat "$p^" "$C" -- "$f" | awk '{s += $1 + $2} END {print s + 0}') lines from before, $(git diff --numstat "$p" "$C" -- "$f" | awk '{s += $1 + $2} END {print s + 0}') from after"
    done; FAIL=1; continue; fi
  BACK=""
  for f in $(git diff --name-only "$p^" "$p"); do
    old=$(git diff --numstat "$p^" "$C" -- "$f" | awk '{s += $1 + $2} END {print s + 0}')
    new=$(git diff --numstat "$p" "$C" -- "$f" | awk '{s += $1 + $2} END {print s + 0}')
    [ "$old" -lt "$new" ] && BACK="$BACK $f($old<$new)"
  done
  if [ -n "$BACK" ]; then echo "FAIL rolled back after its port ($PORT): $NAME"; echo "      $BACK"; FAIL=1
  elif [ "$PORT" = reviewed ]; then echo "ok   hand-merged port, reviewed, not rolled back: $NAME"
  elif [ "$PORT" = "$C" ]; then echo "ok   contained: $NAME"
  else echo "ok   contained since $(git rev-parse --short "$PORT"), later edits on top: $NAME"; fi
done
rm -f "$OURS"
echo "gate: $(git rev-parse --short "$C") against public/main $(git rev-parse --short "$UP"), $N outside commit(s) checked since $SINCE"
[ $FAIL = 0 ] && echo "GATE PASS" || { echo "GATE FAIL: nothing published"; exit 1; }
