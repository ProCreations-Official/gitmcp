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

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
