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

### Prerequisites
- Python 3.8+ 
- pip (Python package manager)

### Required Python Packages
```bash
pip install fastmcp PyGithub
```

### Option 1: Direct Download
Download the `gitmcp.py` file from this repository and run it directly:
```bash
python gitmcp.py
```

### Option 2: Clone Repository
```bash
git clone https://github.com/ProCreations-Official/gitmcp.git
cd gitmcp
pip install -r requirements.txt  # if available
python gitmcp.py
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

```json
{
  "mcpServers": {
    "gitmcp": {
      "command": "python",
      "args": ["/path/to/gitmcp.py"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here"
      }
    }
  }
}
```

Replace `/path/to/gitmcp.py` with the actual path to where you downloaded or cloned the file.

#### VS Code (with Copilot)

Create `.vscode/mcp.json` in your workspace:
```json
{
  "servers": {
    "gitmcp": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/gitmcp.py"],
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
      "command": "python",
      "args": ["/path/to/gitmcp.py"],
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
- \"Delete the old config file from my repository\"
- \"Remove multiple test files in one commit\"
- \"Create a new 'docs' folder for documentation\"
- \"Delete the entire 'deprecated' folder and all its contents\"
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
- `delete_file` - Delete a single file
- `batch_update_files` - Update multiple files at once
- `delete_files_batch` - Delete multiple files in one commit

### Folder Tools
- `create_folder` - Create new folders (with .gitkeep file)
- `delete_folder` - Delete folders and all their contents

### Search & Navigation
- `search_code` - Search for code within repositories

### Branch & PR Tools
- `create_branch` - Create new branches
- `create_pull_request` - Create pull requests

## Development

### Building from Source
```bash
git clone https://github.com/ProCreations-Official/gitmcp.git
cd gitmcp
pip install fastmcp PyGithub
python gitmcp.py
```

### Testing Your Setup
Test that your MCP server is working by running it directly:
```bash
python gitmcp.py
```

You should see output indicating the FastMCP server has started.

### Using MCP Inspector
Debug your MCP server with the official inspector:
```bash
npx @modelcontextprotocol/inspector python gitmcp.py
```

This will open a web interface where you can test all the available tools interactively.

## Security Considerations

- Store your GitHub token securely using environment variables
- Use tokens with minimal required permissions
- Regularly rotate your access tokens
- Review tool permissions before granting access
- Be cautious with destructive operations like `delete_repo`

## Troubleshooting

### Common Issues

1. **"Server not found" or "Command not found" error**
   - Verify Python is installed and accessible via `python` command
   - Check the full path to `gitmcp.py` is correct in your config
   - Try using the full path to Python: `/usr/bin/python3` or `/usr/local/bin/python`

2. **"No module named 'fastmcp'" or "No module named 'github'"**
   - Install the required packages: `pip install fastmcp PyGithub`
   - If using Python virtual environments, ensure packages are installed in the active environment

3. **Authentication errors**
   - Check your GitHub token has the required scopes (`repo`, `user`)
   - Verify the token is set correctly in the environment variables
   - Test your token works: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user`

4. **Permission denied**
   - Ensure your GitHub token has access to the target repositories
   - Check if the repository exists and you have the required permissions

### Debug Mode
For verbose logging, you can modify the `gitmcp.py` file to add debug output or run with Python's verbose flag:
```bash
python -v gitmcp.py
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