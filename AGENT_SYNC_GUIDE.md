# Agent Synchronization Guide

## Overview

The simulation writes a `sim_state.json` file that agents can monitor to synchronize their actions with the simulation timeline. This is the **recommended method** for agent integration.

## The State File: `sim_state.json`

### Location
The file is created in the same directory as `run_simulation.py`.

### Format
```json
{
  "simulation": {
    "date": "2026-03-15",
    "time": "17:00:00",
    "datetime": "2026-03-15 17:00:00",
    "day_number": 15,
    "total_days": 30,
    "status": "day_complete",
    "progress_percent": 50.0
  },
  "operations": {
    "disabled": ["restock", "payroll"],
    "pending": ["restock"]
  },
  "metadata": {
    "last_update": "2026-02-13T10:17:32.251413",
    "state_version": "1.0"
  }
}
```

### Fields Explained

**simulation** section:
- `date`: Current simulation date (YYYY-MM-DD)
- `time`: Current simulation time (HH:MM:SS)
- `datetime`: Combined date and time
- `day_number`: Current day (1-indexed)
- `total_days`: Total days in simulation
- `status`: Current status (see below)
- `progress_percent`: Completion percentage

**operations** section:
- `disabled`: List of operations replaced by agents
- `pending`: Operations that need to be performed NOW by agents

**metadata** section:
- `last_update`: Real-world timestamp when file was updated
- `state_version`: State file format version

### Status Values

| Status | Meaning | When to Act |
|--------|---------|-------------|
| `initializing` | Simulation starting up | Wait |
| `running` | Day operations in progress | Check pending operations |
| `day_complete` | All operations done for day | Agents can do end-of-day tasks |
| `finished` | Simulation completed | Final cleanup |
| `interrupted` | User stopped simulation | Handle gracefully |
| `error` | Simulation error occurred | Log and exit |

## Using the State File

### Method 1: Direct File Monitoring (Simplest)

```python
import json
import time
from pathlib import Path

def watch_simulation():
    """Simple file watching loop."""
    state_file = Path("sim_state.json")
    last_day = 0

    while True:
        if not state_file.exists():
            time.sleep(1)
            continue

        with open(state_file) as f:
            state = json.load(f)

        current_day = state["simulation"]["day_number"]
        status = state["simulation"]["status"]

        # Detect new day
        if current_day > last_day:
            print(f"New day: {state['simulation']['date']}")
            last_day = current_day

            # Check for pending operations
            for op in state["operations"]["pending"]:
                print(f"Need to handle: {op}")
                # Call your handler function

        # Exit if simulation done
        if status in ["finished", "interrupted", "error"]:
            break

        time.sleep(0.5)
```

### Method 2: Using SimulationState Class (Recommended)

```python
from sim_state import SimulationState
import subprocess

class MyAgent:
    def __init__(self):
        self.state = SimulationState()

    def run(self):
        # Wait for simulation to start
        while True:
            state = self.state.read_state()
            if state and state["simulation"]["status"] != "initializing":
                break
            time.sleep(0.5)

        # Monitor each day
        total_days = state["simulation"]["total_days"]

        for day in range(1, total_days + 1):
            # Wait for day operations to start
            self.state.wait_for_status("running", timeout=30)

            # Check what needs to be done
            pending = self.state.get_pending_operations()

            for operation in pending:
                if operation == "restock":
                    self.handle_restock()
                elif operation == "process":
                    self.handle_process()
                # etc.

            # Wait for day to complete
            self.state.wait_for_status("day_complete", timeout=300)
```

### Method 3: Event-Driven with inotify (Advanced)

```python
import inotify.adapters

def watch_state_file_events():
    """Watch for file modifications using inotify."""
    i = inotify.adapters.Inotify()
    i.add_watch('.')

    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event

        if filename == "sim_state.json" and "IN_MODIFY" in type_names:
            # File was modified - read and process
            state = read_state()
            process_state(state)
```

## Complete Example: Synchronized Restock Agent

