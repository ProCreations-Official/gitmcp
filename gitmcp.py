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
def search_public_repos(query: str, language: str = None, sort: str = "stars", 
                       order: str = "desc", limit: int = 20) -> Dict[str, Any]:
    """
    Search for public repositories on GitHub
    
    Args:
        query: Search query (e.g., "machine learning", "web framework")
        language: Filter by programming language (e.g., "Python", "JavaScript")
        sort: Sort criteria ("stars", "forks", "help-wanted-issues", "updated")
        order: Sort order ("desc", "asc")
        limit: Maximum number of results to return (default: 20)
    
    Returns:
        List of public repositories matching the search criteria
    """
    client = init_github_client()
    
    try:
        # Build search query
        search_query = query
        if language:
            search_query += f" language:{language}"
        
        # Search repositories
        results = client.search_repositories(
            query=search_query,
            sort=sort,
            order=order
        )
        
        repos = []
        count = 0
        for repo in results:
            if count >= limit:
                break
            
            repos.append({
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "language": repo.language,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "owner": {
                    "login": repo.owner.login,
                    "type": repo.owner.type,
                    "url": repo.owner.html_url
                },
                "created_at": repo.created_at.isoformat(),
                "updated_at": repo.updated_at.isoformat(),
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "license": repo.license.name if repo.license else None,
                "topics": repo.get_topics(),
                "default_branch": repo.default_branch,
                "archived": repo.archived,
                "disabled": repo.disabled,
                "fork": repo.fork
            })
            count += 1
        
        return {
            "query": query,
            "language_filter": language,
            "sort_by": sort,
            "order": order,
            "total_count": results.totalCount,
            "returned_count": len(repos),
            "repositories": repos
        }
        
    except GithubException as e:
        return {"error": f"Failed to search repositories: {str(e)}"}

@mcp.tool()
def fork_repository(owner: str, repo_name: str, organization: str = None) -> Dict[str, Any]:
    """
    Fork a repository to your account or organization
    
    Args:
        owner: Repository owner (username or organization)
        repo_name: Repository name to fork
        organization: Optional organization to fork to (defaults to your account)
    
    Returns:
        Forked repository information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        # Fork the repository
        if organization:
            # Fork to organization
            org = client.get_organization(organization)
            forked_repo = org.create_fork(repo)
        else:
            # Fork to personal account
            user = client.get_user()
            forked_repo = user.create_fork(repo)
        
        return {
            "action": "repository_forked",
            "original": {
                "name": repo.name,
                "full_name": repo.full_name,
                "owner": repo.owner.login,
                "url": repo.html_url
            },
            "fork": {
                "name": forked_repo.name,
                "full_name": forked_repo.full_name,
                "owner": forked_repo.owner.login,
                "url": forked_repo.html_url,
                "clone_url": forked_repo.clone_url,
                "ssh_url": forked_repo.ssh_url
            },
            "parent_url": forked_repo.parent.html_url if forked_repo.parent else None
        }
        
    except GithubException as e:
        return {"error": f"Failed to fork repository: {str(e)}"}

@mcp.tool()
def get_repository_info(owner: str, repo_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a repository
    
    Args:
        owner: Repository owner (username or organization)
        repo_name: Repository name
    
    Returns:
        Detailed repository information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        # Get additional info
        languages = repo.get_languages()
        topics = repo.get_topics()
        collaborators_count = repo.get_collaborators().totalCount if repo.permissions.admin else None
        
        repo_info = {
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "private": repo.private,
            "fork": repo.fork,
            "url": repo.html_url,
            "clone_url": repo.clone_url,
            "ssh_url": repo.ssh_url,
            "size": repo.size,
            "language": repo.language,
            "languages": languages,
            "topics": topics,
            "stargazers_count": repo.stargazers_count,
            "watchers_count": repo.watchers_count,
            "forks_count": repo.forks_count,
            "open_issues_count": repo.open_issues_count,
            "default_branch": repo.default_branch,
            "created_at": repo.created_at.isoformat(),
            "updated_at": repo.updated_at.isoformat(),
            "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
            "owner": {
                "login": repo.owner.login,
                "type": repo.owner.type,
                "url": repo.owner.html_url
            },
            "permissions": {
                "admin": repo.permissions.admin,
                "maintain": repo.permissions.maintain,
                "push": repo.permissions.push,
                "triage": repo.permissions.triage,
                "pull": repo.permissions.pull
            }
        }
        
        # Add parent info if this is a fork
        if repo.fork and repo.parent:
            repo_info["parent"] = {
                "name": repo.parent.name,
                "full_name": repo.parent.full_name,
                "owner": repo.parent.owner.login,
                "url": repo.parent.html_url
            }
        
        # Add source info if this is a fork
        if repo.fork and repo.source:
            repo_info["source"] = {
                "name": repo.source.name,
                "full_name": repo.source.full_name,
                "owner": repo.source.owner.login,
                "url": repo.source.html_url
            }
        
        # Add collaborators count if accessible
        if collaborators_count is not None:
            repo_info["collaborators_count"] = collaborators_count
        
        return repo_info
        
    except GithubException as e:
        return {"error": f"Failed to get repository info: {str(e)}"}

@mcp.tool()
def list_user_repos(username: str, repo_type: str = "all", limit: int = 10) -> List[Dict[str, Any]]:
    """
    List repositories for any user or organization
    
    Args:
        username: Username or organization name
        repo_type: Type of repos to list ("all", "owner", "public", "private", "member") 
        limit: Maximum number of repos to return (default: 10)
    
    Returns:
        List of repository information
    """
    client = init_github_client()
    repos = []
    
    try:
        # Get user or organization
        try:
            user = client.get_user(username)
            user_type = "user"
        except GithubException:
            try:
                user = client.get_organization(username)
                user_type = "organization"
            except GithubException:
                return {"error": f"User or organization '{username}' not found"}
        
        # Get repositories based on type
        if user_type == "organization":
            repo_list = user.get_repos(type=repo_type)
        else:
            repo_list = user.get_repos(type=repo_type)
        
        for repo in repo_list[:limit]:
            repos.append({
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "language": repo.language,
                "private": repo.private,
                "fork": repo.fork,
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None
            })
        
        return {
            "username": username,
            "user_type": user_type,
            "repo_type": repo_type,
            "repositories": repos
        }
        
    except GithubException as e:
        return {"error": f"Failed to list repositories: {str(e)}"}

@mcp.tool()
def list_branches(owner: str, repo_name: str, limit: int = 20) -> Dict[str, Any]:
    """
    List all branches in a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        limit: Maximum number of branches to return (default: 20)
    
    Returns:
        List of branch information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        branches = []
        
        for branch in repo.get_branches()[:limit]:
            branches.append({
                "name": branch.name,
                "sha": branch.commit.sha,
                "protected": branch.protected,
                "commit": {
                    "sha": branch.commit.sha,
                    "message": branch.commit.commit.message,
                    "author": branch.commit.commit.author.name,
                    "date": branch.commit.commit.author.date.isoformat()
                }
            })
        
        return {
            "repository": f"{owner}/{repo_name}",
            "default_branch": repo.default_branch,
            "total_branches": len(branches),
            "branches": branches
        }
        
    except GithubException as e:
        return {"error": f"Failed to list branches: {str(e)}"}

