# GitMCP - GitHub MCP Server

A Model Context Protocol (MCP) server that provides comprehensive GitHub integration for AI assistants like Claude, enabling seamless repository management, code browsing, and collaborative workflows.

## 🚀 Enhanced Open Source Contribution Workflows

GitMCP now includes **game-changing improvements** for open source contributions! These new features solve the common problems that make contributing to GitHub projects cumbersome:

### ✨ What's New?

**🎯 GitHub Issues Management (NEW!)**
- Create, update, and close issues with full metadata support
- Add comments and participate in issue discussions
- Manage labels, assignments, and milestones
- Advanced issue search and filtering capabilities

**🔄 Complete Fork-to-PR Workflows**
- `complete_fork_to_pr_workflow` - One function handles everything: fork → branch → changes → PR
- `fork_and_setup_contribution` - Smart forking with automatic branch creation
- `create_cross_repo_pull_request` - Proper fork-to-upstream PR creation

**🤝 Advanced PR Collaboration**
- Submit reviews with approval/change requests
- Add comments and request specific reviewers
- Update PR titles, descriptions, and settings
- Enable auto-merge for streamlined workflows

**🛠️ Intelligent Error Handling**
- Gracefully handles existing forks (no "fork already exists" errors)
- Smart branch creation (works even if branch exists)
- Better permission error messages for 403 scenarios

### 💡 Why This Matters

Before these enhancements, contributing to open source required multiple manual steps and often failed due to permission issues when trying to create branches on repositories you don't own. Now Claude can:

1. **"I want to add dark mode to that Streamlit app"** → Claude forks, creates feature branch, makes changes, and submits PR
2. **"Fix the typo in their README"** → Complete workflow handled automatically  
3. **"Review this PR and approve it"** → Claude can participate in code review process

This makes GitMCP the **most powerful GitHub integration for AI assistants**, enabling true collaborative development workflows!

### 🎯 Complete GitHub Project Management

With the addition of comprehensive Issues management, GitMCP now provides **end-to-end GitHub project collaboration**:

- **Code Contributions**: Fork → Branch → Code → PR → Review → Merge
- **Issue Management**: Create → Discuss → Label → Assign → Track → Close  
- **Project Coordination**: Labels, milestones, assignments, and search across all project artifacts

Claude can now participate in **every aspect** of GitHub project workflows, from initial issue reporting to final code delivery.

## What is MCP?

The Model Context Protocol (MCP) is an open standard developed by Anthropic that enables AI assistants to connect securely with external data sources and tools. Think of it as "USB-C for AI applications" - it provides a standardized way to extend AI capabilities without custom integrations.

## Features

This GitHub MCP server provides the following capabilities:

### 🔧 Tools (AI-controlled actions)

#### Core Repository Management
- **Repository Management**: Create, list, and delete repositories
- **File Operations**: Read, write, edit, delete files and manage directories
- **Folder Management**: Create and delete folders with all contents
- **Branch Management**: Create branches and manage repository structure
- **Code Search**: Search for code across repositories
- **Batch Operations**: Update or delete multiple files in a single commit

#### 🚀 Enhanced Fork & PR Workflows (NEW!)
- **Smart Forking**: `fork_and_setup_contribution` - Fork repo + create feature branch in one step
- **Cross-Repo PRs**: `create_cross_repo_pull_request` - Create PRs from forks to upstream repos
- **Complete Workflow**: `complete_fork_to_pr_workflow` - Ultimate function for full contribution workflow
- **PR Management**: Update PR titles, descriptions, and status
- **PR Collaboration**: Add comments, submit reviews, request reviewers
- **Review Tools**: Submit approvals, request changes, add line-specific comments
- **Auto-merge**: Enable auto-merge for PRs when requirements are met

#### 🎯 GitHub Issues Management (NEW!)
- **Create Issues**: `create_issue` - Create issues with labels, assignees, milestones
- **List Issues**: `list_issues` - Filter by state, labels, assignees, creators
- **Issue Details**: `get_issue_details` - Get complete issue info including comments and events
- **Comment on Issues**: `add_issue_comment` - Add comments to any issue
- **Update Issues**: `update_issue` - Change title, body, state, labels, assignees
- **Close Issues**: `close_issue` - Close issues with optional closing comment
- **Label Management**: `add_issue_labels`, `remove_issue_labels` - Manage issue labels
- **Assignment**: `assign_issue`, `unassign_issue` - Assign/unassign users to issues
- **Label Operations**: `list_repository_labels`, `create_repository_label` - Manage repo labels
- **Search Issues**: `search_repository_issues` - Advanced issue search with filters