```python
#!/usr/bin/env python3
"""Agent that handles inventory restocking when disabled."""

import time
import subprocess
from sim_state import SimulationState

class RestockAgent:
    def __init__(self):
        self.state = SimulationState()
        self.restock_count = 0

    def handle_restock(self, sim_date):
        """Execute inventory restocking."""
        print(f"🤖 AGENT: Restocking inventory for {sim_date}")

        result = subprocess.run(
            ['./venv/bin/python', 'update_inventory.py', sim_date],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            self.restock_count += 1
            print(f"🤖 AGENT: ✓ Restock #{self.restock_count} completed")
        else:
            print(f"🤖 AGENT: ✗ Restock failed")

    def run(self):
        """Main agent loop."""
        print("🤖 AGENT: Starting synchronized restock agent...")

        # Wait for simulation to initialize
        while True:
            state = self.state.read_state()
            if state and state["simulation"]["status"] != "initializing":
                break
            time.sleep(0.5)

        print(f"🤖 AGENT: Monitoring {state['simulation']['total_days']} days")

        # Monitor simulation
        last_day = 0

        while True:
            state = self.state.read_state()
            if not state:
                time.sleep(0.5)
                continue

            current_day = state["simulation"]["day_number"]
            status = state["simulation"]["status"]

            # Check for pending restock operations
            if "restock" in state["operations"]["pending"] and current_day > last_day:
                self.handle_restock(state["simulation"]["date"])
                last_day = current_day

            # Exit if simulation complete
            if status in ["finished", "interrupted", "error"]:
                print(f"🤖 AGENT: Simulation ended - performed {self.restock_count} restocks")
                break

            time.sleep(1)

if __name__ == "__main__":
    agent = RestockAgent()
    agent.run()
```

## Running Agents with Simulation

### Terminal 1: Start Simulation
```bash
./venv/bin/python run_simulation.py 30 "2026-03-01" --disable restock --step
```

### Terminal 2: Start Agent
```bash
python my_restock_agent.py
```

The agent will automatically:
1. Wait for simulation to initialize
2. Monitor `sim_state.json` for changes
3. Execute restocking when `pending` contains "restock"
4. Exit when simulation finishes

## Pre-Built Example

We provide a complete synchronized agent example:

```bash
# Terminal 1
./venv/bin/python run_simulation.py 7 "2026-03-01" --disable restock --disable payroll --step

# Terminal 2
./venv/bin/python sync_agent_example.py
```

The example agent (`sync_agent_example.py`) demonstrates:
- Waiting for simulation start
- Monitoring day progression
- Handling multiple operation types
- Proper synchronization
- Clean shutdown

## Best Practices

### 1. Always Check Status
```python
state = read_state()
if state["simulation"]["status"] == "running":
    # Safe to take action
```

### 2. Handle Missing File
```python
from pathlib import Path

state_file = Path("sim_state.json")
if not state_file.exists():
    print("Waiting for simulation to start...")
    time.sleep(1)
```

### 3. Use Timeouts
```python
# Don't wait forever
state.wait_for_status("running", timeout=30)
```

### 4. Handle Errors Gracefully
```python
try:
    state = self.state.read_state()
except json.JSONDecodeError:
    # File is being written, try again
    time.sleep(0.1)
    continue
```

### 5. Log All Actions
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

logger.info(f"Handled restock for day {day}")
```

## Debugging

### View State in Real-Time
```bash
# In a third terminal
watch -n 0.5 cat sim_state.json
```

### Check Last Update
```python
from datetime import datetime

last_update = datetime.fromisoformat(state["metadata"]["last_update"])
age = (datetime.now() - last_update).total_seconds()

if age > 60:
    print("Warning: State file is stale!")
```

### Validate State
```python
def validate_state(state):
    """Check if state is valid."""
    required_keys = ["simulation", "operations", "metadata"]
    return all(key in state for key in required_keys)
```

## Comparison with Other Methods

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **State File** ✅ | Simple, reliable, decoupled | File I/O overhead | Most use cases |
| Named Pipe | Direct control | Complex setup | Advanced control |
| Database Polling | Direct data access | High overhead | Data analysis |
| File Watching (inotify) | Instant notification | Platform-specific | Real-time needs |

## State File Lifecycle

```
Simulation Start
    ↓
sim_state.json created (status: initializing)
    ↓
For each day:
    ↓
Update state (status: running, pending: [...])
    ← Agent reads and acts
    ↓
Update state (status: day_complete)
    ↓
Next day...
    ↓
Final update (status: finished)
    ↓
Agent exits
```

## Summary

✅ **Use the state file** - It's the cleanest way to sync agents
✅ **Monitor `pending` operations** - Know exactly when to act
✅ **Check `status`** - Ensure simulation is in correct state
✅ **Handle all statuses** - Don't just check for "running"
✅ **Use provided examples** - `sync_agent_example.py` as a template

The state file approach gives you:
- 🎯 **Perfect timing** - Know exactly when operations happen
- 🔄 **Reliable synchronization** - No race conditions
- 📊 **Full visibility** - See simulation progress
- 🛠️ **Easy debugging** - Human-readable JSON
- 🤝 **Loose coupling** - Agents independent of simulation

Happy agent building! 🤖