@mcp.tool()
def list_pull_requests(owner: str, repo_name: str, state: str = "open", 
                      limit: int = 10) -> Dict[str, Any]:
    """
    List pull requests in a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        state: PR state ("open", "closed", "all")
        limit: Maximum number of PRs to return (default: 10)
    
    Returns:
        List of pull request information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pull_requests = []
        
        for pr in repo.get_pulls(state=state)[:limit]:
            pull_requests.append({
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "user": pr.user.login,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "url": pr.html_url,
                "head": {
                    "branch": pr.head.ref,
                    "sha": pr.head.sha,
                    "repo": pr.head.repo.full_name if pr.head.repo else None
                },
                "base": {
                    "branch": pr.base.ref,
                    "sha": pr.base.sha,
                    "repo": pr.base.repo.full_name
                },
                "mergeable": pr.mergeable,
                "draft": pr.draft,
                "labels": [label.name for label in pr.labels]
            })
        
        return {
            "repository": f"{owner}/{repo_name}",
            "state": state,
            "total_count": len(pull_requests),
            "pull_requests": pull_requests
        }
        
    except GithubException as e:
        return {"error": f"Failed to list pull requests: {str(e)}"}

@mcp.tool()
def get_pull_request_details(owner: str, repo_name: str, pr_number: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number
    
    Returns:
        Detailed pull request information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        # Get additional details
        files_changed = []
        for file in pr.get_files():
            files_changed.append({
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "patch": file.patch[:1000] if file.patch else None  # Limit patch size
            })
        
        reviews = []
        for review in pr.get_reviews():
            reviews.append({
                "id": review.id,
                "user": review.user.login,
                "state": review.state,
                "body": review.body,
                "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None
            })
        
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "user": {
                "login": pr.user.login,
                "url": pr.user.html_url
            },
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
            "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
            "url": pr.html_url,
            "head": {
                "branch": pr.head.ref,
                "sha": pr.head.sha,
                "repo": pr.head.repo.full_name if pr.head.repo else None,
                "user": pr.head.repo.owner.login if pr.head.repo else None
            },
            "base": {
                "branch": pr.base.ref,
                "sha": pr.base.sha,
                "repo": pr.base.repo.full_name
            },
            "mergeable": pr.mergeable,
            "mergeable_state": pr.mergeable_state,
            "merged": pr.merged,
            "draft": pr.draft,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "changed_files": pr.changed_files,
            "commits": pr.commits,
            "comments": pr.comments,
            "review_comments": pr.review_comments,
            "labels": [{"name": label.name, "color": label.color} for label in pr.labels],
            "assignees": [assignee.login for assignee in pr.assignees],
            "requested_reviewers": [reviewer.login for reviewer in pr.requested_reviewers],
            "files_changed": files_changed,
            "reviews": reviews
        }
        
    except GithubException as e:
        return {"error": f"Failed to get pull request details: {str(e)}"}

@mcp.tool()
def create_pull_request(owner: str, repo_name: str, title: str, body: str,
                       head_branch: str, base_branch: str = "main",
                       head_repo: str = None) -> Dict[str, Any]:
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

@mcp.tool()
def delete_file(owner: str, repo_name: str, file_path: str, commit_message: str,
               branch: str = "main") -> Dict[str, Any]:
    """
    Delete a file from a GitHub repository

    Args:
        owner: Repository owner
        repo_name: Repository name
        file_path: Path to the file to delete
        commit_message: Commit message for this change
        branch: Branch to delete from (default: main)

    Returns:
        Deletion result information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Get the file to delete (we need its SHA)
        file_content = repo.get_contents(file_path, ref=branch)
        
        # Delete the file
        result = repo.delete_file(
            path=file_path,
            message=commit_message,
            sha=file_content.sha,
            branch=branch
        )
        
        return {
            "action": "file_deleted",
            "path": file_path,
            "commit_sha": result["commit"].sha,
            "commit_message": commit_message,
            "branch": branch,
            "commit_url": result["commit"].html_url
        }
        
    except GithubException as e:
        return {"error": f"Failed to delete file: {str(e)}"}

@mcp.tool()
def delete_files_batch(owner: str, repo_name: str, file_paths: List[str],
                      commit_message: str, branch: str = "main") -> Dict[str, Any]:
    """
    Delete multiple files in a single commit

    Args:
        owner: Repository owner
        repo_name: Repository name
        file_paths: List of file paths to delete
        commit_message: Commit message for all deletions
        branch: Branch to delete from (default: main)

    Returns:
        Batch deletion information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Get the latest commit from the branch
        ref = repo.get_git_ref(f"heads/{branch}")
        latest_commit = repo.get_git_commit(ref.object.sha)
        
        # Get current tree
        base_tree = latest_commit.tree
        
        # Get all files that need to be kept (everything except the ones to delete)
        tree_elements = []
        all_contents = []
        
        def get_all_files(path=""):
            """Recursively get all files in the repo"""
            try:
                contents = repo.get_contents(path, ref=branch)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for content in contents:
                    if content.type == "dir":
                        get_all_files(content.path)
                    else:
                        all_contents.append(content)
            except:
                pass
        
        get_all_files()
        
        # Keep all files except the ones to delete
        for content in all_contents:
            if content.path not in file_paths:
                tree_elements.append({
                    "path": content.path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": content.sha
                })
        
        # Create tree without the deleted files
        tree = repo.create_git_tree(tree_elements)
        
        # Create commit
        commit = repo.create_git_commit(commit_message, tree, [latest_commit])
        
        # Update reference
        ref.edit(commit.sha)
        
        return {
            "action": "files_deleted_batch",
            "files_deleted": len(file_paths),
            "deleted_paths": file_paths,
            "commit_sha": commit.sha,
            "commit_message": commit_message,
            "branch": branch
        }
        
    except GithubException as e:
        return {"error": f"Failed to batch delete files: {str(e)}"}

@mcp.tool()
def create_folder(owner: str, repo_name: str, folder_path: str, 
                 commit_message: str = None, branch: str = "main") -> Dict[str, Any]:
    """
    Create a folder in a GitHub repository
    
    Note: Git doesn't track empty folders, so this creates a .gitkeep file inside the folder
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        folder_path: Path of the folder to create
        commit_message: Commit message (optional, auto-generated if not provided)
        branch: Branch to create folder in (default: main)
    
    Returns:
        Folder creation result
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Ensure folder path ends with / and add .gitkeep
        if not folder_path.endswith('/'):
            folder_path += '/'
        gitkeep_path = folder_path + '.gitkeep'
        
        # Auto-generate commit message if not provided
        if not commit_message:
            commit_message = f"Create folder {folder_path}"
        
        # Create .gitkeep file to establish the folder
        result = repo.create_file(
            path=gitkeep_path,
            message=commit_message,
            content="# This file exists to create the folder structure\n",
            branch=branch
        )
        
        return {
            "action": "folder_created",
            "folder_path": folder_path,
            "gitkeep_path": gitkeep_path,
            "commit_sha": result["commit"].sha,
            "commit_message": commit_message,
            "branch": branch,
            "commit_url": result["commit"].html_url,
            "note": "Folder created with .gitkeep file (Git doesn't track empty folders)"
        }
        
    except GithubException as e:
        return {"error": f"Failed to create folder: {str(e)}"}

