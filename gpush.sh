#!/bin/bash
# gpush.sh - Git Push Automation
# Usage: ./gpush.sh "Commit Message"

if [ -z "$1" ]; then
    echo "Usage: ./gpush.sh \"Commit Message\""
    exit 1
fi

echo "Detailed Status:"
git status

echo "Adding all changes..."
git add .

echo "Committing with message: $1"
git commit -m "$1"

echo "Pushing to remote..."
git push

echo "Done! Code is live on GitHub."
