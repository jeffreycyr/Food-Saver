#!/usr/bin/env bash
set -e
REPO_NAME=food-saver
git init
git add .
git commit -m "Initial commit — FoodSaver"
if command -v gh >/dev/null 2>&1; then
  gh repo create "$REPO_NAME" --public --source=. --push
  echo "Pushed to GitHub: $REPO_NAME"
else
  echo "No gh CLI detected. Create a repo on GitHub and push manually."
  echo "Example: git remote add origin git@github.com:your-username/$REPO_NAME.git && git push -u origin main"
fi