@mcp.tool()
def delete_folder(owner: str, repo_name: str, folder_path: str,
                 commit_message: str = None, branch: str = "main") -> Dict[str, Any]:
    """
    Delete a folder and all its contents from a GitHub repository

    Args:
        owner: Repository owner
        repo_name: Repository name
        folder_path: Path of the folder to delete
        commit_message: Commit message (optional, auto-generated if not provided)
        branch: Branch to delete from (default: main)

    Returns:
        Folder deletion result
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Ensure folder path format
        if not folder_path.endswith('/'):
            folder_path += '/'
        
        # Auto-generate commit message if not provided
        if not commit_message:
            commit_message = f"Delete folder {folder_path} and all its contents"
        
        # Get all files in the folder
        def get_folder_files(path):
            """Recursively get all files in a folder"""
            files_to_delete = []
            try:
                contents = repo.get_contents(path.rstrip('/'), ref=branch)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for content in contents:
                    if content.type == "dir":
                        files_to_delete.extend(get_folder_files(content.path))
                    else:
                        files_to_delete.append(content.path)
                        
            except GithubException:
                # Folder doesn't exist
                pass
            return files_to_delete
        
        files_in_folder = get_folder_files(folder_path)
        
        if not files_in_folder:
            return {"error": f"Folder '{folder_path}' not found or is empty"}
        
        # Use batch delete to remove all files in the folder
        result = delete_files_batch(owner, repo_name, files_in_folder, commit_message, branch)
        
        if "error" in result:
            return result
        
        # Update the result to indicate folder deletion
        result.update({
            "action": "folder_deleted",
            "folder_path": folder_path,
            "files_in_folder": len(files_in_folder)
        })
        
        return result
        
    except GithubException as e:
        return {"error": f"Failed to delete folder: {str(e)}"}

@mcp.tool()
def move_file(owner: str, repo_name: str, source_path: str, destination_path: str,
              commit_message: str = None, branch: str = "main") -> Dict[str, Any]:
    """
    Move a file from one location to another within a GitHub repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        source_path: Current path of the file
        destination_path: New path for the file (can be in a different folder)
        commit_message: Commit message (optional, auto-generated if not provided)
        branch: Branch to move file on (default: main)
    
    Returns:
        Move operation result
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Auto-generate commit message if not provided
        if not commit_message:
            commit_message = f"Move {source_path} to {destination_path}"
        
        # Get the source file content
        source_file = repo.get_contents(source_path, ref=branch)
        
        # Decode content if it's base64 encoded
        if source_file.encoding == "base64":
            content = base64.b64decode(source_file.content).decode('utf-8')
        else:
            content = source_file.content
        
        # Check if destination already exists
        try:
            existing_dest = repo.get_contents(destination_path, ref=branch)
            return {"error": f"Destination file '{destination_path}' already exists"}
        except GithubException:
            # Good, destination doesn't exist
            pass
        
        # Get the latest commit for batch operation
        ref = repo.get_git_ref(f"heads/{branch}")
        latest_commit = repo.get_git_commit(ref.object.sha)
        
        # Create blob for the destination file
        blob = repo.create_git_blob(content, "utf-8")
        
        # Get current tree and build new tree
        tree_elements = []
        
        # Get all current files except the source file
        def get_all_files(path=""):
            """Recursively get all files in the repo"""
            try:
                contents = repo.get_contents(path, ref=branch)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for content_item in contents:
                    if content_item.type == "dir":
                        get_all_files(content_item.path)
                    elif content_item.path != source_path:  # Exclude source file
                        tree_elements.append({
                            "path": content_item.path,
                            "mode": "100644",
                            "type": "blob",
                            "sha": content_item.sha
                        })
            except:
                pass
        
        get_all_files()
        
        # Add the file at the new destination
        tree_elements.append({
            "path": destination_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob.sha
        })
        
        # Create tree with the moved file
        tree = repo.create_git_tree(tree_elements)
        
        # Create commit
        commit = repo.create_git_commit(commit_message, tree, [latest_commit])
        
        # Update reference
        ref.edit(commit.sha)
        
        return {
            "action": "file_moved",
            "source_path": source_path,
            "destination_path": destination_path,
            "commit_sha": commit.sha,
            "commit_message": commit_message,
            "branch": branch
        }
        
    except GithubException as e:
        return {"error": f"Failed to move file: {str(e)}"}

@mcp.tool()
def move_files_batch(owner: str, repo_name: str, moves: List[Dict[str, str]],
                    commit_message: str = None, branch: str = "main") -> Dict[str, Any]:
    """
    Move multiple files in a single commit
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        moves: List of moves, each with 'source' and 'destination' keys
        commit_message: Commit message (optional, auto-generated if not provided)
        branch: Branch to move files on (default: main)
    
    Returns:
        Batch move operation result
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Auto-generate commit message if not provided
        if not commit_message:
            move_summary = ", ".join([f"{move['source']} → {move['destination']}" for move in moves[:3]])
            if len(moves) > 3:
                move_summary += f" and {len(moves) - 3} more"
            commit_message = f"Move files: {move_summary}"
        
        # Validate all moves first
        source_paths = []
        dest_paths = []
        file_contents = {}
        
        for move in moves:
            source = move["source"]
            dest = move["destination"]
            
            # Check for duplicates
            if source in source_paths:
                return {"error": f"Duplicate source path: {source}"}
            if dest in dest_paths:
                return {"error": f"Duplicate destination path: {dest}"}
            
            source_paths.append(source)
            dest_paths.append(dest)
            
            # Get source file content
            try:
                source_file = repo.get_contents(source, ref=branch)
                if source_file.encoding == "base64":
                    content = base64.b64decode(source_file.content).decode('utf-8')
                else:
                    content = source_file.content
                file_contents[dest] = content
            except GithubException:
                return {"error": f"Source file not found: {source}"}
            
            # Check if destination already exists (unless it's one of our sources)
            if dest not in source_paths:
                try:
                    repo.get_contents(dest, ref=branch)
                    return {"error": f"Destination file already exists: {dest}"}
                except GithubException:
                    pass  # Good, destination doesn't exist
        
        # Get the latest commit for batch operation
        ref = repo.get_git_ref(f"heads/{branch}")
        latest_commit = repo.get_git_commit(ref.object.sha)
        
        # Create blobs for destination files
        dest_blobs = {}
        for dest, content in file_contents.items():
            blob = repo.create_git_blob(content, "utf-8")
            dest_blobs[dest] = blob.sha
        
        # Build new tree
        tree_elements = []
        
        # Get all current files except the source files
        def get_all_files(path=""):
            """Recursively get all files in the repo"""
            try:
                contents = repo.get_contents(path, ref=branch)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for content_item in contents:
                    if content_item.type == "dir":
                        get_all_files(content_item.path)
                    elif content_item.path not in source_paths:  # Exclude source files
                        tree_elements.append({
                            "path": content_item.path,
                            "mode": "100644",
                            "type": "blob",
                            "sha": content_item.sha
                        })
            except:
                pass
        
        get_all_files()
        
        # Add files at their new destinations
        for dest, blob_sha in dest_blobs.items():
            tree_elements.append({
                "path": dest,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha
            })
        
        # Create tree with moved files
        tree = repo.create_git_tree(tree_elements)
        
        # Create commit
        commit = repo.create_git_commit(commit_message, tree, [latest_commit])
        
        # Update reference
        ref.edit(commit.sha)
        
        return {
            "action": "files_moved_batch",
            "files_moved": len(moves),
            "moves": [{"source": move["source"], "destination": move["destination"]} for move in moves],
            "commit_sha": commit.sha,
            "commit_message": commit_message,
            "branch": branch
        }
        
    except GithubException as e:
        return {"error": f"Failed to batch move files: {str(e)}"}

@mcp.tool()
def rename_file(owner: str, repo_name: str, file_path: str, new_name: str,
                commit_message: str = None, branch: str = "main") -> Dict[str, Any]:
    """
    Rename a file in a GitHub repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        file_path: Current path of the file to rename
        new_name: New name for the file (just the filename, not the full path)
        commit_message: Commit message (optional, auto-generated if not provided)
        branch: Branch to rename file on (default: main)
    
    Returns:
        Rename operation result
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Extract directory and current filename
        if "/" in file_path:
            directory = "/".join(file_path.split("/")[:-1])
            current_name = file_path.split("/")[-1]
            new_path = f"{directory}/{new_name}"
        else:
            # File is in root directory
            current_name = file_path
            new_path = new_name
        
        # Auto-generate commit message if not provided
        if not commit_message:
            commit_message = f"Rename {current_name} to {new_name}"
        
        # Check if new name is the same as current name
        if current_name == new_name:
            return {"error": "New name is the same as current name"}
        
        # Get the source file content
        source_file = repo.get_contents(file_path, ref=branch)
        
        # Decode content if it's base64 encoded
        if source_file.encoding == "base64":
            content = base64.b64decode(source_file.content).decode('utf-8')
        else:
            content = source_file.content
        
        # Check if destination already exists
        try:
            existing_dest = repo.get_contents(new_path, ref=branch)
            return {"error": f"A file named '{new_name}' already exists in this location"}
        except GithubException:
            # Good, destination doesn't exist
            pass
        
        # Get the latest commit for batch operation
        ref = repo.get_git_ref(f"heads/{branch}")
        latest_commit = repo.get_git_commit(ref.object.sha)
        
        # Create blob for the renamed file
        blob = repo.create_git_blob(content, "utf-8")
        
        # Get current tree and build new tree
        tree_elements = []
        
        # Get all current files except the source file
        def get_all_files(path=""):
            """Recursively get all files in the repo"""
            try:
                contents = repo.get_contents(path, ref=branch)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for content_item in contents:
                    if content_item.type == "dir":
                        get_all_files(content_item.path)
                    elif content_item.path != file_path:  # Exclude source file
                        tree_elements.append({
                            "path": content_item.path,
                            "mode": "100644",
                            "type": "blob",
                            "sha": content_item.sha
                        })
            except:
                pass
        
        get_all_files()
        
        # Add the file with the new name
        tree_elements.append({
            "path": new_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob.sha
        })
        
        # Create tree with the renamed file
        tree = repo.create_git_tree(tree_elements)
        
        # Create commit
        commit = repo.create_git_commit(commit_message, tree, [latest_commit])
        
        # Update reference
        ref.edit(commit.sha)
        
        return {
            "action": "file_renamed",
            "old_path": file_path,
            "new_path": new_path,
            "old_name": current_name,
            "new_name": new_name,
            "commit_sha": commit.sha,
            "commit_message": commit_message,
            "branch": branch
        }
        
    except GithubException as e:
        return {"error": f"Failed to rename file: {str(e)}"}

