#!/usr/bin/env python3
"""
GitHub Code Assistant MCP Server - Streamlined Version
A compact MCP server for GitHub operations with local clone/edit/PR workflow
"""

import os
import sys
import base64
import json
import subprocess
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from github import Github, GithubException
from mcp.server.fastmcp import FastMCP
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP(
    "GitHub Code Assistant",
    description="Streamlined GitHub integration with local workflow support"
)

# Global GitHub client
github_client: Optional[Github] = None

def init_github_client(token: Optional[str] = None) -> Github:
    """Initialize GitHub client with token"""
    global github_client
    if github_client is None or token is not None:
        auth_token = token or os.getenv("GITHUB_TOKEN")
        if not auth_token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        try:
            github_client = Github(auth_token)
            github_client.get_user()  # Test connection
            logger.info("GitHub client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to authenticate with GitHub: {e}")
            raise
    return github_client

@mcp.tool()
def repo_operations(action: str, owner: str = None, repo_name: str = None, 
                   name: str = None, description: str = "", private: bool = False,
                   limit: int = 10) -> Dict[str, Any]:
    """
    Combined repository operations: list, create, delete
    
    Args:
        action: "list", "create", or "delete"
        owner: Repository owner (for create/delete)
        repo_name: Repository name (for create/delete)
        name: New repository name (for create)
        description: Repository description (for create)
        private: Whether repo should be private (for create)
        limit: Max repos to return (for list)
    """
    client = init_github_client()
    
    if action == "list":
        repos = []
        for repo in client.get_user().get_repos()[:limit]:
            repos.append({
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "language": repo.language,
                "private": repo.private,
                "url": repo.html_url,
                "clone_url": repo.clone_url
            })
        return {"repos": repos}
    
    elif action == "create":
        if not name:
            return {"error": "Repository name is required for create action"}
        try:
            repo = client.get_user().create_repo(
                name=name,
                description=description,
                private=private,
                auto_init=True
            )
            return {
                "action": "repository_created",
                "name": repo.name,
                "full_name": repo.full_name,
                "url": repo.html_url,
                "clone_url": repo.clone_url
            }
        except GithubException as e:
            return {"error": f"Failed to create repository: {str(e)}"}
    
    elif action == "delete":
        if not owner or not repo_name:
            return {"error": "Owner and repo_name required for delete action"}
        try:
            repo = client.get_repo(f"{owner}/{repo_name}")
            repo.delete()
            return {
                "action": "repository_deleted",
                "repo": f"{owner}/{repo_name}",
                "warning": "Repository permanently deleted"
            }
        except GithubException as e:
            return {"error": f"Failed to delete repository: {str(e)}"}
    
    return {"error": f"Unknown action: {action}"}

