#!/usr/bin/env python3
"""
GitHub Code Assistant MCP Server
A custom MCP server that lets Claude read, edit, and write to your GitHub repos
"""

import os
import sys
import base64
from typing import Dict, List, Optional, Any
from github import Github, GithubException
from mcp.server.fastmcp import FastMCP
from dataclasses import dataclass

# Initialize the MCP server
mcp = FastMCP("GitHub Code Assistant")

# Global GitHub client (will be initialized with token)
github_client: Optional[Github] = None

@dataclass
class FileChange:
    """Represents a file change to be made"""
    path: str
    content: str
    message: str

def init_github_client() -> Github:
    """Initialize GitHub client with token from environment"""
    global github_client
    if github_client is None:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            print("ERROR: GITHUB_TOKEN environment variable is required", file=sys.stderr)
            raise ValueError("GITHUB_TOKEN environment variable is required")
        try:
            github_client = Github(token)
            # Test the connection
            github_client.get_user()
        except Exception as e:
            print(f"ERROR: Failed to authenticate with GitHub: {e}", file=sys.stderr)
            raise
    return github_client

@mcp.tool()
def list_repos(limit: int = 10) -> List[Dict[str, Any]]:
    """
    List your GitHub repositories (both public and private)
    
    Args:
        limit: Maximum number of repos to return (default: 10)
    
    Returns:
        List of repository info including name, description, language, etc.
    """
    client = init_github_client()
    repos = []
    
    for repo in client.get_user().get_repos()[:limit]:
        repos.append({
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "private": repo.private,
            "url": repo.html_url,
            "clone_url": repo.clone_url,
            "updated_at": repo.updated_at.isoformat() if repo.updated_at else None
        })
    
    return repos

@mcp.tool()
def create_repo(name: str, description: str = "", private: bool = False,
                auto_init: bool = True, readme_content: str = "") -> Dict[str, Any]:
    """
    Create a new GitHub repository
    
    Args:
        name: Repository name
        description: Repository description (optional)
        private: Whether the repo should be private (default: False)
        auto_init: Whether to initialize with a README (default: True)
        readme_content: Custom README content (optional, uses default if empty)
    
    Returns:
        New repository information
    """
    client = init_github_client()
    user = client.get_user()
    
    try:
        # Create the repository
        repo = user.create_repo(
            name=name,
            description=description,
            private=private,
            auto_init=auto_init
        )
        
        # If custom README content is provided, update the README
        if readme_content.strip() and auto_init:
            try:
                # Wait a moment for repo initialization, then update README
                import time
                time.sleep(1)
                
                readme_file = repo.get_contents("README.md")
                repo.update_file(
                    path="README.md",
                    message="Initialize README with custom content",
                    content=readme_content,
                    sha=readme_file.sha
                )
            except Exception as e:
                # If README update fails, that's okay - repo is still created
                pass
        
        return {
            "action": "repository_created",
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "private": repo.private,
            "url": repo.html_url,
            "clone_url": repo.clone_url,
            "ssh_url": repo.ssh_url,
            "created_at": repo.created_at.isoformat()
        }
        
    except GithubException as e:
        return {"error": f"Failed to create repository: {str(e)}"}

@mcp.tool()
def delete_repo(owner: str, repo_name: str, confirm_deletion: bool = True) -> Dict[str, Any]:
    """
    Delete a GitHub repository (DANGEROUS OPERATION)
    
    IMPORTANT: Claude should ALWAYS ask the user for explicit permission before calling this function.
    This operation permanently deletes a repository and cannot be undone.
    
    Args:
        owner: Repository owner (username or organization)
        repo_name: Repository name to delete
        confirm_deletion: Confirmation flag (defaults to True, but Claude should still ask user)
    
    Returns:
        Deletion confirmation or error
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        # Additional safety check - verify user owns the repo or has admin access
        current_user = client.get_user().login
        if repo.owner.login != current_user:
            # Check if user has admin permissions
            try:
                permission = repo.get_collaborator_permission(current_user)
                if permission != "admin":
                    return {
                        "error": "You must be the owner or have admin permissions to delete this repository",
                        "repo_owner": repo.owner.login,
                        "your_username": current_user
                    }
            except:
                return {
                    "error": "You do not have permission to delete this repository",
                    "repo_owner": repo.owner.login,
                    "your_username": current_user
                }
        
        # Store repo info before deletion
        repo_info = {
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "private": repo.private,
            "url": repo.html_url
        }
        
        # Delete the repository
        repo.delete()
        
        return {
            "action": "repository_deleted",
            "deleted_repo": repo_info,
            "warning": "Repository has been permanently deleted and cannot be recovered"
        }
        
    except GithubException as e:
        return {"error": f"Failed to delete repository: {str(e)}"}

@mcp.tool()
def get_repo_structure(owner: str, repo_name: str, path: str = "") -> Dict[str, Any]:
    """
    Get the file/folder structure of a repository
    
    Args:
        owner: Repository owner (username or organization)
        repo_name: Repository name
        path: Path within repo to explore (empty for root)
    
    Returns:
        Directory structure with files and folders
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        contents = repo.get_contents(path)
        if not isinstance(contents, list):
            contents = [contents]
            
        structure = {
            "path": path,
            "items": []
        }
        
        for item in contents:
            structure["items"].append({
                "name": item.name,
                "path": item.path,
                "type": item.type,  # "file" or "dir"
                "size": item.size if item.type == "file" else None,
                "url": item.html_url
            })
            
        return structure
        
    except GithubException as e:
        return {"error": f"Failed to get repo structure: {str(e)}"}