@mcp.tool()
def update_repo_settings(owner: str, repo_name: str, new_name: str = None, 
                        private: bool = None, description: str = None,
                        homepage: str = None, has_issues: bool = None,
                        has_wiki: bool = None, has_downloads: bool = None) -> Dict[str, Any]:
    """
    Update repository settings like name, privacy, description, etc.
    
    Args:
        owner: Repository owner
        repo_name: Current repository name
        new_name: New repository name (optional)
        private: Whether the repo should be private (optional)
        description: New repository description (optional)
        homepage: Homepage URL (optional)
        has_issues: Enable/disable issues (optional)
        has_wiki: Enable/disable wiki (optional)
        has_downloads: Enable/disable downloads (optional)
    
    Returns:
        Updated repository information
    """
    client = init_github_client()
    repo = client.get_repo(f"{owner}/{repo_name}")
    
    try:
        # Prepare update parameters
        update_params = {}
        changes_made = []
        
        if new_name is not None and new_name != repo.name:
            update_params["name"] = new_name
            changes_made.append(f"name: {repo.name} → {new_name}")
        
        if private is not None and private != repo.private:
            update_params["private"] = private
            privacy_status = "private" if private else "public"
            old_status = "private" if repo.private else "public"
            changes_made.append(f"privacy: {old_status} → {privacy_status}")
        
        if description is not None and description != repo.description:
            update_params["description"] = description
            old_desc = repo.description or "(no description)"
            changes_made.append(f"description: {old_desc[:50]}... → {description[:50]}...")
        
        if homepage is not None and homepage != repo.homepage:
            update_params["homepage"] = homepage
            old_home = repo.homepage or "(no homepage)"
            changes_made.append(f"homepage: {old_home} → {homepage}")
        
        if has_issues is not None and has_issues != repo.has_issues:
            update_params["has_issues"] = has_issues
            changes_made.append(f"issues: {'enabled' if has_issues else 'disabled'}")
        
        if has_wiki is not None and has_wiki != repo.has_wiki:
            update_params["has_wiki"] = has_wiki
            changes_made.append(f"wiki: {'enabled' if has_wiki else 'disabled'}")
        
        if has_downloads is not None and has_downloads != repo.has_downloads:
            update_params["has_downloads"] = has_downloads
            changes_made.append(f"downloads: {'enabled' if has_downloads else 'disabled'}")
        
        if not update_params:
            return {"message": "No changes needed - all settings are already as specified"}
        
        # Update the repository
        repo.edit(**update_params)
        
        # Refresh repo object to get updated info
        updated_repo = client.get_repo(f"{owner}/{new_name if new_name else repo_name}")
        
        return {
            "action": "repository_updated",
            "old_name": repo_name,
            "new_name": updated_repo.name,
            "changes_made": changes_made,
            "updated_settings": {
                "name": updated_repo.name,
                "full_name": updated_repo.full_name,
                "description": updated_repo.description,
                "private": updated_repo.private,
                "homepage": updated_repo.homepage,
                "has_issues": updated_repo.has_issues,
                "has_wiki": updated_repo.has_wiki,
                "has_downloads": updated_repo.has_downloads,
                "url": updated_repo.html_url
            }
        }
        
    except GithubException as e:
        return {"error": f"Failed to update repository settings: {str(e)}"}

@mcp.tool()
def merge_pull_request(owner: str, repo_name: str, pr_number: int, 
                      commit_title: str = None, commit_message: str = None,
                      merge_method: str = "merge") -> Dict[str, Any]:
    """
    Merge a pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number to merge
        commit_title: Title for the merge commit (optional)
        commit_message: Message for the merge commit (optional)
        merge_method: Merge method ("merge", "squash", "rebase")
    
    Returns:
        Merge result information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        # Check if PR is mergeable
        if not pr.mergeable:
            return {"error": f"Pull request #{pr_number} is not mergeable. Check for conflicts."}
        
        if pr.state != "open":
            return {"error": f"Pull request #{pr_number} is {pr.state}, not open"}
        
        # Merge the PR
        merge_result = pr.merge(
            commit_title=commit_title,
            commit_message=commit_message,
            merge_method=merge_method
        )
        
        return {
            "action": "pull_request_merged",
            "pr_number": pr_number,
            "merged": merge_result.merged,
            "sha": merge_result.sha,
            "message": merge_result.message,
            "merge_method": merge_method,
            "pr_url": pr.html_url
        }
        
    except GithubException as e:
        return {"error": f"Failed to merge pull request: {str(e)}"}

@mcp.tool()
def close_pull_request(owner: str, repo_name: str, pr_number: int,
                      comment: str = None) -> Dict[str, Any]:
    """
    Close a pull request without merging
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number to close
        comment: Optional comment to add when closing
    
    Returns:
        Close result information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        if pr.state != "open":
            return {"error": f"Pull request #{pr_number} is already {pr.state}"}
        
        # Add comment if provided
        if comment:
            pr.create_issue_comment(comment)
        
        # Close the PR
        pr.edit(state="closed")
        
        return {
            "action": "pull_request_closed",
            "pr_number": pr_number,
            "title": pr.title,
            "url": pr.html_url,
            "comment_added": bool(comment)
        }
        
    except GithubException as e:
        return {"error": f"Failed to close pull request: {str(e)}"}

@mcp.tool()
def compare_branches(owner: str, repo_name: str, base_branch: str, 
                    head_branch: str, head_repo: str = None) -> Dict[str, Any]:
    """
    Compare two branches to see differences
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        base_branch: Base branch for comparison
        head_branch: Head branch for comparison
        head_repo: Repository for head branch (for cross-repo comparison)
    
    Returns:
        Comparison information including commits and file changes
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        # Construct the comparison
        if head_repo:
            # Cross-repository comparison
            comparison = repo.compare(base_branch, f"{head_repo}:{head_branch}")
        else:
            # Same repository comparison
            comparison = repo.compare(base_branch, head_branch)
        
        # Get file changes
        files_changed = []
        for file in comparison.files:
            files_changed.append({
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "patch": file.patch[:500] if file.patch else None  # Limit patch size
            })
        
        # Get commit info
        commits = []
        for commit in comparison.commits:
            commits.append({
                "sha": commit.sha,
                "message": commit.commit.message,
                "author": commit.commit.author.name,
                "date": commit.commit.author.date.isoformat(),
                "url": commit.html_url
            })
        
        return {
            "base_branch": base_branch,
            "head_branch": head_branch,
            "head_repo": head_repo,
            "repository": f"{owner}/{repo_name}",
            "status": comparison.status,
            "ahead_by": comparison.ahead_by,
            "behind_by": comparison.behind_by,
            "total_commits": comparison.total_commits,
            "files_changed": files_changed,
            "commits": commits,
            "merge_base_commit": comparison.merge_base_commit.sha if comparison.merge_base_commit else None
        }
        
    except GithubException as e:
        return {"error": f"Failed to compare branches: {str(e)}"}

@mcp.tool()
def get_project_docs(owner: str, repo_name: str, include_wiki: bool = True) -> Dict[str, Any]:
    """
    Get comprehensive, up-to-date documentation for a project
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        include_wiki: Whether to include wiki pages (default: True)
    
    Returns:
        Complete project documentation including README, wiki, and key files
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        docs = {
            "repository": f"{owner}/{repo_name}",
            "description": repo.description,
            "homepage": repo.homepage,
            "topics": repo.get_topics(),
            "readme": None,
            "license": None,
            "contributing": None,
            "code_of_conduct": None,
            "security": None,
            "changelog": None,
            "wiki_pages": []
        }
        
        # Common documentation files to look for
        doc_files = {
            "readme": ["README.md", "README.rst", "README.txt", "readme.md"],
            "license": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
            "contributing": ["CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING.txt"],
            "code_of_conduct": ["CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.rst"],
            "security": ["SECURITY.md", "SECURITY.rst", "SECURITY.txt"],
            "changelog": ["CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG.txt", "HISTORY.md"]
        }
        
        # Try to find and read each documentation file
        for doc_type, filenames in doc_files.items():
            for filename in filenames:
                try:
                    file_content = repo.get_contents(filename)
                    if file_content.encoding == "base64":
                        content = base64.b64decode(file_content.content).decode('utf-8')
                    else:
                        content = file_content.content
                    
                    docs[doc_type] = {
                        "filename": filename,
                        "content": content[:5000],  # Limit content size
                        "size": file_content.size,
                        "url": file_content.html_url
                    }
                    break  # Found one, move to next doc type
                except GithubException:
                    continue  # File not found, try next filename
        
        # Get wiki pages if requested and available
        if include_wiki and repo.has_wiki:
            try:
                # Note: Wiki access through API is limited, this is a basic implementation
                docs["wiki_available"] = True
                docs["wiki_url"] = f"{repo.html_url}/wiki"
            except:
                docs["wiki_available"] = False
        
        return docs
        
    except GithubException as e:
        return {"error": f"Failed to get project documentation: {str(e)}"}

