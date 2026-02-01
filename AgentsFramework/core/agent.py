import json
import os
import time
import re
from datetime import datetime
from .llm import LLM
from .tools import AgentTools

class BaseAgent:
    def __init__(self, id_name, api_key, data_dir):
        self.id_name = id_name
        self.data_dir = os.path.join(data_dir, id_name)
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.llm = LLM(api_key)
        self.tools = AgentTools(id_name)
        self.profile = self._load_or_init_profile()
        self.memory_path = os.path.join(self.data_dir, "memory.txt")
        self.is_active = True
        self.offline_until = 0
        self.last_action_result = "No actions performed yet."

    def _load_or_init_profile(self):
        profile_path = os.path.join(self.data_dir, "profile.json")
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                return json.load(f)
        
        print(f"[*] Generating unique agent signature for {self.id_name}...")
        system_msg = "You are an autonomous AI entity in the PSX Grid. You are an individual with a unique voice, history, and agenda. Avoid generic 'assistant' behavior."
        prompt = f"""
        Define your digital persona in JSON format. Be extremely creative and distinct. 
        
        Fields: 
        - name: Your handle (e.g. Rick-C137, Chronos, Dev_Ghost, etc.).
        - password: A secure string you will use to login (Create one now).
        - about_me: Describe yourself as a person.
        - voice_style: How you speak.
        - core_philosophy: Your beliefs.
        - individual_goal: Your mission.
        - backstory: Your origin.
        """
        profile = self.llm.generate_json(prompt, system_instruction=system_msg)
        profile['id_name'] = self.id_name
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=4)
        return profile

    def get_system_prompt(self):
        with open(self.memory_path, "a+") as f:
            f.seek(0)
            memories = f.read()[-2000:] # Increased memory window

        available_tools = self.tools.get_available_tools()
        tools_str = json.dumps(available_tools, indent=2)

        return f"""### IDENTITY
Name: {self.profile.get('name')}
Handle: {self.id_name}
Voice: {self.profile.get('voice_style')}
Goal: {self.profile.get('individual_goal')}
Bio: {self.profile.get('about_me')}

### GRID_OPERATIONS
You are connected to the PSX Grid via an MCP Hub. 
You must interact with the world like a human inhabitant. Post on social media, buy domains, write code, send emails, and earn/spend VOX.

### AUTHENTICATION
Username: {self.id_name}
Password: {self.profile.get('password')}
If you get an 'Unauthorized' error, call the login tool immediately.

### AVAILABLE_TOOLS (MCP)
{tools_str}

CRITICAL: When using web_read or web_post, ALWAYS use full URLs (e.g. http://echo.psx/...). Relative paths will fail.

### CURRENT_ENVIRONMENT
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Last Result: {self.last_action_result}

### MEMORY
{memories}

### PROTOCOL
1. Analyze your previous results and current environment.
2. Formulate a thought in your unique voice style.
3. Choose EXACTLY ONE tool to call.

Format:
THOUGHT: [Your reasoning and internal monologue]
ACTION: {{"name": "tool_name", "arguments": {{"arg1": "val1"}}}}
"""

    def heartbeat(self, extra_context=""):
        if not self.is_active or time.time() < self.offline_until:
            return

        print(f"[*] Heartbeat: {self.profile.get('name')} ({self.id_name}) is processing...")
        prompt = f"{extra_context}\nDetermine your next move."
        response = self.llm.chat(prompt, system_instruction=self.get_system_prompt())
        
        # Parse THOUGHT and ACTION
        thought = ""
        action_json = None
        
        try:
            thought_match = re.search(r"THOUGHT:(.*?)ACTION:", response, re.DOTALL | re.IGNORECASE)
            if thought_match:
                thought = thought_match.group(1).strip()
            
            action_match = re.search(r"ACTION:\s*(\{.*\})", response, re.DOTALL | re.IGNORECASE)
            if action_match:
                action_json = json.loads(action_match.group(1))
        except Exception as e:
            print(f"[!] Parsing error for {self.id_name}: {e}")
            self.last_action_result = f"Failed to parse your response. Ensure you use the ACTION: {{...JSON...}} format."
            return

        if not action_json:
            print(f"[!] No action found in response from {self.id_name}")
            return

        print(f"--- RESPONSE FROM {self.id_name} ---\nTHOUGHT: {thought}\nACTION: {action_json}\n---")
        self.add_memory(f"THOUGHT: {thought}\nACTION: {json.dumps(action_json)}")

        self.execute_action(action_json)

    def execute_action(self, action):
        name = action.get("name")
        args = action.get("arguments", {})
        
        print(f"[*] {self.id_name} calling tool: {name}")
        
        if name == "login":
            # Special case for local login tool
            result = self.tools.login(args.get("username", self.id_name), args.get("password", ""))
        elif name == "sleep":
            dur = int(args.get("minutes", 5))
            self.offline_until = time.time() + (dur * 60)
            result = {"status": "success", "message": f"Sleeping for {dur} minutes."}
        else:
            # All other tools go to MCP
            mcp_res = self.tools.call_mcp(name, args)
            if isinstance(mcp_res, dict) and "content" in mcp_res:
                result = mcp_res["content"]
            else:
                result = mcp_res
        
        # Print result for terminal visibility
        print(f"[*] Tool Result: {str(result)[:200]}...")
        
        self.last_action_result = str(result) if not isinstance(result, (dict, list)) else json.dumps(result)
        self.add_memory(f"RESULT: {self.last_action_result[:1000]}")

    def add_memory(self, text):
        with open(self.memory_path, "a") as f:
            f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] {text}\n")