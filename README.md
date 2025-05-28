# GitMCP - GitHub MCP Server

A Model Context Protocol (MCP) server that provides comprehensive GitHub integration for AI assistants like Claude, enabling seamless repository management, code browsing, and collaborative workflows.

## What is MCP?

The Model Context Protocol (MCP) is an open standard developed by Anthropic that enables AI assistants to connect securely with external data sources and tools. Think of it as "USB-C for AI applications" - it provides a standardized way to extend AI capabilities without custom integrations.

## Features

This GitHub MCP server provides the following capabilities:

### 🔧 Tools (AI-controlled actions)
- **Repository Management**: Create, list, and delete repositories
- **File Operations**: Read, write, edit, and search files
- **Branch Management**: Create branches and manage repository structure
- **Pull Requests**: Create and manage pull requests
- **Code Search**: Search for code across repositories
- **Batch Operations**: Update multiple files in a single commit

### 📁 Resources (Context for AI)
- Repository metadata and structure
- File contents and directory trees
- Commit history and branch information

## Installation

### Option 1: NPM (Recommended)
```bash
npm install -g gitmcp
```

### Option 2: Local Development
```bash
git clone https://github.com/[username]/gitmcp.git
cd gitmcp
npm install
npm run build
```

## Setup

### 1. GitHub Authentication

You'll need a GitHub Personal Access Token (PAT) with appropriate permissions:

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate a new token with these scopes:
   - `repo` - Full control of private repositories
   - `user` - Read user profile data
   - `delete_repo` - Delete repositories (if needed)

### 2. Configure Your AI Client

#### Claude Desktop

Add to your `claude_desktop_config.json`:

**For NPM installation:**
```json
{
  "mcpServers": {
    "gitmcp": {
      "command": "npx",
      "args": ["-y", "gitmcp"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  }
}
```

**For local development:**
```json
{
  "mcpServers": {
    "gitmcp": {
      "command": "node",
      "args": ["/path/to/gitmcp/build/index.js"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  }
}
```

#### VS Code (with Copilot)

Create `.vscode/mcp.json` in your workspace:
```json
{
  "servers": {
    "gitmcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "gitmcp"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  }
}
```

#### Cursor

Create `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "gitmcp": {
      "command": "npx",
      "args": ["-y", "gitmcp"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  }
}
```

### 3. Configuration File Locations

| Client | Global Config | Workspace Config |
|--------|---------------|------------------|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)<br>`%APPDATA%\Claude\claude_desktop_config.json` (Windows) | N/A |
| VS Code | User Settings (`mcp` section) | `.vscode/mcp.json` |
| Cursor | `~/.cursor/mcp.json` | `.cursor/mcp.json` |

## Usage Examples

Once configured, you can interact with GitHub through your AI assistant:

### Repository Operations
- "Create a new repository called 'my-project' with a basic README"
- "List all my repositories"
- "Show me the structure of the 'gitmcp' repository"

### File Management
- "Read the package.json file from my project"
- "Create a new Python file with a basic Flask app"
- "Search for all TODO comments in my codebase"

### Collaboration
- "Create a pull request for the feature branch"
- "Create a new branch called 'feature/auth-system'"

## Available Tools

### Repository Tools
- `list_repos` - List user repositories
- `create_repo` - Create new repositories
- `delete_repo` - Delete repositories (use with caution)
- `get_repo_structure` - Get directory structure

### File Tools
- `read_file` - Read file contents
- `write_file` - Create or update files
- `edit_file` - Make targeted edits to files
- `batch_update_files` - Update multiple files at once

### Search & Navigation
- `search_code` - Search for code within repositories

### Branch & PR Tools
- `create_branch` - Create new branches
- `create_pull_request` - Create pull requests

## Development

### Building from Source
```bash
git clone https://github.com/[username]/gitmcp.git
cd gitmcp
npm install
npm run build
npm run dev  # For development with auto-reload
```

### Testing
```bash
npm test
```

### Using MCP Inspector
Debug your MCP server with the official inspector:
```bash
npx @modelcontextprotocol/inspector node build/index.js
```

## Security Considerations

- Store your GitHub token securely using environment variables
- Use tokens with minimal required permissions
- Regularly rotate your access tokens
- Review tool permissions before granting access
- Be cautious with destructive operations like `delete_repo`

## Troubleshooting

### Common Issues

1. **"Server not found" error**
   - Verify the command path is correct
   - Ensure the package is installed globally (`npm install -g gitmcp`)

2. **Authentication errors**
   - Check your GitHub token has the required scopes
   - Verify the token is set in the environment variables

3. **Permission denied**
   - Ensure your GitHub token has access to the target repositories
   - Check if the repository exists and you have the required permissions

### Debug Mode
Set environment variable for verbose logging:
```bash
DEBUG=gitmcp node build/index.js
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Related Projects

- [Model Context Protocol](https://modelcontextprotocol.io/) - Official MCP documentation
- [Anthropic Claude](https://claude.ai/) - AI assistant with MCP support
- [MCP Servers](https://github.com/modelcontextprotocol/servers) - Official MCP server implementations

---

Made with ❤️ for the MCP community