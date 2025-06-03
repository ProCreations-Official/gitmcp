#!/bin/bash

# GitMCP Remote Server Startup Script
# This script helps you quickly start the GitMCP remote server

echo "🚀 Starting GitMCP Remote Server..."
echo "   For Anthropic Integrations support"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if required packages are installed
python3 -c "import fastapi, uvicorn, github, mcp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing required packages..."
    pip install -r requirements.txt
fi

# Set default environment variables if not set
export HOST=${HOST:-"0.0.0.0"}
export PORT=${PORT:-"8000"}

echo "🌐 Server starting on http://${HOST}:${PORT}"
echo "📚 Endpoints:"
echo "   - Health check: http://${HOST}:${PORT}/"
echo "   - MCP HTTP: http://${HOST}:${PORT}/mcp/http" 
echo "   - MCP SSE: http://${HOST}:${PORT}/mcp/sse"
echo "   - Tools list: http://${HOST}:${PORT}/mcp/tools"
echo ""
echo "🔑 Don't forget to set your GITHUB_TOKEN environment variable!"
echo "   Get one from: https://github.com/settings/tokens"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 remote_server.py