@mcp.tool()
def file_operations(action: str, owner: str, repo_name: str, path: str,
                   content: str = None, old_text: str = None, new_text: str = None,
                   commit_message: str = None, branch: str = "main") -> Dict[str, Any]:
    """
    Combined file operations: read, write, edit, delete
    
    Args:
        action: "read", "write", "edit", or "delete"
        owner: Repository owner
        repo_name: Repository name
        path: File path
        content: File content (for write)
        old_text: Text to replace (for edit)
        new_text: Replacement text (for edit)
        commit_message: Commit message
        branch: Branch name
    """
    if not path:
        return {"error": "Path parameter is required"}
        
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        if action == "read":
            file_content = repo.get_contents(path, ref=branch)
            if file_content.encoding == "base64":
                content = base64.b64decode(file_content.content).decode('utf-8')
            else:
                content = file_content.content
            return {
                "path": file_content.path,
                "content": content,
                "size": file_content.size,
                "branch": branch
            }
        
        elif action == "write":
            if content is None:
                return {"error": "Content is required for write action"}
            if not commit_message:
                commit_message = f"Update {path}"
            
            try:
                existing_file = repo.get_contents(path, ref=branch)
                result = repo.update_file(path, commit_message, content, existing_file.sha, branch)
                action_type = "updated"
            except GithubException:
                result = repo.create_file(path, commit_message, content, branch)
                action_type = "created"
            
            return {
                "action": f"file_{action_type}",
                "path": path,
                "commit_sha": result["commit"].sha,
                "commit_url": result["commit"].html_url
            }
        
        elif action == "edit":
            if not old_text or new_text is None:
                return {"error": "Both old_text and new_text are required for edit action"}
            if not commit_message:
                commit_message = f"Edit {path}"
            
            file_content = repo.get_contents(path, ref=branch)
            if file_content.encoding == "base64":
                current_content = base64.b64decode(file_content.content).decode('utf-8')
            else:
                current_content = file_content.content
            
            if old_text not in current_content:
                return {"error": "Text to replace not found in file"}
            
            new_content = current_content.replace(old_text, new_text)
            result = repo.update_file(path, commit_message, new_content, file_content.sha, branch)
            
            return {
                "action": "file_edited",
                "path": path,
                "commit_sha": result["commit"].sha,
                "commit_url": result["commit"].html_url
            }
        
        elif action == "delete":
            if not commit_message:
                commit_message = f"Delete {path}"
            
            file_content = repo.get_contents(path, ref=branch)
            result = repo.delete_file(path, commit_message, file_content.sha, branch)
            
            return {
                "action": "file_deleted",
                "path": path,
                "commit_sha": result["commit"].sha,
                "commit_url": result["commit"].html_url
            }
        
        return {"error": f"Unknown action: {action}"}
        
    except GithubException as e:
        return {"error": f"Failed to {action} file: {str(e)}"}

@mcp.tool()
def branch_operations(action: str, owner: str, repo_name: str, branch_name: str = None,
                     source_branch: str = "main") -> Dict[str, Any]:
    """
    Combined branch operations: create, list, delete
    
    Args:
        action: "create", "list", or "delete"
        owner: Repository owner
        repo_name: Repository name
        branch_name: Branch name (for create/delete)
        source_branch: Source branch for new branch (for create)
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        if action == "list":
            branches = []
            for branch in repo.get_branches():
                branches.append({
                    "name": branch.name,
                    "protected": branch.protected,
                    "commit_sha": branch.commit.sha
                })
            return {"branches": branches}
        
        elif action == "create":
            if not branch_name:
                return {"error": "Branch name is required for create action"}
            
            source_ref = repo.get_git_ref(f"heads/{source_branch}")
            new_ref = repo.create_git_ref(f"refs/heads/{branch_name}", source_ref.object.sha)
            
            return {
                "action": "branch_created",
                "branch_name": branch_name,
                "source_branch": source_branch,
                "sha": new_ref.object.sha
            }
        
        elif action == "delete":
            if not branch_name:
                return {"error": "Branch name is required for delete action"}
            
            ref = repo.get_git_ref(f"heads/{branch_name}")
            ref.delete()
            
            return {
                "action": "branch_deleted",
                "branch_name": branch_name
            }
        
        return {"error": f"Unknown action: {action}"}
        
    except GithubException as e:
        return {"error": f"Failed to {action} branch: {str(e)}"}

@mcp.tool()
def search_code(owner: str, repo_name: str, query: str, file_extension: str = None) -> Dict[str, Any]:
    """
    Search for code within a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        query: Search query
        file_extension: File extension filter (optional)
    """
    client = init_github_client()
    
    try:
        search_query = f"{query} repo:{owner}/{repo_name}"
        if file_extension:
            search_query += f" extension:{file_extension}"
        
        results = client.search_code(search_query)
        matches = []
        for item in results[:20]:
            matches.append({
                "file_path": item.path,
                "file_url": item.html_url,
                "score": item.score
            })
        
        return {
            "query": query,
            "total_count": results.totalCount,
            "matches": matches
        }
        
    except GithubException as e:
        return {"error": f"Failed to search code: {str(e)}"}

@mcp.tool()
def get_repo_info(owner: str, repo_name: str, path: str = "") -> Dict[str, Any]:
    """
    Get repository structure and information
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        path: Path to explore (empty for root)
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        contents = repo.get_contents(path)
        if not isinstance(contents, list):
            contents = [contents]
        
        items = []
        for item in contents:
            items.append({
                "name": item.name,
                "path": item.path,
                "type": item.type,
                "size": item.size if item.type == "file" else None,
                "url": item.html_url
            })
        
        return {
            "repo": f"{owner}/{repo_name}",
            "path": path,
            "items": items
        }
        
    except GithubException as e:
        return {"error": f"Failed to get repo info: {str(e)}"}