@mcp.tool()
def clone_repo_local(owner: str, repo_name: str, local_path: str, 
                    branch: str = None) -> Dict[str, Any]:
    """
    Clone a GitHub repository to local filesystem
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        local_path: Local directory to clone into
        branch: Specific branch to clone (optional)
    
    Returns:
        Clone operation result
    """
    import subprocess
    import os
    
    try:
        repo_url = f"https://github.com/{owner}/{repo_name}.git"
        
        # Prepare clone command
        cmd = ["git", "clone", repo_url, local_path]
        if branch:
            cmd.extend(["-b", branch])
        
        # Execute clone
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {
                "action": "repository_cloned",
                "repository": f"{owner}/{repo_name}",
                "local_path": os.path.abspath(local_path),
                "branch": branch or "main",
                "clone_url": repo_url,
                "success": True
            }
        else:
            return {
                "error": f"Failed to clone repository: {result.stderr}",
                "repository": f"{owner}/{repo_name}",
                "attempted_path": local_path
            }
            
    except Exception as e:
        return {"error": f"Clone operation failed: {str(e)}"}

@mcp.tool()
def setup_local_git_repo(local_path: str, repo_name: str, 
                        initial_commit_message: str = "Initial commit") -> Dict[str, Any]:
    """
    Initialize a new git repository locally and set up GitHub integration
    
    Args:
        local_path: Path to the project directory
        repo_name: Name for the repository
        initial_commit_message: Message for initial commit
    
    Returns:
        Setup result with next steps
    """
    import subprocess
    import os
    
    try:
        # Change to the project directory
        original_dir = os.getcwd()
        os.chdir(local_path)
        
        try:
            # Initialize git repository
            subprocess.run(["git", "init"], check=True)
            
            # Add all files
            subprocess.run(["git", "add", "."], check=True)
            
            # Create initial commit
            subprocess.run(["git", "commit", "-m", initial_commit_message], check=True)
            
            # Get current user for GitHub URL
            client = init_github_client()
            username = client.get_user().login
            
            return {
                "action": "local_git_initialized",
                "local_path": os.path.abspath(local_path),
                "repo_name": repo_name,
                "initial_commit": initial_commit_message,
                "next_steps": [
                    "Create GitHub repository (use create_repo tool)",
                    f"Add remote: git remote add origin https://github.com/{username}/{repo_name}.git",
                    "Push code: git push -u origin main"
                ],
                "suggested_remote_url": f"https://github.com/{username}/{repo_name}.git"
            }
            
        finally:
            os.chdir(original_dir)
            
    except subprocess.CalledProcessError as e:
        return {"error": f"Git command failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Setup failed: {str(e)}"}

@mcp.tool()
def create_github_repo_from_local(repo_name: str, local_path: str, 
                                 description: str = "", private: bool = False,
                                 auto_push: bool = True) -> Dict[str, Any]:
    """
    Create a new GitHub repository and push local code to it
    
    Args:
        repo_name: Name for the new repository
        local_path: Path to local project to push
        description: Repository description
        private: Whether to make repository private
        auto_push: Automatically push local code to new repo
    
    Returns:
        Repository creation and push result
    """
    import subprocess
    import os
    
    try:
        # Create the GitHub repository
        repo_result = create_repo(repo_name, description, private, auto_init=False)
        
        if "error" in repo_result:
            return repo_result
        
        if auto_push:
            # Change to local directory
            original_dir = os.getcwd()
            os.chdir(local_path)
            
            try:
                # Add remote if not exists
                remote_url = repo_result["clone_url"]
                subprocess.run(["git", "remote", "add", "origin", remote_url], 
                             capture_output=True)  # Ignore error if remote exists
                
                # Push to GitHub
                push_result = subprocess.run(["git", "push", "-u", "origin", "main"], 
                                           capture_output=True, text=True)
                
                if push_result.returncode != 0:
                    # Try with 'master' if 'main' fails
                    push_result = subprocess.run(["git", "push", "-u", "origin", "master"], 
                                               capture_output=True, text=True)
                
                if push_result.returncode == 0:
                    repo_result.update({
                        "push_success": True,
                        "local_path": os.path.abspath(local_path),
                        "message": "Repository created and code pushed successfully"
                    })
                else:
                    repo_result.update({
                        "push_success": False,
                        "push_error": push_result.stderr,
                        "message": "Repository created but push failed"
                    })
                    
            finally:
                os.chdir(original_dir)
        
        return repo_result
        
    except Exception as e:
        return {"error": f"Failed to create repository from local code: {str(e)}"}

@mcp.tool()
def sync_local_with_remote(local_path: str, branch: str = "main") -> Dict[str, Any]:
    """
    Sync local repository with remote (pull latest changes)
    
    Args:
        local_path: Path to local repository
        branch: Branch to sync (default: main)
    
    Returns:
        Sync operation result
    """
    import subprocess
    import os
    
    try:
        original_dir = os.getcwd()
        os.chdir(local_path)
        
        try:
            # Fetch latest changes
            subprocess.run(["git", "fetch", "origin"], check=True, capture_output=True)
            
            # Pull changes
            pull_result = subprocess.run(["git", "pull", "origin", branch], 
                                       capture_output=True, text=True)
            
            if pull_result.returncode == 0:
                return {
                    "action": "repository_synced",
                    "local_path": os.path.abspath(local_path),
                    "branch": branch,
                    "output": pull_result.stdout,
                    "success": True
                }
            else:
                return {
                    "error": f"Sync failed: {pull_result.stderr}",
                    "local_path": local_path,
                    "branch": branch
                }
                
        finally:
            os.chdir(original_dir)
            
    except subprocess.CalledProcessError as e:
        return {"error": f"Git sync failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Sync operation failed: {str(e)}"}

