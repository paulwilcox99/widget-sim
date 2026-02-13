# Intelligent Agent Integration Guide

## Overview

The simulator allows you to disable built-in operations and replace them with your own intelligent agents. This is perfect for:
- Testing AI-powered decision making
- Building autonomous business operations
- Experimenting with different strategies
- Benchmarking agent performance

## Disabling Operations

### Available Operations to Disable

| Operation | Flag | When It Runs | What to Replace |
|-----------|------|--------------|-----------------|
| **Order Processing** | `--disable process` | Daily at 10:00 | `process_order.py` - Deduct inventory, start manufacturing |
| **Manufacturing Ops** | `--disable ops` | Daily at 10:00 | `run_ops.py` - Advance production stages, ship orders |
| **Inventory Restocking** | `--disable restock` | Every 3 days | `update_inventory.py` - Check stock, reorder parts |
| **Employee Payroll** | `--disable payroll` | Every Friday | `pay_employees.py` - Pay all employees |

### Usage Examples

```bash
# Disable single operation
./venv/bin/python run_simulation.py 30 --disable restock

# Disable multiple operations
./venv/bin/python run_simulation.py 30 --disable process --disable ops

# Combine with step mode for controlled testing
./venv/bin/python run_simulation.py 7 --step --disable payroll

# Disable everything except order generation
./venv/bin/python run_simulation.py 30 \
  --disable process \
  --disable ops \
  --disable restock \
  --disable payroll
```

## Agent Integration Patterns

### Pattern 1: File Watcher

Your agent watches the simulation and takes action when needed.

```python
import time
import sqlite3
from pathlib import Path
from datetime import datetime

class InventoryAgent:
    """Intelligent agent that manages inventory restocking."""

    def __init__(self, db_dir="databases"):
        self.db_dir = Path(db_dir)
        self.last_check = None

    def should_restock(self):
        """Check if restocking is needed based on intelligent rules."""
        conn = sqlite3.connect(self.db_dir / "inventory.db")
        cursor = conn.cursor()

        # Get parts below threshold
        cursor.execute("""
            SELECT part_name, quantity_available
            FROM inventory_levels
            WHERE quantity_available < 200
        """)

        low_stock = cursor.fetchall()
        conn.close()

        return len(low_stock) > 0

    def restock(self):
        """Execute restocking with intelligent decisions."""
        # Your custom restocking logic here
        # Could use ML to predict demand, optimize order quantities, etc.
        import subprocess
        subprocess.run([
            './venv/bin/python',
            'update_inventory.py',
            datetime.now().strftime('%Y-%m-%d')
        ])

    def run(self):
        """Watch and respond to inventory needs."""
        while True:
            if self.should_restock():
                print("🤖 AGENT: Detected low inventory, restocking...")
                self.restock()
            time.sleep(60)  # Check every minute

# Run in parallel with simulation
# Terminal 1: ./venv/bin/python run_simulation.py 30 --disable restock --step
# Terminal 2: python your_agent.py
```

### Pattern 2: Named Pipe Control

Agent controls simulation flow through a named pipe.

```bash
# Setup named pipe
mkfifo /tmp/sim_control

# Start simulation (controlled by agent)
./venv/bin/python run_simulation.py 30 \
  --disable process \
  --step \
  < /tmp/sim_control &

# Your agent script
python agent_controller.py
```

```python
# agent_controller.py
import time
import subprocess

class SimulationController:
    """Agent that controls simulation and replaces operations."""

    def __init__(self):
        self.pipe = open('/tmp/sim_control', 'w')
        self.day = 0

    def process_orders_intelligently(self):
        """Your intelligent order processing logic."""
        # Analyze which orders to process
        # Optimize inventory usage
        # Prioritize high-value orders
        # etc.
        subprocess.run([
            './venv/bin/python',
            'process_order.py',
            f'2026-03-{self.day:02d} 10:00:00'
        ])

    def advance_day(self):
        """Advance simulation to next day."""
        self.day += 1
        self.pipe.write('\n')
        self.pipe.flush()

    def run(self):
        """Run agent-controlled simulation."""
        for day in range(1, 31):
            time.sleep(2)  # Wait for day operations

            # Your intelligent decision making
            self.process_orders_intelligently()

            # Advance to next day
            self.advance_day()

        self.pipe.close()
```