#### Traditional Git Operations  
- **Pull Requests**: Create and manage pull requests (enhanced with cross-repo support)
- **Local Git Integration**: Clone repos, sync with remotes, setup local repositories

### 📁 Resources (Context for AI)
- Repository metadata and structure
- File contents and directory trees
- Commit history and branch information
- Pull request details and review status

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
pip install fastmcp PyGithub
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

### 🚀 Enhanced Open Source Contribution Workflows

#### Smart Fork Setup
- \"Fork the 'streamlit-ollama-llm' repository and create a 'feature/enhanced-ui' branch for my contributions\"
- \"Set me up to contribute to 'microsoft/vscode' - fork it and create a 'fix/memory-leak' branch\"

#### Complete Contribution Workflow  
- \"Complete contribution to 'facebook/react': fork it, create 'feature/new-hook' branch, and create a PR with my changes\"
- \"I want to contribute chat history and dark mode to 'romilandc/streamlit-ollama-llm' - handle the entire workflow\"

#### Cross-Repository Pull Requests
- \"Create a PR from my fork 'myusername/awesome-project' feature branch to the upstream 'original/awesome-project' main branch\"
- \"Submit my 'bug-fix' branch from my fork to the original repository as a pull request\"

### 🎯 GitHub Issues Management

#### Creating and Managing Issues
- \"Create a new issue titled 'Add dark mode support' with bug and enhancement labels\"
- \"Create an issue about the memory leak and assign it to 'developer1' and 'developer2'\"
- \"List all open issues labeled 'help wanted' in the react repository\"
- \"Show me details for issue #42 including all comments and activity\"

#### Issue Communication
- \"Add a comment to issue #15 saying 'I can work on this feature'\"
- \"Comment on issue #23 with a proposed solution and timeline\"
- \"Close issue #18 with a comment explaining the fix\"

#### Issue Organization
- \"Add 'priority:high' and 'bug' labels to issue #31\"
- \"Assign issue #27 to 'maintainer1' for review\"
- \"Remove the 'help wanted' label from issue #12 since it's being worked on\"
- \"Search for all issues mentioning 'performance' in the codebase\"

#### Label Management
- \"List all available labels in this repository\"
- \"Create a new 'documentation' label with blue color\"

### Collaboration & PR Management
- \"Add a comment to PR #15 saying the changes look good\"
- \"Submit an approval review for pull request #23 with the comment 'LGTM, great work!'\"
- \"Request 'maintainer1' and 'maintainer2' as reviewers for PR #42\"
- \"Update PR #18 title to 'Fix: Resolve memory leak in data processing'\"
- \"Enable auto-merge for PR #7 using squash method\"

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

### 🚀 Enhanced Fork & PR Tools (NEW!)
- `fork_and_setup_contribution` - Complete fork + branch setup for contributions
- `create_cross_repo_pull_request` - Create PRs from forks to upstream repositories
- `complete_fork_to_pr_workflow` - Ultimate all-in-one contribution workflow
- `update_pull_request` - Update PR title, description, or status
- `add_pull_request_comment` - Add comments to pull requests
- `submit_pull_request_review` - Submit reviews (approve, request changes, comment)
- `request_pull_request_reviewers` - Request specific reviewers for PRs
- `list_pull_request_reviews` - List all reviews for a PR
- `auto_merge_pull_request` - Enable auto-merge when requirements are met

### 🎯 GitHub Issues Tools (NEW!)
- `create_issue` - Create issues with labels, assignees, milestones
- `list_issues` - List issues with filtering by state, labels, assignee, creator
- `get_issue_details` - Get detailed issue information including comments and events
- `add_issue_comment` - Add comments to issues
- `update_issue` - Update issue title, body, state, labels, assignees, milestone
- `close_issue` - Close issues with optional closing comment
- `add_issue_labels` - Add labels to issues
- `remove_issue_labels` - Remove labels from issues
- `assign_issue` - Assign users to issues
- `unassign_issue` - Remove user assignments from issues
- `list_repository_labels` - List all labels in a repository
- `create_repository_label` - Create new labels with custom colors
- `search_repository_issues` - Search issues with advanced filtering

### Traditional Branch & PR Tools
- `create_branch` - Create new branches
- `create_pull_request` - Create pull requests (same-repo)
- `list_pull_requests` - List PRs in a repository
- `get_pull_request_details` - Get detailed PR information
- `merge_pull_request` - Merge pull requests
- `close_pull_request` - Close PRs without merging
- `compare_branches` - Compare differences between branches

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