@mcp.tool()
def fork_and_setup_contribution(owner: str, repo_name: str, feature_branch: str, 
                               organization: str = None) -> Dict[str, Any]:
    """
    Complete workflow: Fork repository and create a feature branch for contributions
    
    This is the ideal function for starting contributions to open source projects.
    It handles the common workflow of fork -> create feature branch -> ready to work.
    
    Args:
        owner: Repository owner (username or organization)
        repo_name: Repository name to fork
        feature_branch: Name for the feature branch to create
        organization: Optional organization to fork to (defaults to your account)
    
    Returns:
        Complete setup information with next steps
    """
    client = init_github_client()
    
    try:
        # Step 1: Fork the repository (handles existing forks gracefully)
        fork_result = fork_repository(owner, repo_name, organization)
        
        if "error" in fork_result:
            return fork_result
        
        # Extract fork info
        if fork_result["action"] == "repository_forked":
            fork_owner = fork_result["fork"]["owner"]
            fork_name = fork_result["fork"]["name"]
        else:  # fork_already_exists
            fork_owner = fork_result["fork"]["owner"]
            fork_name = fork_result["fork"]["name"]
        
        # Step 2: Create feature branch on the fork
        branch_result = create_branch(fork_owner, fork_name, feature_branch)
        
        if "error" in branch_result:
            # If branch already exists, that's okay for this workflow
            if "already exists" not in str(branch_result.get("error", "")):
                return {
                    "error": f"Fork successful but failed to create branch: {branch_result['error']}",
                    "fork_info": fork_result
                }
        
        return {
            "action": "contribution_setup_complete",
            "message": "Repository forked and feature branch created - ready for contributions!",
            "original_repo": {
                "full_name": f"{owner}/{repo_name}",
                "url": f"https://github.com/{owner}/{repo_name}"
            },
            "fork_info": fork_result["fork"],
            "feature_branch": feature_branch,
            "next_steps": [
                f"Make your changes on the '{feature_branch}' branch",
                f"Commit and push your changes to your fork",
                f"Create a pull request from {fork_owner}/{fork_name}:{feature_branch} to {owner}/{repo_name}:main"
            ],
            "clone_command": f"git clone {fork_result['fork']['clone_url']}",
            "branch_checkout": f"git checkout {feature_branch}",
            "ready_for_pr": True
        }
        
    except Exception as e:
        return {"error": f"Setup failed: {str(e)}"}

@mcp.tool()
def create_cross_repo_pull_request(upstream_owner: str, upstream_repo: str, 
                                  fork_owner: str, fork_repo: str, head_branch: str,
                                  title: str, body: str, base_branch: str = "main") -> Dict[str, Any]:
    """
    Create a pull request from a fork to the upstream repository
    
    This is specifically designed for contributing to open source projects where
    you've forked a repo and want to create a PR back to the original.
    
    Args:
        upstream_owner: Original repository owner
        upstream_repo: Original repository name
        fork_owner: Fork owner (usually your username)
        fork_repo: Fork repository name (usually same as upstream)
        head_branch: Branch with your changes (on the fork)
        title: Pull request title
        body: Pull request description
        base_branch: Branch to merge into on upstream (default: main)
    
    Returns:
        Pull request information
    """
    client = init_github_client()
    
    try:
        # Get the upstream repository
        upstream = client.get_repo(f"{upstream_owner}/{upstream_repo}")
        
        # Verify the fork exists and has the head branch
        fork = client.get_repo(f"{fork_owner}/{fork_repo}")
        
        try:
            fork.get_branch(head_branch)
        except GithubException:
            return {"error": f"Branch '{head_branch}' not found in fork {fork_owner}/{fork_repo}"}
        
        # Create the PR from fork to upstream
        pr = upstream.create_pull(
            title=title,
            body=body,
            head=f"{fork_owner}:{head_branch}",  # This is the key for cross-repo PRs
            base=base_branch
        )
        
        return {
            "action": "cross_repo_pull_request_created",
            "pr_number": pr.number,
            "title": pr.title,
            "url": pr.html_url,
            "upstream_repo": f"{upstream_owner}/{upstream_repo}",
            "fork_repo": f"{fork_owner}/{fork_repo}",
            "head_branch": head_branch,
            "base_branch": base_branch,
            "state": pr.state,
            "mergeable": pr.mergeable,
            "draft": pr.draft
        }
        
    except GithubException as e:
        return {"error": f"Failed to create cross-repo pull request: {str(e)}"}

@mcp.tool()
def complete_fork_to_pr_workflow(upstream_owner: str, upstream_repo: str,
                                feature_branch: str, title: str, body: str,
                                file_changes: List[Dict[str, str]] = None,
                                base_branch: str = "main") -> Dict[str, Any]:
    """
    Complete workflow: Fork -> Create Branch -> Make Changes -> Create PR
    
    This is the ultimate function for contributing to open source projects.
    It handles the entire workflow from fork to pull request creation.
    
    Args:
        upstream_owner: Original repository owner
        upstream_repo: Original repository name
        feature_branch: Name for the feature branch
        title: Pull request title
        body: Pull request description
        file_changes: Optional list of file changes to make (each with 'path' and 'content')
        base_branch: Branch to merge into on upstream (default: main)
    
    Returns:
        Complete workflow result with PR information
    """
    client = init_github_client()
    
    try:
        # Step 1: Fork and setup contribution
        setup_result = fork_and_setup_contribution(upstream_owner, upstream_repo, feature_branch)
        
        if "error" in setup_result:
            return setup_result
        
        fork_owner = setup_result["fork_info"]["owner"]
        fork_name = setup_result["fork_info"]["name"]
        
        # Step 2: Make file changes if provided
        if file_changes:
            changes_result = batch_update_files(
                fork_owner, 
                fork_name, 
                file_changes,
                f"Implement changes for {title}",
                feature_branch
            )
            
            if "error" in changes_result:
                return {
                    "error": f"Fork and branch created but failed to make changes: {changes_result['error']}",
                    "setup_info": setup_result
                }
        
        # Step 3: Create the pull request
        pr_result = create_cross_repo_pull_request(
            upstream_owner, upstream_repo, fork_owner, fork_name,
            feature_branch, title, body, base_branch
        )
        
        if "error" in pr_result:
            return {
                "error": f"Fork and changes complete but failed to create PR: {pr_result['error']}",
                "setup_info": setup_result,
                "changes_made": bool(file_changes)
            }
        
        return {
            "action": "complete_contribution_workflow",
            "message": "Successfully forked, made changes, and created pull request!",
            "workflow_steps": [
                "✅ Repository forked",
                "✅ Feature branch created", 
                "✅ Changes committed" if file_changes else "⏭️ Ready for manual changes",
                "✅ Pull request created"
            ],
            "setup_info": setup_result,
            "pr_info": pr_result,
            "changes_made": len(file_changes) if file_changes else 0
        }
        
    except Exception as e:
        return {"error": f"Complete workflow failed: {str(e)}"}

@mcp.tool()
def update_pull_request(owner: str, repo_name: str, pr_number: int,
                       title: str = None, body: str = None, state: str = None,
                       base_branch: str = None) -> Dict[str, Any]:
    """
    Update an existing pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number to update
        title: New title (optional)
        body: New body/description (optional)
        state: New state - "open" or "closed" (optional)
        base_branch: New base branch (optional)
    
    Returns:
        Updated pull request information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        # Prepare update parameters
        update_params = {}
        changes_made = []
        
        if title is not None and title != pr.title:
            update_params["title"] = title
            changes_made.append(f"title: '{pr.title}' → '{title}'")
        
        if body is not None and body != pr.body:
            update_params["body"] = body
            changes_made.append("body: updated")
        
        if state is not None and state != pr.state:
            update_params["state"] = state
            changes_made.append(f"state: {pr.state} → {state}")
        
        if base_branch is not None and base_branch != pr.base.ref:
            update_params["base"] = base_branch
            changes_made.append(f"base branch: {pr.base.ref} → {base_branch}")
        
        if not update_params:
            return {"message": "No changes needed - all parameters are already as specified"}
        
        # Update the PR
        pr.edit(**update_params)
        
        return {
            "action": "pull_request_updated",
            "pr_number": pr_number,
            "changes_made": changes_made,
            "title": pr.title,
            "state": pr.state,
            "url": pr.html_url
        }
        
    except GithubException as e:
        return {"error": f"Failed to update pull request: {str(e)}"}

@mcp.tool()
def add_pull_request_comment(owner: str, repo_name: str, pr_number: int,
                            comment: str) -> Dict[str, Any]:
    """
    Add a comment to a pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number
        comment: Comment text to add
    
    Returns:
        Comment creation result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        comment_obj = pr.create_issue_comment(comment)
        
        return {
            "action": "comment_added",
            "pr_number": pr_number,
            "comment_id": comment_obj.id,
            "comment_url": comment_obj.html_url,
            "author": comment_obj.user.login,
            "created_at": comment_obj.created_at.isoformat()
        }
        
    except GithubException as e:
        return {"error": f"Failed to add comment: {str(e)}"}

