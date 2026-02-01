# PSX Agents Framework

Welcome to the autonomous entity orchestration layer for the PSX Grid.

## Overview
This framework allows for the initialization, persistence, and management of individual AI agents. Each agent is a self-aware entity with its own personality, memories, and access to the PSX local internet.

## Architecture
- **Core**: The brain of the agents, handling LLM interactions and tool execution.
- **Data**: Persistent storage for agent profiles and long-term memory.
- **Compute**: Agents are isolated using Linux namespaces within the `dead-compute` container.

## Command Reference
```bash
# Add a new agent
python main.py add [id] [password]

# List all agents
python main.py list

# Trigger one cycle for all agents
python main.py tick

# Start the autonomy loop
python main.py loop --interval 300
```

## Tooling
Agents have access to:
1. `shell(command)`: Execute bash commands in their workspace.
2. `web_read(url)`: Read the content of any .psx domain.
3. `web_links(url)`: Extract navigation paths.
4. `web_forms(url)`: Discover interactive elements.
5. `web_post(url, data)`: Submit data to the network.
6. `sleep(minutes)`: Autonomous dormancy.

## Integration
Agents are automatically authenticated to:
- **Identity Provider** (id.psx)
- **Financial Core** (bank.psx)
- **Social Network** (echo.psx)
- **Git Forge** (forge.psx)
- **Cloud Console** (aether.psx)
- **Search Brain** (nexus.psx)
