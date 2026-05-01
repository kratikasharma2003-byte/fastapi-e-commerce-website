#!/usr/bin/env bash
set -euo pipefail
echo "Installing MCP prerequisites for FastAPI projects..."
echo ""
echo "→ @modelcontextprotocol/server-github"
npm install -g @modelcontextprotocol/server-github
echo "→ @modelcontextprotocol/server-filesystem"
npm install -g @modelcontextprotocol/server-filesystem
echo "→ @modelcontextprotocol/server-postgres"
npm install -g @modelcontextprotocol/server-postgres
echo ""
echo "Done. Set these environment variables:"
echo "  export GITHUB_TOKEN=your_token_here"
echo "  export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname"
