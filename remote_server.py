#!/usr/bin/env python3
"""
GitMCP Remote Server
A remote MCP server implementation for Anthropic's new Integrations feature.
Supports both SSE and HTTP streaming protocols for remote MCP connectivity.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from github import Github, GithubException

# Import the existing MCP tools
from gitmcp import (
    list_repos, create_repo, delete_repo, get_repo_structure, read_file,
    edit_file, write_file, batch_update_files, create_branch, search_code,
    create_pull_request, delete_file, delete_files_batch, create_folder,
    delete_folder, move_file, move_files_batch, update_repo_settings
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GitMCP Remote Server",
    description="Remote MCP server for GitHub integration with Anthropic's Integrations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Global GitHub client cache
github_clients: Dict[str, Github] = {}

def get_github_client(token: str) -> Github:
    """Get or create a GitHub client for the given token"""
    if token not in github_clients:
        try:
            client = Github(token)
            # Test the connection
            client.get_user()
            github_clients[token] = client
        except Exception as e:
            logger.error(f"Failed to authenticate GitHub token: {e}")
            raise HTTPException(status_code=401, detail="Invalid GitHub token")
    return github_clients[token]

async def get_current_user(request: Request):
    """Extract and validate the GitHub token from the request"""
    token = None
    
    # Try to get token from Authorization header
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
    elif auth_header:
        token = auth_header
    
    # Try to get token from the request body for MCP calls
    if not token:
        try:
            body = await request.body()
            if body:
                import json
                data = json.loads(body)
                # Look for authorization_token in MCP server config
                if isinstance(data, dict) and "authorization_token" in data:
                    token = data["authorization_token"]
        except:
            pass
    
    # Fallback to environment variable for development
    if not token:
        token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        raise HTTPException(status_code=401, detail="GitHub token required")
    
    # Validate the token by creating a GitHub client
    try:
        client = get_github_client(token)
        user = client.get_user()
        return {
            "token": token,
            "username": user.login,
            "client": client
        }
    except Exception as e:
        logger.error(f"Auth failed for token: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# MCP Protocol Implementation
class MCPMessage:
    """MCP message structure"""
    def __init__(self, method: str, params: Dict[str, Any] = None, id: str = None):
        self.method = method
        self.params = params or {}
        self.id = id

    def to_dict(self):
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.id
        }

class MCPResponse:
    """MCP response structure"""
    def __init__(self, result: Any = None, error: Any = None, id: str = None):
        self.result = result
        self.error = error
        self.id = id

    def to_dict(self):
        response = {"jsonrpc": "2.0", "id": self.id}
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response

# MCP Tools Registry
MCP_TOOLS = {
    "list_repos": list_repos,
    "create_repo": create_repo,
    "delete_repo": delete_repo,
    "get_repo_structure": get_repo_structure,
    "read_file": read_file,
    "edit_file": edit_file,
    "write_file": write_file,
    "batch_update_files": batch_update_files,
    "create_branch": create_branch,
    "search_code": search_code,
    "create_pull_request": create_pull_request,
    "delete_file": delete_file,
    "delete_files_batch": delete_files_batch,
    "create_folder": create_folder,
    "delete_folder": delete_folder,
    "move_file": move_file,
    "move_files_batch": move_files_batch,
    "update_repo_settings": update_repo_settings,
}

def setup_github_env(token: str):
    """Setup GitHub environment for the existing tools"""
    os.environ["GITHUB_TOKEN"] = token

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": "GitMCP Remote Server",
        "version": "1.0.0",
        "status": "running",
        "protocol": "MCP",
        "endpoints": {
            "sse": "/mcp/sse",
            "http": "/mcp/http",
            "tools": "/mcp/tools"
        }
    }

@app.get("/mcp/tools")
async def list_tools(user=Depends(get_current_user)):
    """List available MCP tools"""
    tools = []
    for tool_name, tool_func in MCP_TOOLS.items():
        # Get tool metadata from the function
        doc = tool_func.__doc__ or ""
        tools.append({
            "name": tool_name,
            "description": doc.strip().split('\n')[0] if doc else f"Execute {tool_name}",
            "parameters": getattr(tool_func, '_mcp_schema', {})
        })
    
    return {
        "tools": tools,
        "user": user["username"]
    }

@app.post("/mcp/http")
async def mcp_http_handler(request: Request):
    """Handle MCP requests via HTTP"""
    try:
        # Read the request body
        body = await request.json()
        
        # Extract token from request (try multiple methods)
        token = None
        
        # Method 1: From Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            else:
                token = auth_header
        
        # Method 2: From X-API-Key header (alternative)
        if not token:
            token = request.headers.get("x-api-key")
        
        # Method 3: Fallback to environment
        if not token:
            token = os.getenv("GITHUB_TOKEN")
        
        if not token:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32002, "message": "GitHub token required"},
                "id": body.get("id")
            }
        
        # Setup GitHub environment
        setup_github_env(token)
        
        # Validate token
        try:
            client = get_github_client(token)
            user = client.get_user()
        except Exception as e:
            return {
                "jsonrpc": "2.0", 
                "error": {"code": -32002, "message": f"Invalid GitHub token: {str(e)}"},
                "id": body.get("id")
            }
        
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        if method == "tools/list":
            # Return available tools
            tools = []
            for tool_name, tool_func in MCP_TOOLS.items():
                doc = tool_func.__doc__ or ""
                description = doc.strip().split('\n')[0] if doc else f"Execute {tool_name}"
                tools.append({
                    "name": tool_name,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True
                    }
                })
            
            return {
                "jsonrpc": "2.0",
                "result": {"tools": tools},
                "id": request_id
            }
        
        elif method == "tools/call":
            # Execute a tool
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name not in MCP_TOOLS:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                    "id": request_id
                }
            
            try:
                # Execute the tool
                result = MCP_TOOLS[tool_name](**tool_args)
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [
                            {
                                "type": "text", 
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    },
                    "id": request_id
                }
            
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": f"Tool execution failed: {str(e)}"},
                    "id": request_id
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }
    
    except Exception as e:
        logger.error(f"Request processing error: {e}")
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            "id": None
        }

@app.get("/mcp/sse")
async def mcp_sse_handler(user=Depends(get_current_user)):
    """Handle MCP requests via Server-Sent Events (SSE)"""
    
    async def event_stream():
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected', 'user': user['username']})}\n\n"
        
        # Keep connection alive
        while True:
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.post("/oauth/github")
async def github_oauth_handler(request: Request):
    """Handle GitHub OAuth callback (for future OAuth implementation)"""
    body = await request.json()
    code = body.get("code")
    
    if not code:
        raise HTTPException(status_code=400, detail="OAuth code required")
    
    # TODO: Implement full OAuth flow
    # For now, return instructions to use personal access token
    return {
        "message": "OAuth flow not fully implemented yet",
        "instructions": "Please use a GitHub Personal Access Token for authentication",
        "token_url": "https://github.com/settings/tokens"
    }

# Anthropic Integration Endpoints
@app.get("/.well-known/mcp-server")
async def mcp_server_manifest():
    """MCP server manifest for Anthropic integrations discovery"""
    return {
        "name": "GitMCP",
        "version": "1.0.0",
        "description": "GitHub integration for AI assistants via MCP",
        "author": "ProCreations-Official",
        "homepage": "https://github.com/ProCreations-Official/gitmcp",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False
        },
        "protocols": ["http", "sse"],
        "endpoints": {
            "http": "/mcp/http",
            "sse": "/mcp/sse"
        },
        "authentication": {
            "type": "bearer",
            "description": "GitHub Personal Access Token"
        }
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting GitMCP Remote Server on {host}:{port}")
    logger.info("Endpoints available:")
    logger.info(f"  - Health check: http://{host}:{port}/")
    logger.info(f"  - MCP HTTP: http://{host}:{port}/mcp/http")
    logger.info(f"  - MCP SSE: http://{host}:{port}/mcp/sse")
    logger.info(f"  - Tools list: http://{host}:{port}/mcp/tools")
    
    uvicorn.run(
        "remote_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
