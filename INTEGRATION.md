# GitMCP Integration Configuration

## Server Configuration for Anthropic Integrations

Replace YOUR_GITHUB_TOKEN with your actual GitHub Personal Access Token.

```json
{
  "type": "url",
  "url": "https://your-server.com/mcp/http",
  "name": "gitmcp-integration",
  "authorization_token": "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
}
```

## Anthropic API Usage Example

```bash
curl https://api.anthropic.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: mcp-client-2025-04-04" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1000,
    "messages": [{"role": "user", "content": "List my repositories"}],
    "mcp_servers": [{
      "type": "url",
      "url": "https://your-server.com/mcp/http",
      "name": "gitmcp",
      "authorization_token": "YOUR_GITHUB_TOKEN"
    }]
  }'
```

## Deployment Options

- **Local Development**: `python remote_server.py`
- **Docker**: `docker build -t gitmcp . && docker run -p 8000:8000 gitmcp`
- **Docker Compose**: `docker-compose up -d`
- **Cloud Platforms**: Railway, Render, Vercel, Heroku
