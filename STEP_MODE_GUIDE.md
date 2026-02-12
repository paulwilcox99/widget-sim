# Step Mode Guide

## Overview
Step mode allows you to run the simulation interactively, pausing after each day to review results before continuing.

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
- Learning how the simulation works
- Debugging issues with specific days
- Observing patterns in order generation
- Monitoring inventory levels closely
- Teaching/demonstrations

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

### Learning the System (First Time)
```bash
# Start fresh, step through one week
./venv/bin/python run_simulation.py 7 --step

# Review each day's operations
# Press 's' on Friday to see payroll impact
# Press 'q' after understanding the flow
```

### Debugging Inventory Issues
```bash
# Initialize fresh
./venv/bin/python run_simulation.py 10 --step

# Watch for "INSUFFICIENT INVENTORY" messages
# Press 's' to check stock levels
# Continue or quit when issue is clear
```

### Demonstrating to Others
```bash
# Use a fixed start date for consistency
./venv/bin/python run_simulation.py 14 "2026-01-06" --step

# Explain each operation as it happens
# Use 's' to show real-time financial impact
# Let attendees decide when to continue
```