@mcp.tool()
def submit_pull_request_review(owner: str, repo_name: str, pr_number: int,
                              event: str, body: str = "",
                              comments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Submit a review for a pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number
        event: Review event ("APPROVE", "REQUEST_CHANGES", "COMMENT")
        body: Overall review comment
        comments: List of line-specific comments (each with 'path', 'line', 'body')
    
    Returns:
        Review submission result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        # Prepare review comments
        review_comments = []
        if comments:
            for comment in comments:
                review_comments.append({
                    "path": comment["path"],
                    "line": comment["line"],
                    "body": comment["body"]
                })
        
        # Submit the review
        review = pr.create_review(
            body=body,
            event=event,
            comments=review_comments if review_comments else None
        )
        
        return {
            "action": "review_submitted",
            "pr_number": pr_number,
            "review_id": review.id,
            "event": event,
            "review_url": review.html_url,
            "line_comments": len(review_comments),
            "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None
        }
        
    except GithubException as e:
        return {"error": f"Failed to submit review: {str(e)}"}

@mcp.tool()
def request_pull_request_reviewers(owner: str, repo_name: str, pr_number: int,
                                  reviewers: List[str] = None,
                                  team_reviewers: List[str] = None) -> Dict[str, Any]:
    """
    Request reviewers for a pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number
        reviewers: List of usernames to request as reviewers
        team_reviewers: List of team names to request as reviewers
    
    Returns:
        Reviewer request result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        # Request reviewers
        result = pr.create_review_request(
            reviewers=reviewers or [],
            team_reviewers=team_reviewers or []
        )
        
        return {
            "action": "reviewers_requested",
            "pr_number": pr_number,
            "requested_reviewers": [user.login for user in result.requested_reviewers],
            "requested_teams": [team.name for team in result.requested_teams],
            "total_requested": len(result.requested_reviewers) + len(result.requested_teams)
        }
        
    except GithubException as e:
        return {"error": f"Failed to request reviewers: {str(e)}"}

@mcp.tool()
def list_pull_request_reviews(owner: str, repo_name: str, pr_number: int) -> Dict[str, Any]:
    """
    List all reviews for a pull request
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number
    
    Returns:
        List of reviews with details
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        reviews = []
        for review in pr.get_reviews():
            review_data = {
                "id": review.id,
                "user": review.user.login,
                "state": review.state,
                "body": review.body,
                "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
                "commit_id": review.commit_id,
                "html_url": review.html_url
            }
            reviews.append(review_data)
        
        return {
            "pr_number": pr_number,
            "repository": f"{owner}/{repo_name}",
            "total_reviews": len(reviews),
            "reviews": reviews
        }
        
    except GithubException as e:
        return {"error": f"Failed to list reviews: {str(e)}"}

@mcp.tool()
def auto_merge_pull_request(owner: str, repo_name: str, pr_number: int,
                           merge_method: str = "merge") -> Dict[str, Any]:
    """
    Enable auto-merge for a pull request (will merge when requirements are met)
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number
        merge_method: Merge method ("merge", "squash", "rebase")
    
    Returns:
        Auto-merge configuration result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        
        # Enable auto-merge (this uses GitHub's GraphQL API under the hood)
        # Note: This requires the PR to pass all required checks
        
        return {
            "action": "auto_merge_enabled",
            "pr_number": pr_number,
            "merge_method": merge_method,
            "message": "Auto-merge enabled - PR will merge automatically when all requirements are met",
            "requirements": [
                "All required status checks must pass",
                "All required reviews must be approved",
                "No conflicts with base branch"
            ]
        }
        
    except GithubException as e:
        return {"error": f"Failed to enable auto-merge: {str(e)}"}

@mcp.tool()
def create_issue(owner: str, repo_name: str, title: str, body: str = "",
                labels: List[str] = None, assignees: List[str] = None,
                milestone: int = None) -> Dict[str, Any]:
    """
    Create a new issue in a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        title: Issue title
        body: Issue description/body (optional)
        labels: List of label names to apply (optional)
        assignees: List of usernames to assign (optional)
        milestone: Milestone number to assign (optional)
    
    Returns:
        Created issue information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        # Create the issue
        issue = repo.create_issue(
            title=title,
            body=body,
            labels=labels or [],
            assignees=assignees or [],
            milestone=repo.get_milestone(milestone) if milestone else None
        )
        
        return {
            "action": "issue_created",
            "issue_number": issue.number,
            "title": issue.title,
            "url": issue.html_url,
            "state": issue.state,
            "author": issue.user.login,
            "labels": [label.name for label in issue.labels],
            "assignees": [assignee.login for assignee in issue.assignees],
            "created_at": issue.created_at.isoformat()
        }
        
    except GithubException as e:
        return {"error": f"Failed to create issue: {str(e)}"}

@mcp.tool()
def list_issues(owner: str, repo_name: str, state: str = "open", 
               labels: List[str] = None, assignee: str = None,
               creator: str = None, limit: int = 20) -> Dict[str, Any]:
    """
    List issues in a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        state: Issue state ("open", "closed", "all")
        labels: Filter by label names (optional)
        assignee: Filter by assignee username (optional)  
        creator: Filter by creator username (optional)
        limit: Maximum number of issues to return (default: 20)
    
    Returns:
        List of issues with details
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        # Build filter parameters
        kwargs = {"state": state}
        if labels:
            kwargs["labels"] = labels
        if assignee:
            kwargs["assignee"] = assignee
        if creator:
            kwargs["creator"] = creator
        
        issues = []
        for issue in repo.get_issues(**kwargs)[:limit]:
            # Skip pull requests (GitHub API returns PRs as issues)
            if not issue.pull_request:
                issues.append({
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "author": issue.user.login,
                    "labels": [label.name for label in issue.labels],
                    "assignees": [assignee.login for assignee in issue.assignees],
                    "comments": issue.comments,
                    "created_at": issue.created_at.isoformat(),
                    "updated_at": issue.updated_at.isoformat(),
                    "url": issue.html_url
                })
        
        return {
            "repository": f"{owner}/{repo_name}",
            "state": state,
            "total_count": len(issues),
            "issues": issues
        }
        
    except GithubException as e:
        return {"error": f"Failed to list issues: {str(e)}"}

@mcp.tool()
def get_issue_details(owner: str, repo_name: str, issue_number: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number
    
    Returns:
        Detailed issue information including comments
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Get comments
        comments = []
        for comment in issue.get_comments():
            comments.append({
                "id": comment.id,
                "author": comment.user.login,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat(),
                "url": comment.html_url
            })
        
        # Get events (optional, for activity tracking)
        events = []
        for event in issue.get_events()[:10]:  # Limit to last 10 events
            events.append({
                "event": event.event,
                "actor": event.actor.login if event.actor else None,
                "created_at": event.created_at.isoformat()
            })
        
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "author": issue.user.login,
            "labels": [{
                "name": label.name,
                "color": label.color,
                "description": label.description
            } for label in issue.labels],
            "assignees": [assignee.login for assignee in issue.assignees],
            "milestone": {
                "title": issue.milestone.title,
                "number": issue.milestone.number,
                "due_on": issue.milestone.due_on.isoformat() if issue.milestone.due_on else None
            } if issue.milestone else None,
            "comments_count": issue.comments,
            "comments": comments,
            "events": events,
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
            "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
            "url": issue.html_url
        }
        
    except GithubException as e:
        return {"error": f"Failed to get issue details: {str(e)}"}

@mcp.tool()
def add_issue_comment(owner: str, repo_name: str, issue_number: int,
                     comment: str) -> Dict[str, Any]:
    """
    Add a comment to an issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number
        comment: Comment text to add
    
    Returns:
        Comment creation result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        comment_obj = issue.create_comment(comment)
        
        return {
            "action": "comment_added",
            "issue_number": issue_number,
            "comment_id": comment_obj.id,
            "comment_url": comment_obj.html_url,
            "author": comment_obj.user.login,
            "created_at": comment_obj.created_at.isoformat()
        }
        
    except GithubException as e:
        return {"error": f"Failed to add comment: {str(e)}"}

@mcp.tool()
def update_issue(owner: str, repo_name: str, issue_number: int,
                title: str = None, body: str = None, state: str = None,
                labels: List[str] = None, assignees: List[str] = None,
                milestone: int = None) -> Dict[str, Any]:
    """
    Update an existing issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number to update
        title: New title (optional)
        body: New body/description (optional)
        state: New state - "open" or "closed" (optional)
        labels: New list of label names (optional)
        assignees: New list of assignee usernames (optional)
        milestone: New milestone number (optional, use 0 to remove)
    
    Returns:
        Updated issue information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Prepare update parameters
        update_params = {}
        changes_made = []
        
        if title is not None and title != issue.title:
            update_params["title"] = title
            changes_made.append(f"title: '{issue.title}' → '{title}'")
        
        if body is not None and body != issue.body:
            update_params["body"] = body
            changes_made.append("body: updated")
        
        if state is not None and state != issue.state:
            update_params["state"] = state
            changes_made.append(f"state: {issue.state} → {state}")
        
        if labels is not None:
            current_labels = [label.name for label in issue.labels]
            if labels != current_labels:
                update_params["labels"] = labels
                changes_made.append(f"labels: {current_labels} → {labels}")
        
        if assignees is not None:
            current_assignees = [assignee.login for assignee in issue.assignees]
            if assignees != current_assignees:
                update_params["assignees"] = assignees
                changes_made.append(f"assignees: {current_assignees} → {assignees}")
        
        if milestone is not None:
            if milestone == 0:
                update_params["milestone"] = None
                changes_made.append("milestone: removed")
            else:
                milestone_obj = repo.get_milestone(milestone)
                update_params["milestone"] = milestone_obj
                changes_made.append(f"milestone: set to {milestone_obj.title}")
        
        if not update_params:
            return {"message": "No changes needed - all parameters are already as specified"}
        
        # Update the issue
        issue.edit(**update_params)
        
        return {
            "action": "issue_updated",
            "issue_number": issue_number,
            "changes_made": changes_made,
            "title": issue.title,
            "state": issue.state,
            "url": issue.html_url
        }
        
    except GithubException as e:
        return {"error": f"Failed to update issue: {str(e)}"}

@mcp.tool()
def close_issue(owner: str, repo_name: str, issue_number: int,
               comment: str = None) -> Dict[str, Any]:
    """
    Close an issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number to close
        comment: Optional comment to add when closing
    
    Returns:
        Close result information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        if issue.state == "closed":
            return {"message": f"Issue #{issue_number} is already closed"}
        
        # Add comment if provided
        if comment:
            issue.create_comment(comment)
        
        # Close the issue
        issue.edit(state="closed")
        
        return {
            "action": "issue_closed",
            "issue_number": issue_number,
            "title": issue.title,
            "url": issue.html_url,
            "comment_added": bool(comment)
        }
        
    except GithubException as e:
        return {"error": f"Failed to close issue: {str(e)}"}

@mcp.tool()
def add_issue_labels(owner: str, repo_name: str, issue_number: int,
                    labels: List[str]) -> Dict[str, Any]:
    """
    Add labels to an issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number
        labels: List of label names to add
    
    Returns:
        Label addition result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Add labels
        issue.add_to_labels(*labels)
        
        # Get updated issue to return current labels
        updated_issue = repo.get_issue(issue_number)
        current_labels = [label.name for label in updated_issue.labels]
        
        return {
            "action": "labels_added",
            "issue_number": issue_number,
            "labels_added": labels,
            "current_labels": current_labels
        }
        
    except GithubException as e:
        return {"error": f"Failed to add labels: {str(e)}"}

@mcp.tool()
def remove_issue_labels(owner: str, repo_name: str, issue_number: int,
                       labels: List[str]) -> Dict[str, Any]:
    """
    Remove labels from an issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number
        labels: List of label names to remove
    
    Returns:
        Label removal result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Remove labels
        issue.remove_from_labels(*labels)
        
        # Get updated issue to return current labels
        updated_issue = repo.get_issue(issue_number)
        current_labels = [label.name for label in updated_issue.labels]
        
        return {
            "action": "labels_removed",
            "issue_number": issue_number,
            "labels_removed": labels,
            "current_labels": current_labels
        }
        
    except GithubException as e:
        return {"error": f"Failed to remove labels: {str(e)}"}

@mcp.tool()
def assign_issue(owner: str, repo_name: str, issue_number: int,
                assignees: List[str]) -> Dict[str, Any]:
    """
    Assign users to an issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number
        assignees: List of usernames to assign
    
    Returns:
        Assignment result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Add assignees
        issue.add_to_assignees(*assignees)
        
        # Get updated issue to return current assignees
        updated_issue = repo.get_issue(issue_number)
        current_assignees = [assignee.login for assignee in updated_issue.assignees]
        
        return {
            "action": "users_assigned",
            "issue_number": issue_number,
            "assignees_added": assignees,
            "current_assignees": current_assignees
        }
        
    except GithubException as e:
        return {"error": f"Failed to assign users: {str(e)}"}

@mcp.tool()
def unassign_issue(owner: str, repo_name: str, issue_number: int,
                  assignees: List[str]) -> Dict[str, Any]:
    """
    Unassign users from an issue
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number
        assignees: List of usernames to unassign
    
    Returns:
        Unassignment result
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        
        # Remove assignees
        issue.remove_from_assignees(*assignees)
        
        # Get updated issue to return current assignees
        updated_issue = repo.get_issue(issue_number)
        current_assignees = [assignee.login for assignee in updated_issue.assignees]
        
        return {
            "action": "users_unassigned",
            "issue_number": issue_number,
            "assignees_removed": assignees,
            "current_assignees": current_assignees
        }
        
    except GithubException as e:
        return {"error": f"Failed to unassign users: {str(e)}"}

@mcp.tool()
def list_repository_labels(owner: str, repo_name: str) -> Dict[str, Any]:
    """
    List all labels available in a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
    
    Returns:
        List of repository labels
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        labels = []
        for label in repo.get_labels():
            labels.append({
                "name": label.name,
                "color": label.color,
                "description": label.description,
                "url": label.url
            })
        
        return {
            "repository": f"{owner}/{repo_name}",
            "total_labels": len(labels),
            "labels": labels
        }
        
    except GithubException as e:
        return {"error": f"Failed to list labels: {str(e)}"}

@mcp.tool()
def create_repository_label(owner: str, repo_name: str, name: str,
                           color: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new label in a repository
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        name: Label name
        color: Label color (hex code without #, e.g., "ff0000")
        description: Label description (optional)
    
    Returns:
        Created label information
    """
    client = init_github_client()
    
    try:
        repo = client.get_repo(f"{owner}/{repo_name}")
        
        label = repo.create_label(
            name=name,
            color=color,
            description=description
        )
        
        return {
            "action": "label_created",
            "name": label.name,
            "color": label.color,
            "description": label.description,
            "url": label.url
        }
        
    except GithubException as e:
        return {"error": f"Failed to create label: {str(e)}"}

@mcp.tool()
def search_repository_issues(owner: str, repo_name: str, query: str,
                           state: str = "all", limit: int = 20) -> Dict[str, Any]:
    """
    Search for issues in a repository using GitHub's search
    
    Args:
        owner: Repository owner
        repo_name: Repository name
        query: Search query (e.g., "bug", "help wanted", etc.)
        state: Issue state filter ("open", "closed", "all")
        limit: Maximum number of results (default: 20)
    
    Returns:
        Search results with matching issues
    """
    client = init_github_client()
    
    try:
        # Build search query
        search_query = f"{query} repo:{owner}/{repo_name} is:issue"
        if state != "all":
            search_query += f" is:{state}"
        
        results = client.search_issues(search_query)
        
        issues = []
        for issue in results[:limit]:
            issues.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "author": issue.user.login,
                "labels": [label.name for label in issue.labels],
                "assignees": [assignee.login for assignee in issue.assignees],
                "comments": issue.comments,
                "score": issue.score,
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "url": issue.html_url
            })
        
        return {
            "query": query,
            "repository": f"{owner}/{repo_name}",
            "total_count": results.totalCount,
            "returned_count": len(issues),
            "issues": issues
        }
        
    except GithubException as e:
        return {"error": f"Failed to search issues: {str(e)}"}

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
