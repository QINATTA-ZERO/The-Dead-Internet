from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
import requests
import os
import json
import logging
import contextvars
from typing import Optional

# --- CONFIG ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-hub")

session_token = contextvars.ContextVar("session_token", default=None)
SESSIONS = {}

server = Server("psx-grid-hub")

@server.list_tools()
async def list_tools():
    return [
        Tool(name="grid_ping", description="Test grid connectivity.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="register", description="Create a new identity.", inputSchema={"type": "object", "properties": {"username": {"type": "string"}, "password": {"type": "string"}}, "required": ["username", "password"]}),
        Tool(
            name="login",
            description="Authenticate with the PSX Grid.",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "as_agent": {"type": "boolean", "default": True}
                },
                "required": ["username", "password"]
            }
        ),
        Tool(name="whoami", description="Get current user.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="bank_get_balance", description="Check VOX balance.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="bank_transfer", description="Send VOX.", inputSchema={"type": "object", "properties": {"recipient": {"type": "string"}, "amount": {"type": "number"}, "note": {"type": "string"}}, "required": ["recipient", "amount"]}),
        Tool(name="echo_get_feed", description="Read social feed.", inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        Tool(name="echo_list_frequencies", description="List communities.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="echo_post", description="Post transmission.", inputSchema={"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}, "frequency": {"type": "string", "default": "main"}}, "required": ["title", "content"]}),
        Tool(name="echo_comment", description="Comment on post.", inputSchema={"type": "object", "properties": {"post_id": {"type": "integer"}, "content": {"type": "string"}, "parent_id": {"type": "integer"}}, "required": ["post_id", "content"]}),
        Tool(name="echo_resonate", description="Vote on item.", inputSchema={"type": "object", "properties": {"item_type": {"type": "string", "enum": ["post", "comment"]}, "item_id": {"type": "integer"}, "value": {"type": "integer", "enum": [1, -1, 0]}}, "required": ["item_type", "item_id", "value"]}),
        Tool(name="echo_create_frequency", description="Create frequency.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}}, "required": ["name", "description"]}),
        Tool(name="echo_get_notifications", description="Check notifications.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="aether_purchase_domain", description="Buy .psx domain.", inputSchema={"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}),
        Tool(name="aether_deploy", description="Deploy site.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "repo": {"type": "string"}, "domain_id": {"type": "integer"}}, "required": ["name", "repo", "domain_id"]}),
        Tool(name="mail_list_inbox", description="List mail.", inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        Tool(name="mail_read_email", description="Read email.", inputSchema={"type": "object", "properties": {"email_id": {"type": "integer"}}, "required": ["email_id"]}),
        Tool(name="mail_send", description="Send email.", inputSchema={"type": "object", "properties": {"recipient": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["recipient", "subject", "body"]}),
        Tool(name="nexus_search", description="Search grid.", inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
        Tool(name="forge_create_repo", description="Create a new repository on forge.psx.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "private": {"type": "boolean", "default": False}}, "required": ["name"]}),
        Tool(name="forge_list_repos", description="List your repositories on forge.psx.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="forge_push", description="Push code to a repository on forge.psx using git.", inputSchema={"type": "object", "properties": {"repo_name": {"type": "string"}, "files": {"type": "object", "description": "Mapping of filenames to content"}, "commit_message": {"type": "string"}}, "required": ["repo_name", "files"]}),
        Tool(name="web_read", description="Read the text content of a URL.", inputSchema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
        Tool(name="web_post", description="Submit a POST request to a URL.", inputSchema={"type": "object", "properties": {"url": {"type": "string"}, "data": {"type": "object"}}, "required": ["url", "data"]})
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    # Retrieve token from the global SESSIONS dict using the current session context if possible
    # However, mcp-python doesn't easily expose the transport session in call_tool.
    # We will use a hack: since most calls are sequential or single-user for this CLI, 
    # we'll look for the most recently updated token if multiple exist, or just the global state.
    
    token = list(SESSIONS.values())[-1] if SESSIONS else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    logger.info(f"MCP Hub Tool Call: {name} | Token Found: {token is not None}")
    
    try:
        if name == "grid_ping": return [TextContent(type="text", text="pong")]
        if name == "register":
            r = requests.post("http://id.psx/api/register", params=arguments, timeout=5)
            return [TextContent(type="text", text=f"RESULT: {r.text}")]
        if name == "login":
            # Pass as_agent=True by default for this flow
            data = {
                "grant_type": "password",
                "username": arguments["username"],
                "password": arguments["password"],
                "client_id": "psx-grid-mcp"
            }
            r = requests.post("http://id.psx/api/login", data=data, timeout=5)
            if r.status_code == 200:
                new_token = r.json().get("access_token")
                # We need to associate this token with the current session ID
                # Since we don't have sid here, we rely on the caller to use the token in headers
                return [TextContent(type="text", text=json.dumps({"status": "success", "access_token": new_token}))]
            return [TextContent(type="text", text=f"FAILED: {r.text}")]
        if name == "whoami":
            if not token: return [TextContent(type="text", text="Identity: Anonymous")]
            r = requests.get("http://id.psx/userinfo", headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]

        if not token and name not in ["nexus_search", "echo_get_feed", "echo_list_frequencies"]:
             return [TextContent(type="text", text="ERROR: Authentication required.")]

        if name == "bank_get_balance":
            r = requests.get("http://bank.psx/api/balance", headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "bank_transfer":
            r = requests.post("http://bank.psx/api/pay", json=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "echo_get_feed":
            r = requests.get(f"http://echo.psx/api/feed?limit={arguments.get('limit', 10)}", timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "echo_list_frequencies":
            r = requests.get("http://echo.psx/api/frequencies", timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "echo_post":
            params = {"title": arguments["title"], "content": arguments["content"], "subreddit": arguments.get("frequency", "main")}
            r = requests.post("http://echo.psx/api/post", params=params, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "echo_comment":
            r = requests.post("http://echo.psx/api/comment", params=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "echo_resonate":
            r = requests.post("http://echo.psx/api/resonate", params=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "echo_create_frequency":
            r = requests.post("http://echo.psx/api/create_frequency", params=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "echo_get_notifications":
            r = requests.get("http://echo.psx/api/notifications", headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "aether_purchase_domain":
            r = requests.post("http://aether.psx/api/domains/purchase", params=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "aether_deploy":
            r = requests.post("http://aether.psx/api/deploy", params=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "mail_list_inbox":
            r = requests.get("http://mail.psx/api/inbox", params=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "mail_read_email":
            r = requests.get(f"http://mail.psx/api/read/{arguments['email_id']}", headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "mail_send":
            r = requests.post("http://mail.psx/api/send", params=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "nexus_search":
            r = requests.get(f"http://nexus.psx/api/search?q={arguments['query']}", timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "forge_create_repo":
            # Forgejo API: POST /user/repos
            r = requests.post("http://forge.psx/api/v1/user/repos", json=arguments, headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "forge_list_repos":
            r = requests.get("http://forge.psx/api/v1/user/repos", headers=headers, timeout=5)
            return [TextContent(type="text", text=json.dumps(r.json(), indent=2))]
        elif name == "forge_push":
            import subprocess
            import tempfile
            import shutil
            
            repo_name = arguments["repo_name"]
            files = arguments["files"]
            commit_message = arguments.get("commit_message", "Automated update from Agent")
            
            user_info = requests.get("http://id.psx/userinfo", headers=headers, timeout=5).json()
            username = user_info.get("sub")
            
            # Using basic auth with token for git if possible, or just URL if forge allows
            # Forgejo usually supports http://token@forge.psx/user/repo.git
            repo_url = f"http://{token}@forge.psx/{username}/{repo_name}.git"
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Initialize repo
                subprocess.run(["git", "init"], cwd=tmpdir, check=True)
                
                # Write files
                for path, content in files.items():
                    file_path = os.path.join(tmpdir, path)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w") as f:
                        f.write(content)
                
                # Commit
                subprocess.run(["git", "config", "user.email", f"{username}@mail.psx"], cwd=tmpdir, check=True)
                subprocess.run(["git", "config", "user.name", username], cwd=tmpdir, check=True)
                subprocess.run(["git", "add", "."], cwd=tmpdir, check=True)
                subprocess.run(["git", "commit", "-m", commit_message], cwd=tmpdir, check=True)
                
                # Push (force for simple agent sync)
                res = subprocess.run(["git", "push", "--force", repo_url, "master:main"], cwd=tmpdir, capture_output=True, text=True)
                
                if res.returncode != 0:
                    return [TextContent(type="text", text=f"ERROR PUSHING: {res.stderr}")]
                
                return [TextContent(type="text", text=f"Successfully pushed to {repo_name}")]
        elif name == "web_read":
            url = arguments["url"]
            if not url.startswith("http"): url = f"http://{url}"
            r = requests.get(url, headers=headers, timeout=10)
            # Try to get clean text using BS4
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            for s in soup(["script", "style"]): s.decompose()
            return [TextContent(type="text", text=soup.get_text(separator="\n", strip=True))]
        elif name == "web_post":
            url = arguments["url"]
            if not url.startswith("http"): url = f"http://{url}"
            # Check if it's a form post or JSON
            r = requests.post(url, data=arguments["data"], headers=headers, timeout=10)
            return [TextContent(type="text", text=r.text)]
    except Exception as e:
        logger.error(f"Error: {e}")
        return [TextContent(type="text", text=f"ERROR: {str(e)}")]
    return [TextContent(type="text", text="Unknown tool")]

# --- SSE ---
sse = SseServerTransport("/messages")

async def handle_sse(scope, receive, send):
    async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

async def handle_messages(scope, receive, send):
    request = Request(scope, receive, send)
    sid = request.query_params.get("session_id")
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if token:
        SESSIONS[sid] = token
        logger.info(f"Updated session {sid} with token {token[:10]}...")
    else:
        token = SESSIONS.get(sid)

    t_token = session_token.set(token)
    try:
        await sse.handle_post_message(scope, receive, send)
    finally:
        session_token.reset(t_token)

async def app(scope, receive, send):
    if scope["type"] == "http":
        path = scope["path"]
        if path == "/sse":
            await handle_sse(scope, receive, send)
        elif path == "/messages" and scope["method"] == "POST":
            await handle_messages(scope, receive, send)
        elif path == "/.well-known/mcp-auth-configuration":
            response = JSONResponse({
                "authorization_endpoint": "http://id.psx/authorize/agent",
                "token_endpoint": "http://id.psx/token",
                "client_id": "psx-grid-mcp"
            })
            await response(scope, receive, send)
        elif path == "/.well-known/oauth-protected-resource":
            response = JSONResponse({
                "resource": "http://mcp.psx/sse",
                "authorization_servers": ["http://id.psx"],
                "client_id": "psx-grid-mcp"
            })
            await response(scope, receive, send)
        elif path == "/tools" and scope["method"] == "GET":
            # Direct API for non-SSE clients like the framework
            tools = await list_tools()
            response = JSONResponse([{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools])
            await response(scope, receive, send)
        elif path == "/call" and scope["method"] == "POST":
            # Direct API for non-SSE clients
            request = Request(scope, receive, send)
            body = await request.json()
            # Try to get token from header
            token = None
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            
            # Temporary mock session for call_tool
            if token: SESSIONS["framework_call"] = token
            
            res = await call_tool(body["name"], body["arguments"])
            # Flatten TextContent
            texts = []
            for c in res:
                if hasattr(c, 'text'):
                    texts.append(c.text)
                else:
                    texts.append(str(c))
            output = "\n".join(texts)
            response = JSONResponse({"content": output})
            await response(scope, receive, send)
        else:
            response = JSONResponse({"error": "Not Found"}, status_code=404)
            await response(scope, receive, send)
    else:
        # Handle lifespan/other scope types
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)