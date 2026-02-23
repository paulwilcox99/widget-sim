# Step Mode Guide

## Overview
Step mode allows you to run the simulator interactively, pausing after each simulated day so you can inspect the databases, run your agent manually, or review results before advancing to the next day.

## Usage

### Basic Step Mode
```bash
./venv/bin/python run_simulation.py 7 --step
```

### Step Mode with Specific Start Date
```bash
./venv/bin/python run_simulation.py 30 "2026-03-01" --step
```

### Step Mode with Existing Database
```bash
./venv/bin/python run_simulation.py 14 --step --no-init
```

## Interactive Commands

After each day completes, you'll see a prompt:
```
----------------------------------------------------------------------
Press Enter to continue to next day (or 'q' to quit, 's' for summary):
```

### Available Commands:

| Key | Action |
|-----|--------|
| **Enter** | Continue to the next day |
| **q** | Quit simulation and show final summary |
| **s** | Show current summary, then continue |

## Example Session

```
DAY 1/7: 2026-03-01 (Monday)
======================================================================

📋 Generating 15 new orders...
  ✓ Generated 15 orders at 2026-03-01 09:00:00

⚙️  Processing orders at 2026-03-01 10:00:00...
  → Processing new orders

🏭 Running manufacturing operations at 2026-03-01 10:00:00...
  → Advancing production stages

✓ Day 1 complete

----------------------------------------------------------------------
Press Enter to continue to next day (or 'q' to quit, 's' for summary): [Press Enter]

DAY 2/7: 2026-03-02 (Tuesday)
======================================================================
...
```

## When to Use Step Mode

**Good for:**
- Learning how the business databases change day to day
- Developing agents — pause after each day, run your agent, inspect results
- Debugging unexpected database state on a specific day
- Demonstrations — explain each operation as it happens

**Not ideal for:**
- Long simulations (30+ days)
- Batch processing
- Automated testing
- Quick results

## Tips

1. **Use 's' to check progress**: Press 's' periodically to see financial metrics without stopping the simulation

2. **Combine with small day counts**: Start with 7-14 days to keep sessions manageable

3. **Review special days**: Pay attention to:
   - Day 3, 6, 9... (inventory restocking)
   - Fridays (payroll)
   - Days when orders ship (revenue events)

4. **Quick restart**: If you want to restart without losing progress:
   ```bash
   # Stop current simulation (press 'q')
   # Continue with existing data
   ./venv/bin/python run_simulation.py 7 --step --no-init
   ```

## Example Workflows

### Learning the Database Schema (First Time)
```bash
# Start fresh, step through one week
./venv/bin/python run_simulation.py 7 --step

# After each day, query the databases directly to see what changed:
#   sqlite3 databases/crm.db "SELECT status, COUNT(*) FROM orders GROUP BY status"
#   sqlite3 databases/erp.db "SELECT transaction_type, SUM(amount) FROM financial_transactions GROUP BY transaction_type"
# Press 's' on Friday to see payroll impact in the summary
# Press 'q' after you understand the data flow
```

### Developing an Agent
```bash
# Disable the operation your agent will handle
./venv/bin/python run_simulation.py 10 "2026-03-01" --step --disable restock

# After each day pauses, run your agent with that day's date:
#   python restock_agent.py 2026-03-01
# Inspect results, then press Enter to advance
```

### Demonstrating to Others
```bash
# Use a fixed start date for reproducibility
./venv/bin/python run_simulation.py 14 "2026-01-06" --step

# Explain each database change as it happens
# Use 's' to show running financial totals
# Let attendees decide when to continue
```