@mcp.tool()
def pull_request_operations(action: str, owner: str, repo_name: str, title: str = None,
                           body: str = None, head_branch: str = None, base_branch: str = "main",
                           pr_number: int = None) -> Dict[str, Any]:
    """
    Combined pull request operations: create, list, close
    
    Args:
        action: "create", "list", or "close"
        owner: Repository owner
        repo_name: Repository name
        title: PR title (for create)
        body: PR description (for create)
        head_branch: Source branch (for create)
        base_branch: Target branch (for create)
        pr_number: PR number (for close)
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        if action == "create":
            if not all([title, head_branch]):
                return {"error": "Title and head_branch are required for create action"}
            
            pr = repo.create_pull(title=title, body=body or "", head=head_branch, base=base_branch)
            return {
                "action": "pull_request_created",
                "pr_number": pr.number,
                "title": pr.title,
                "url": pr.html_url,
                "head_branch": head_branch,
                "base_branch": base_branch
            }
        
        elif action == "list":
            prs = []
            for pr in repo.get_pulls(state='open')[:10]:
                prs.append({
                    "number": pr.number,
                    "title": pr.title,
                    "url": pr.html_url,
                    "head_branch": pr.head.ref,
                    "base_branch": pr.base.ref,
                    "state": pr.state
                })
            return {"pull_requests": prs}
        
        elif action == "close":
            if not pr_number:
                return {"error": "PR number is required for close action"}
            
            pr = repo.get_pull(pr_number)
            pr.edit(state='closed')
            return {
                "action": "pull_request_closed",
                "pr_number": pr_number,
                "title": pr.title
            }
        
        return {"error": f"Unknown action: {action}"}
        
    except GithubException as e:
        return {"error": f"Failed to {action} pull request: {str(e)}"}

@mcp.tool()
def clone_edit_pr_workflow(owner: str, repo_name: str, branch_name: str, 
                          file_changes: List[Dict[str, str]], pr_title: str,
                          pr_body: str = "", base_branch: str = "main") -> Dict[str, Any]:
    """
    Complete workflow: Clone repo locally, make changes, create PR
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        branch_name: New branch name for changes
        file_changes: List of dicts with 'path', 'content' or 'old_text'/'new_text'
        pr_title: Pull request title
        pr_body: Pull request description
        base_branch: Base branch to merge into
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    repo_dir = os.path.join(temp_dir, repo_name)
    
    try:
        # Clone repository
        clone_url = repo.clone_url.replace('https://', f'https://{os.getenv("GITHUB_TOKEN")}@')
        result = subprocess.run(['git', 'clone', clone_url, repo_dir], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"error": f"Failed to clone repository: {result.stderr}"}
        
        # Change to repo directory
        os.chdir(repo_dir)
        
        # Create and checkout new branch
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
        
        # Apply file changes
        changes_applied = []
        for change in file_changes:
            file_path = change['path']
            
            if 'content' in change:
                # Write new content
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(change['content'])
                changes_applied.append(f"Updated {file_path}")
                
            elif 'old_text' in change and 'new_text' in change:
                # Edit existing file
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if change['old_text'] in content:
                        new_content = content.replace(change['old_text'], change['new_text'])
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        changes_applied.append(f"Edited {file_path}")
                    else:
                        changes_applied.append(f"Warning: Text not found in {file_path}")
                else:
                    changes_applied.append(f"Warning: File {file_path} not found")
        
        # Stage all changes
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Commit changes
        commit_message = f"Automated changes for PR: {pr_title}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        
        # Push to remote
        subprocess.run(['git', 'push', 'origin', branch_name], check=True)
        
        # Create pull request
        pr = repo.create_pull(title=pr_title, body=pr_body, head=branch_name, base=base_branch)
        
        return {
            "action": "clone_edit_pr_completed",
            "branch_name": branch_name,
            "changes_applied": changes_applied,
            "pr_number": pr.number,
            "pr_url": pr.html_url,
            "commit_message": commit_message
        }
        
    except Exception as e:
        return {"error": f"Workflow failed: {str(e)}"}
    
    finally:
        # Cleanup
        os.chdir('/')
        shutil.rmtree(temp_dir, ignore_errors=True)