### Pattern 3: API Server

Run simulation as a service with agents calling APIs.

```python
from flask import Flask, request
import subprocess
import threading

app = Flask(__name__)
simulation_thread = None

@app.route('/operations/process', methods=['POST'])
def process_orders():
    """API endpoint for agent to trigger order processing."""
    date_time = request.json.get('datetime')
    result = subprocess.run([
        './venv/bin/python',
        'process_order.py',
        date_time
    ], capture_output=True, text=True)
    return {'status': 'success', 'output': result.stdout}

@app.route('/operations/restock', methods=['POST'])
def restock_inventory():
    """API endpoint for agent to trigger restocking."""
    date = request.json.get('date')
    # Your intelligent restocking logic
    result = subprocess.run([
        './venv/bin/python',
        'update_inventory.py',
        date
    ], capture_output=True, text=True)
    return {'status': 'success', 'output': result.stdout}

@app.route('/operations/advance', methods=['POST'])
def advance_simulation():
    """API endpoint to advance simulation day."""
    # Send to simulation control pipe
    with open('/tmp/sim_control', 'w') as f:
        f.write('\n')
    return {'status': 'advanced'}

if __name__ == '__main__':
    # Start simulation in background
    # Terminal 1: ./venv/bin/python run_simulation.py 30 --disable process --disable restock --step < /tmp/sim_control
    # Terminal 2: python api_server.py

    app.run(port=5000)
```

## Use Cases

### 1. ML-Based Inventory Management

```python
class MLInventoryAgent:
    """Use machine learning to optimize inventory levels."""

    def predict_demand(self, part_name):
        """Predict future demand using historical data."""
        # Your ML model here
        pass

    def optimize_order_quantity(self, part_name, current_stock):
        """Calculate optimal order quantity."""
        predicted_demand = self.predict_demand(part_name)
        lead_time = 3  # days
        safety_stock = predicted_demand * 0.2

        order_qty = max(0, predicted_demand * lead_time + safety_stock - current_stock)
        return order_qty

    def restock(self):
        """Smart restocking based on predictions."""
        # Custom implementation using ML
        pass
```

### 2. Dynamic Pricing Agent

```python
class PricingAgent:
    """Dynamically adjust order prices based on demand."""

    def calculate_optimal_price(self, widget_type, inventory_level):
        """Calculate price based on supply/demand."""
        base_cost = self.get_widget_cost(widget_type)

        # Higher prices when inventory is low
        if inventory_level < 100:
            markup = 0.40  # 40% margin
        else:
            markup = 0.25  # 25% margin

        return base_cost / (1 - markup)
```

### 3. Workflow Optimization Agent

```python
class WorkflowAgent:
    """Optimize order processing workflow."""

    def prioritize_orders(self):
        """Intelligent order prioritization."""
        # Sort by:
        # - High value customers
        # - Urgent delivery dates
        # - Inventory availability
        # - Profit margins
        pass

    def batch_processing(self):
        """Process orders in optimized batches."""
        # Group similar orders
        # Minimize setup times
        # Optimize resource utilization
        pass
```

## Testing Your Agent

### 1. Start Simple
```bash
# Test with one disabled operation
./venv/bin/python run_simulation.py 7 --step --disable restock

# Manually trigger your agent when needed
./venv/bin/python your_agent.py
```

### 2. Add Monitoring
```python
from example_monitor import DatabaseMonitor

monitor = DatabaseMonitor()
monitor.capture_baseline()

# After your agent acts
changes = monitor.analyze_changes()
valid = monitor.check_invariants()

if not valid:
    print("Agent caused data integrity issues!")
```