@mcp.tool()
def read_file(owner: str, repo_name: str, file_path: str, branch: str = "main") -> Dict[str, Any]:
    """
    Read the contents of a file from a GitHub repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        file_path: Path to the file in the repository
        branch: Branch to read from (default: main)
    
    Returns:
        File contents and metadata
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        file_content = repo.get_contents(file_path, ref=branch)
        
        # Decode content if it's base64 encoded
        if file_content.encoding == "base64":
            content = base64.b64decode(file_content.content).decode('utf-8')
        else:
            content = file_content.content
            
        return {
            "path": file_content.path,
            "content": content,
            "size": file_content.size,
            "sha": file_content.sha,
            "encoding": file_content.encoding,
            "branch": branch
        }
        
    except GithubException as e:
        return {"error": f"Failed to read file: {str(e)}"}

@mcp.tool()
def edit_file(owner: str, repo_name: str, file_path: str, old_text: str,
              new_text: str, commit_message: str, branch: str = "main") -> Dict[str, Any]:
    """
    Edit a file by replacing specific text content
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        file_path: Path to the file to edit
        old_text: Text to find and replace (must match exactly)
        new_text: Text to replace it with
        commit_message: Commit message for this change
        branch: Branch to edit on (default: main)
    
    Returns:
        Edit result with diff information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Get the current file content
        file_content = repo.get_contents(file_path, ref=branch)
        
        # Decode content if it's base64 encoded
        if file_content.encoding == "base64":
            current_content = base64.b64decode(file_content.content).decode('utf-8')
        else:
            current_content = file_content.content
            
        # Check if the old_text exists in the file
        if old_text not in current_content:
            return {
                "error": f"Text to replace not found in file. Make sure the text matches exactly.",
                "searched_for": old_text
            }
            
        # Count occurrences to warn about multiple matches
        occurrences = current_content.count(old_text)
        if occurrences > 1:
            return {
                "error": f"Found {occurrences} occurrences of the text. Please be more specific to avoid unintended replacements.",
                "searched_for": old_text,
                "occurrences": occurrences
            }
            
        # Make the replacement
        new_content = current_content.replace(old_text, new_text)
        
        # Update the file
        result = repo.update_file(
            path=file_path,
            message=commit_message,
            content=new_content,
            sha=file_content.sha,
            branch=branch
        )
        
        # Create a simple diff view
        lines_before = current_content.split('\n')
        lines_after = new_content.split('\n')
        
        return {
            "action": "file_edited",
            "path": file_path,
            "old_text": old_text,
            "new_text": new_text,
            "commit_sha": result["commit"].sha,
            "commit_message": commit_message,
            "branch": branch,
            "commit_url": result["commit"].html_url,
            "changes": {
                "lines_changed": len(lines_after) - len(lines_before),
                "characters_changed": len(new_content) - len(current_content)
            }
        }
        
    except GithubException as e:
        return {"error": f"Failed to edit file: {str(e)}"}

