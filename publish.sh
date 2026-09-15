#!/bin/sh
# Push this project to GitHub.
#
#   sh publish.sh <github-user> <token> [repo-name]
#   OWNER=winreboot sh publish.sh winreboot2 <token>      # push to another account's repo
#
# The token is a fine-grained personal access token with, for this repository:
#   Contents: Read and write
# Create one at: github.com -> Settings -> Developer settings -> Personal access tokens
#
# Fine-grained tokens usually CANNOT create repositories, so if the repo is
# missing the script tells you to create it by hand (about fifteen seconds).
set -e
USER="$1"
TOKEN="$2"
REPO="${3:-apiary-eyes}"
OWNER="${OWNER:-$USER}"
[ -n "$USER" ] && [ -n "$TOKEN" ] || { echo "usage: sh publish.sh <github-user> <token> [repo-name]"; exit 1; }
cd "$(dirname "$0")"

api() { curl -s -o /tmp/gh.json -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
        -H "Accept: application/vnd.github+json" "$@"; }

echo "Looking for $OWNER/$REPO ..."
CODE=$(api "https://api.github.com/repos/$OWNER/$REPO")
if [ "$CODE" = "200" ]; then
  echo "  found it."
else
  echo "  not visible to this token (HTTP $CODE). Trying to create it ..."
  CODE=$(api -X POST https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO\",\"private\":false,\"has_issues\":true,\"description\":\"Open-source bee traffic counting: Raspberry Pi 5 cameras + YOLO11/ByteTrack -> InfluxDB\"}")
  if [ "$CODE" = "201" ]; then
    echo "  created."
  else
    echo
    echo "  Could not create it (HTTP $CODE):"
    sed -n 's/.*"message": *"\([^"]*\)".*/    \1/p' /tmp/gh.json
    echo
    echo "  Do this instead:"
    echo "    1. github.com -> New repository -> owner $OWNER, name $REPO, Public,"
    echo "       and leave every 'initialize with' box UNCHECKED"
    echo "    2. Edit your token -> Repository access -> add $REPO,"
    echo "       Permissions -> Contents: Read and write"
    echo "    3. run this script again"
    exit 1
  fi
fi

if [ ! -d .git ]; then
  git init -b main
  git add .
  git -c user.name="$USER" -c user.email="$USER@users.noreply.github.com" \
      commit -m "Apiary Eyes v$(cat VERSION): Pi 5 camera node, YOLO11 counter, training scripts"
fi
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$OWNER/$REPO.git"

echo "Pushing ..."
git push -u "https://$USER:$TOKEN@github.com/$OWNER/$REPO.git" main

echo
echo "Done: https://github.com/$OWNER/$REPO"
echo "In the repo's Settings: Features -> tick Discussions, so people can ask questions."