### 3. Benchmark Performance
```bash
# Run baseline (no agents)
./venv/bin/python run_simulation.py 30 "2026-03-01"
# Note: Revenue, costs, efficiency

# Run with your agent
./venv/bin/python run_simulation.py 30 "2026-03-01" --disable restock
python your_agent.py
# Compare: Did your agent improve performance?
```

## Example: Complete Agent Implementation

```python
#!/usr/bin/env python3
"""
intelligent_restock_agent.py - ML-powered inventory management
"""

import time
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

class IntelligentRestockAgent:
    """Agent that replaces inventory restocking with intelligent decisions."""

    def __init__(self, db_dir="databases"):
        self.db_dir = Path(db_dir)
        self.restock_count = 0

    def analyze_inventory(self):
        """Analyze current inventory status."""
        conn = sqlite3.connect(self.db_dir / "inventory.db")
        cursor = conn.cursor()

        # Get critical parts
        cursor.execute("""
            SELECT part_name, quantity_available
            FROM inventory_levels
            WHERE quantity_available < 300
            ORDER BY quantity_available
        """)

        critical_parts = cursor.fetchall()
        conn.close()

        return critical_parts

    def decide_restock(self):
        """Make intelligent decision about restocking."""
        critical_parts = self.analyze_inventory()

        if not critical_parts:
            print("🤖 AGENT: Inventory levels healthy, no action needed")
            return False

        print(f"🤖 AGENT: Found {len(critical_parts)} parts below threshold")
        for part, qty in critical_parts[:5]:
            print(f"   - {part}: {qty} units")

        # Intelligent decision
        # Could use ML model, historical data, demand forecasting, etc.
        urgency_score = sum(1 for _, qty in critical_parts if qty < 100)

        if urgency_score >= 3:
            print("🤖 AGENT: High urgency - executing restock NOW")
            return True
        elif urgency_score >= 1:
            print("🤖 AGENT: Medium urgency - will restock soon")
            return False  # Wait for next check
        else:
            print("🤖 AGENT: Low urgency - monitoring")
            return False

    def execute_restock(self):
        """Execute restocking operation."""
        date = datetime.now().strftime("%Y-%m-%d")
        result = subprocess.run(
            ['./venv/bin/python', 'update_inventory.py', date],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            self.restock_count += 1
            print(f"🤖 AGENT: Restock #{self.restock_count} completed successfully")
        else:
            print(f"🤖 AGENT: Restock failed - {result.stderr}")

    def run(self, check_interval=60):
        """Run agent loop."""
        print("🤖 AGENT: Intelligent Restock Agent starting...")
        print(f"🤖 AGENT: Checking inventory every {check_interval} seconds")

        try:
            while True:
                if self.decide_restock():
                    self.execute_restock()

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print(f"\n🤖 AGENT: Shutting down (executed {self.restock_count} restocks)")

if __name__ == "__main__":
    agent = IntelligentRestockAgent()
    agent.run(check_interval=30)  # Check every 30 seconds
```

**Usage:**
```bash
# Terminal 1 - Run simulation with restocking disabled
./venv/bin/python run_simulation.py 30 --disable restock --step

# Terminal 2 - Run your intelligent agent
python intelligent_restock_agent.py
```

## Tips for Agent Development

1. **Start with monitoring** - Use `example_monitor.py` as a base
2. **Test incrementally** - Disable one operation at a time
3. **Use step mode** - Easier to debug agent behavior
4. **Log everything** - Track agent decisions and outcomes
5. **Compare performance** - Run with and without agents
6. **Handle errors** - Agents should be resilient
7. **Validate data** - Check database integrity after agent actions

## Next Steps

- Build agents for different operations
- Combine multiple agents (multi-agent system)
- Use reinforcement learning to optimize decisions
- Add monitoring dashboards for agent performance
- Create agent benchmarks and competitions

Your simulation is now an AI playground! 🤖🎯