@mcp.tool()
def write_file(owner: str, repo_name: str, file_path: str, content: str,
               commit_message: str, branch: str = "main") -> Dict[str, Any]:
    """
    Write/update a file in a GitHub repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name  
        file_path: Path where to write the file
        content: File content to write
        commit_message: Commit message for this change
        branch: Branch to write to (default: main)
    
    Returns:
        Commit information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Check if file exists to determine if we're creating or updating
        try:
            existing_file = repo.get_contents(file_path, ref=branch)
            # File exists, update it
            result = repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=existing_file.sha,
                branch=branch
            )
        except GithubException:
            # File doesn't exist, create it
            result = repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch
            )
            
        return {
            "action": "updated" if 'existing_file' in locals() else "created",
            "path": file_path,
            "commit_sha": result["commit"].sha,
            "commit_message": commit_message,
            "branch": branch,
            "commit_url": result["commit"].html_url
        }
        
    except GithubException as e:
        return {"error": f"Failed to write file: {str(e)}"}

@mcp.tool()
def batch_update_files(owner: str, repo_name: str, changes: List[Dict[str, str]],
                      commit_message: str, branch: str = "main") -> Dict[str, Any]:
    """
    Update multiple files in a single commit
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        changes: List of changes, each with 'path' and 'content' keys
        commit_message: Commit message for all changes
        branch: Branch to commit to (default: main)
    
    Returns:
        Batch commit information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Get the latest commit from the branch
        ref = repo.get_git_ref(f"heads/{branch}")
        latest_commit = repo.get_git_commit(ref.object.sha)
        
        # Create blobs for each file
        blobs = []
        for change in changes:
            blob = repo.create_git_blob(change["content"], "utf-8")
            blobs.append({
                "path": change["path"],
                "mode": "100644",  # Regular file
                "type": "blob",
                "sha": blob.sha
            })
        
        # Create tree with all changes
        tree = repo.create_git_tree(blobs, latest_commit.tree)
        
        # Create commit
        commit = repo.create_git_commit(commit_message, tree, [latest_commit])
        
        # Update reference
        ref.edit(commit.sha)
        
        return {
            "action": "batch_updated",
            "files_changed": len(changes),
            "paths": [change["path"] for change in changes],
            "commit_sha": commit.sha,
            "commit_message": commit_message,
            "branch": branch
        }
        
    except GithubException as e:
        return {"error": f"Failed to batch update files: {str(e)}"}

@mcp.tool()
def create_branch(owner: str, repo_name: str, branch_name: str,
                 source_branch: str = "main") -> Dict[str, Any]:
    """
    Create a new branch in the repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        branch_name: Name of the new branch
        source_branch: Branch to create from (default: main)
    
    Returns:
        New branch information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Get source branch reference
        source_ref = repo.get_git_ref(f"heads/{source_branch}")
        
        # Create new branch
        new_ref = repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=source_ref.object.sha
        )
        
        return {
            "action": "branch_created",
            "branch_name": branch_name,
            "source_branch": source_branch,
            "sha": new_ref.object.sha
        }
        
    except GithubException as e:
        return {"error": f"Failed to create branch: {str(e)}"}

@mcp.tool()
def search_code(owner: str, repo_name: str, query: str,
               file_extension: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for code within a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        query: Search query (code to find)
        file_extension: Optional file extension filter (e.g., "py", "js")
    
    Returns:
        Search results with file matches
    """
    client = init_github_client()
    
    try:
        # Build search query
        search_query = f"{query} repo:{owner}/{repo_name}"
        if file_extension:
            search_query += f" extension:{file_extension}"
            
        results = client.search_code(search_query)
        
        matches = []
        for item in results[:20]:  # Limit to 20 results
            matches.append({
                "file_path": item.path,
                "file_url": item.html_url,
                "score": item.score,
                "repository": item.repository.full_name
            })
            
        return {
            "query": query,
            "total_count": results.totalCount,
            "matches": matches
        }
        
    except GithubException as e:
        return {"error": f"Failed to search code: {str(e)}"}

@mcp.tool()
def create_pull_request(owner: str, repo_name: str, title: str, body: str,
                       head_branch: str, base_branch: str = "main") -> Dict[str, Any]:
    """
    Create a pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        title: Pull request title
        body: Pull request description
        head_branch: Branch with your changes
        base_branch: Branch to merge into (default: main)
    
    Returns:
        Pull request information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch
        )
        
        return {
            "action": "pull_request_created",
            "pr_number": pr.number,
            "title": pr.title,
            "url": pr.html_url,
            "head_branch": head_branch,
            "base_branch": base_branch
        }
        
    except GithubException as e:
        return {"error": f"Failed to create pull request: {str(e)}"}

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
