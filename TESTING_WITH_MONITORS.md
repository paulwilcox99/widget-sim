# Testing Database Monitoring Software

## Overview
The step mode allows external software to monitor database changes in a controlled manner. After each simulation day, the databases are in a stable state, perfect for monitoring software to analyze.

## Basic Workflow

```
┌─────────────────────────────────────────────────────────┐
│  Simulation (run_simulation.py --step)                 │
│  ├─ Day 1 operations                                   │
│  ├─ Databases updated                                  │
│  └─ PAUSE ⏸️  (waiting for input)                      │
│                                                         │
│  ┌────────────────────────────────────┐               │
│  │  Your Monitoring Software          │               │
│  │  ├─ Detect changes in databases/   │               │
│  │  ├─ Read CRM, ERP, Inventory, MES  │               │
│  │  ├─ Analyze transactions           │               │
│  │  └─ Run tests/validations          │               │
│  └────────────────────────────────────┘               │
│                                                         │
│  [User/Script sends: Enter]                            │
│  ├─ Day 2 operations                                   │
│  ├─ Databases updated                                  │
│  └─ PAUSE ⏸️                                            │
│  ...                                                   │
└─────────────────────────────────────────────────────────┘
```

## Method 1: Manual Control

Start the simulation in one terminal:
```bash
cd /home/paul/code/widget
./venv/bin/python run_simulation.py 30 "2026-03-01" --step
```

In another terminal, monitor the databases:
```bash
# Watch for file changes
watch -n 1 'ls -lh databases/'

# Or use your monitoring software
your-monitor --watch databases/ --on-change analyze
```

After each day:
1. Simulation pauses
2. Your software detects database changes
3. Your software analyzes the changes
4. Press Enter in simulation terminal to continue

## Method 2: Scripted Control with Named Pipe

Create a named pipe for controlled input:

```bash
# Setup
mkfifo /tmp/sim_control

# Start simulation (reads from pipe)
./venv/bin/python run_simulation.py 30 "2026-03-01" --step < /tmp/sim_control

# In another terminal/script, control the flow:
echo "" > /tmp/sim_control  # Advance one day
sleep 5                      # Let monitoring software run
echo "" > /tmp/sim_control  # Advance another day
```

## Method 3: Automated Testing Script

```bash
#!/bin/bash
# automated_test.sh - Run simulation with monitoring

SIM_DAYS=30
START_DATE="2026-03-01"

# Start simulation in background with pipe
mkfifo /tmp/sim_pipe
./venv/bin/python run_simulation.py $SIM_DAYS "$START_DATE" --step < /tmp/sim_pipe &
SIM_PID=$!

# Function to advance simulation
advance_day() {
    echo "" > /tmp/sim_pipe
}

# Function to run monitoring checks
check_databases() {
    echo "Running monitoring checks..."

    # Example: Check order count
    sqlite3 databases/crm.db "SELECT COUNT(*) FROM orders" > /tmp/order_count.txt

    # Run your monitoring software
    your-monitor --check databases/ --report /tmp/monitor_report.txt

    # Validate results
    if [ $? -eq 0 ]; then
        echo "✓ Monitoring checks passed"
        return 0
    else
        echo "✗ Monitoring checks failed"
        return 1
    fi
}

# Run simulation with monitoring
for day in $(seq 1 $SIM_DAYS); do
    echo "Waiting for day $day to complete..."
    sleep 2  # Wait for day operations to finish

    # Run monitoring checks
    check_databases

    if [ $? -ne 0 ]; then
        echo "Test failed on day $day"
        echo "q" > /tmp/sim_pipe  # Quit simulation
        exit 1
    fi

    # Advance to next day
    advance_day
done

# Cleanup
rm /tmp/sim_pipe
wait $SIM_PID
```

## Method 4: Python Integration