@mcp.tool()
def batch_file_operations(owner: str, repo_name: str, operations: List[Dict[str, Any]],
                         commit_message: str, branch: str = "main") -> Dict[str, Any]:
    """
    Perform multiple file operations in a single commit
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        operations: List of operations, each with 'action', 'path', and other params
        commit_message: Single commit message for all changes
        branch: Branch to commit to
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Get latest commit
        ref = repo.get_git_ref(f"heads/{branch}")
        latest_commit = repo.get_git_commit(ref.object.sha)
        
        # Process operations and create blobs
        tree_elements = []
        changes_made = []
        
        # Get current tree to preserve existing files
        def get_all_files(path=""):
            try:
                contents = repo.get_contents(path, ref=branch)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for content in contents:
                    if content.type == "dir":
                        get_all_files(content.path)
                    else:
                        # Check if this file will be modified by operations
                        will_modify = any(op.get('path') == content.path for op in operations)
                        if not will_modify:
                            tree_elements.append({
                                "path": content.path,
                                "mode": "100644",
                                "type": "blob",
                                "sha": content.sha
                            })
            except:
                pass
        
        get_all_files()
        
        # Process each operation
        for op in operations:
            action = op.get('action')
            path = op.get('path')
            
            if action == 'write' or action == 'create':
                content = op.get('content', '')
                blob = repo.create_git_blob(content, "utf-8")
                tree_elements.append({
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob.sha
                })
                changes_made.append(f"Write {path}")
                
            elif action == 'edit':
                # Get current content and edit it
                try:
                    file_content = repo.get_contents(path, ref=branch)
                    if file_content.encoding == "base64":
                        current_content = base64.b64decode(file_content.content).decode('utf-8')
                    else:
                        current_content = file_content.content
                    
                    old_text = op.get('old_text', '')
                    new_text = op.get('new_text', '')
                    
                    if old_text in current_content:
                        new_content = current_content.replace(old_text, new_text)
                        blob = repo.create_git_blob(new_content, "utf-8")
                        tree_elements.append({
                            "path": path,
                            "mode": "100644",
                            "type": "blob",
                            "sha": blob.sha
                        })
                        changes_made.append(f"Edit {path}")
                    else:
                        changes_made.append(f"Warning: Text not found in {path}")
                except:
                    changes_made.append(f"Error: Could not edit {path}")
            
            # Note: delete operation is handled by not including the file in tree_elements
            elif action == 'delete':
                changes_made.append(f"Delete {path}")
        
        # Create tree and commit
        tree = repo.create_git_tree(tree_elements)
        commit = repo.create_git_commit(commit_message, tree, [latest_commit])
        ref.edit(commit.sha)
        
        return {
            "action": "batch_operations_completed",
            "operations_count": len(operations),
            "changes_made": changes_made,
            "commit_sha": commit.sha,
            "commit_message": commit_message,
            "branch": branch
        }
        
    except Exception as e:
        return {"error": f"Batch operations failed: {str(e)}"}

@mcp.tool()
def health_check() -> Dict[str, Any]:
    """Server health check and status"""
    try:
        github_healthy = False
        github_user = None
        
        if os.getenv("GITHUB_TOKEN"):
            try:
                client = init_github_client()
                user = client.get_user()
                github_healthy = True
                github_user = user.login
            except:
                pass
        
        return {
            "status": "healthy",
            "github_connection": {
                "healthy": github_healthy,
                "authenticated_user": github_user
            },
            "available_commands": [
                "repo_operations", "file_operations", "branch_operations",
                "search_code", "get_repo_info", "pull_request_operations", 
                "clone_edit_pr_workflow", "batch_file_operations", 
                "health_check"
            ]
        }
        
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    logger.info("Starting streamlined GitHub MCP server")
    try:
        mcp.run()
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)
