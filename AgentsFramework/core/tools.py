import requests
import json
import os

class AgentTools:
    def __init__(self, agent_name, mcp_url="http://mcp.psx"):
        self.agent_name = agent_name
        self.mcp_url = mcp_url
        self.token = None
        self.token_file = f"/tmp/psx_token_{agent_name}"

    def login(self, username, password):
        """Authenticates with the PSX Grid to get a session token."""
        print(f"[*] {self.agent_name} attempting login...")
        try:
            # We use the agent-specific authorization endpoint
            # Since we are outside the container, we need to use 'localhost' if forwarded
            # or rely on the agent framework running in a place that can see 'id.psx'
            # For simplicity, we assume the framework environment can resolve .psx (e.g. it uses the local DNS)
            r = requests.post("http://id.psx/token", data={
                "grant_type": "password",
                "username": username,
                "password": password,
                "client_id": "mcp_hub" # Framework acts as MCP hub client
            }, timeout=10)
            
            if r.status_code == 200:
                self.token = r.json()["access_token"]
                with open(self.token_file, "w") as f:
                    f.write(self.token)
                return {"status": "success", "message": f"Authenticated as {username}"}
            else:
                return {"status": "error", "message": r.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_token(self):
        if self.token: return self.token
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                self.token = f.read().strip()
                return self.token
        return None

    def call_mcp(self, tool_name, arguments):
        """Calls a tool on the MCP server."""
        token = self._get_token()
        if not token and tool_name not in ["login", "register"]:
            return {"error": "Not authenticated. Call login first."}

        try:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            r = requests.post(f"{self.mcp_url}/call", json={
                "name": tool_name,
                "arguments": arguments
            }, headers=headers, timeout=30)
            
            if r.status_code == 200:
                result = r.json()
                # Special handling for login: save the token
                if tool_name == "login":
                    try:
                        # Extract JSON from TextContent string
                        import json
                        login_data = json.loads(result["content"])
                        if login_data.get("status") == "success":
                            self.token = login_data["access_token"]
                            with open(self.token_file, "w") as f:
                                f.write(self.token)
                    except:
                        pass
                return result
            else:
                return {"error": f"MCP Error {r.status_code}: {r.text}"}
        except Exception as e:
            return {"error": str(e)}

    def get_available_tools(self):
        """Fetches the list of tools from the MCP server and adds local tools."""
        tools = []
        try:
            r = requests.get(f"{self.mcp_url}/tools", timeout=5)
            if r.status_code == 200:
                tools = r.json()
        except:
            pass
        
        # Add local tools that the agent framework handles
        tools.append({
            "name": "login",
            "description": "Authenticate with the PSX Grid. Call this if you get an Unauthorized error.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"}
                },
                "required": ["username", "password"]
            }
        })
        tools.append({
            "name": "sleep",
            "description": "Go dormant for a specified number of minutes to save energy.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "default": 5}
                }
            }
        })
        
        return tools