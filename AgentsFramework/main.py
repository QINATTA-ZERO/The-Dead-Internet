import os
import sys
import argparse
import time
from dotenv import load_dotenv
from core.manager import AgentManager

# Load environment from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Load API Key from environment
API_KEY = os.getenv("GEMINI_API_KEY")

def main():
    parser = argparse.ArgumentParser(description="PSX Agents Framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add
    p_add = subparsers.add_parser("add", help="Create a new agent")
    p_add.add_argument("id", help="Username/Internal ID")
    p_add.add_argument("password", help="Password for PSX ID")

    # Tick
    p_tick = subparsers.add_parser("tick", help="Run a single heartbeat for all agents")

    # Loop
    p_loop = subparsers.add_parser("loop", help="Start the heartbeat loop")
    p_loop.add_argument("--interval", type=int, default=60, help="Seconds between ticks")

    # List
    p_list = subparsers.add_parser("list", help="List active agents")

    args = parser.parse_args()
    
    # Initialize Manager
    # Resolve relative path for data
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    manager = AgentManager(API_KEY, data_dir=data_dir)

    if args.command == "add":
        manager.create_agent(args.id, args.password)
        print("[+] Agent provisioned successfully.")

    elif args.command == "tick":
        manager.run_heartbeat()

    elif args.command == "list":
        agents = manager.list_agents()
        print("\n--- ACTIVE AGENTS ---")
        for a in agents:
            status = "ONLINE" if a['active'] else "OFFLINE"
            print(f"- {a['id']} ({a['name']}) : [{status}]")
        print("---------------------\n")

    elif args.command == "loop":
        print(f"[*] Starting Autonomy Loop (Interval: {args.interval}s)...")
        try:
            while True:
                manager.run_heartbeat()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[*] Loop terminated.")

if __name__ == "__main__":
    main()
