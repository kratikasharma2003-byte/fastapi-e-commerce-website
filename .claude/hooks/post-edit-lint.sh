#!/usr/bin/env bash
ruff check --fix "$CLAUDE_FILE_PATH" 2>/dev/null || true