```python
#!/usr/bin/env python3
"""
monitor_simulation.py - Integrate monitoring with simulation
"""

import subprocess
import time
import sqlite3
from pathlib import Path

class SimulationMonitor:
    def __init__(self, db_path="databases"):
        self.db_path = Path(db_path)
        self.previous_state = {}

    def check_changes(self):
        """Detect what changed in databases."""
        changes = {}

        # Check CRM
        conn = sqlite3.connect(self.db_path / "crm.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = cursor.fetchone()[0]

        if 'order_count' in self.previous_state:
            changes['new_orders'] = order_count - self.previous_state['order_count']

        self.previous_state['order_count'] = order_count
        conn.close()

        # Check ERP for new transactions
        conn = sqlite3.connect(self.db_path / "erp.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM financial_transactions")
        txn_count = cursor.fetchone()[0]

        if 'txn_count' in self.previous_state:
            changes['new_transactions'] = txn_count - self.previous_state['txn_count']

        self.previous_state['txn_count'] = txn_count
        conn.close()

        return changes

    def analyze_day(self, day_num):
        """Analyze changes after a simulation day."""
        print(f"\n=== Monitoring Day {day_num} ===")

        changes = self.check_changes()

        for key, value in changes.items():
            print(f"  {key}: {value}")

        # Run your monitoring logic here
        # Example: alert if too many orders
        if changes.get('new_orders', 0) > 15:
            print("  ⚠️  Alert: High order volume!")

        # Return True to continue, False to stop
        return True

def run_monitored_simulation(days=7, start_date="2026-03-01"):
    """Run simulation with monitoring between days."""
    monitor = SimulationMonitor()

    # Start simulation
    proc = subprocess.Popen(
        ['./venv/bin/python', 'run_simulation.py', str(days), start_date, '--step'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    for day in range(1, days + 1):
        # Wait for day to complete
        time.sleep(3)

        # Run monitoring
        should_continue = monitor.analyze_day(day)

        if not should_continue:
            proc.stdin.write("q\n")
            proc.stdin.flush()
            break

        # Continue to next day
        proc.stdin.write("\n")
        proc.stdin.flush()

    proc.wait()

if __name__ == "__main__":
    run_monitored_simulation(days=7, start_date="2026-03-01")
```

## Database Files to Monitor

All database files are in `databases/`:
```
databases/
├── crm.db          # Orders, customer interactions
├── inventory.db    # BoM, stock levels
├── mes.db          # Manufacturing stages
├── erp.db          # Financial transactions, payroll
└── customers.db    # Customer pool (rarely changes)
```

## What Changes Each Day

| Day Event | Database Changes |
|-----------|------------------|
| **Order Generation** | `crm.db`: New rows in `orders` table |
| **Order Processing** | `inventory.db`: Decremented stock<br>`crm.db`: Status changes<br>`mes.db`: New tracking rows<br>`erp.db`: Inventory usage transactions |
| **Manufacturing Ops** | `mes.db`: Stage completions<br>`crm.db`: Status to shipped<br>`erp.db`: Customer payments |
| **Inventory Restock** (every 3 days) | `inventory.db`: Increased stock<br>`erp.db`: Purchase transactions |
| **Payroll** (Fridays) | `erp.db`: 200 payment transactions |

## Testing Scenarios

### Scenario 1: Monitor Order Processing
```bash
# Watch for orders moving through stages
./venv/bin/python run_simulation.py 10 --step

# Your monitor checks:
# - Orders changing from order_received → order_processing
# - MES entries being created
# - Inventory being deducted
```

### Scenario 2: Financial Transaction Validation
```bash
# Verify all transactions are recorded correctly
./venv/bin/python run_simulation.py 14 --step

# Your monitor validates:
# - Every shipped order has a payment transaction
# - Payroll happens only on Fridays
# - Inventory purchases match stock increases
```

### Scenario 3: Inventory Monitoring
```bash
# Alert when stock is low
./venv/bin/python run_simulation.py 30 --step

# Your monitor checks:
# - Stock levels after each order
# - Restock triggers (every 3 days)
# - No negative inventory
```

## Tips for Monitoring Software

1. **Wait for Stability**: After simulation pauses, wait 1-2 seconds before querying databases to ensure all writes are committed.

2. **Use Read-Only Connections**: Open databases with `PRAGMA query_only = ON` to avoid locking issues.

3. **Snapshot Comparisons**: Take database snapshots and compare states between days.

4. **File Watching**: Monitor database file modification times to detect when changes occur.

5. **Transaction Logs**: Query the `financial_transactions` table to see all financial events.

## Example: Simple File Watcher

```python
import time
from pathlib import Path

def watch_databases():
    db_dir = Path("databases")
    last_modified = {}

    while True:
        for db_file in db_dir.glob("*.db"):
            mtime = db_file.stat().st_mtime

            if db_file.name in last_modified:
                if mtime > last_modified[db_file.name]:
                    print(f"🔄 {db_file.name} changed!")
                    # Run your analysis here

            last_modified[db_file.name] = mtime

        time.sleep(1)
```

## Integration with CI/CD

```yaml
# Example: GitHub Actions workflow
name: Test Database Monitor

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m venv venv
          ./venv/bin/pip install faker

      - name: Run monitored simulation
        run: |
          # Run 7 days with your monitoring software
          ./tests/run_monitored_test.sh

      - name: Validate results
        run: |
          # Check that monitoring software detected all changes
          ./tests/validate_monitoring.sh
```

This allows you to fully control the simulation flow and test your monitoring software in a controlled, repeatable environment!
