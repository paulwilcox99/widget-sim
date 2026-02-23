# Agent Developer Guide

## Overview

This guide is for developers building intelligent agents that integrate with Acme Widget Works manufacturing systems. You'll learn how to access the company databases, understand the data structures, implement business logic, and deploy agents that work in both development and production environments.

Agents connect directly to the company databases — the same systems used by every other part of the business. From an agent's perspective these are live production systems. An agent reads order queues, checks inventory levels, tracks manufacturing progress, and records financial transactions exactly as a human operator would, just programmatically.

## Quick Start

### Database Locations
All company systems are SQLite databases in the `databases/` directory:

```
databases/
├── crm.db         # Orders and customer interactions
├── inventory.db   # Parts, Bill of Materials, stock levels
├── mes.db         # Manufacturing execution tracking
└── erp.db         # Employees and financial transactions
```

### Basic Access Pattern

```python
import sqlite3

# Read-only access (safe for agents monitoring)
conn = sqlite3.connect('databases/crm.db')
conn.execute("PRAGMA query_only = ON")  # Prevents accidental writes
conn.row_factory = sqlite3.Row          # Access columns by name
cursor = conn.cursor()

cursor.execute("SELECT * FROM orders WHERE status = 'order_received'")
orders = cursor.fetchall()

conn.close()
```

---

## Database Schemas

### 1. CRM Database (`crm.db`)

**Purpose**: Track customer orders from placement to shipment

#### Table: `orders`

| Column | Type | Description |
|--------|------|-------------|
| `order_id` | INTEGER PRIMARY KEY | Unique order identifier (auto-increment) |
| `customer_name` | TEXT | Customer's full name |
| `widget_type` | TEXT | Product type: `Widget_Pro`, `Widget`, `Widget_Classic` |
| `quantity` | INTEGER | Number of units ordered |
| `unit_price` | REAL | Price per unit |
| `date_ordered` | TEXT | When order was placed (YYYY-MM-DD HH:MM:SS) |
| `status` | TEXT | Current status (see below) |
| `date_shipped` | TEXT | When order was shipped (NULL if not shipped) |
| `predicted_ship_date` | TEXT | Estimated ship date (YYYY-MM-DD) |

**Status Values:**
- `order_received` — New order, not yet processed
- `order_processing` — Inventory deducted, in manufacturing
- `order_shipped` — Completed and shipped

**Common Queries:**

```sql
-- Get all unprocessed orders
SELECT * FROM orders WHERE status = 'order_received' ORDER BY order_id;

-- Get high-value orders
SELECT * FROM orders WHERE (quantity * unit_price) > 10000;

-- Get orders for a specific widget type
SELECT * FROM orders WHERE widget_type = 'Widget_Pro' AND status = 'order_processing';

-- Count orders by status
SELECT status, COUNT(*), SUM(quantity * unit_price) as total_value
FROM orders
GROUP BY status;

-- Get orders past their predicted ship date
SELECT * FROM orders
WHERE status = 'order_processing'
AND predicted_ship_date < date('now');
```

**Agent Use Cases:**
- Prioritize high-value or time-sensitive orders
- Detect orders at risk of missing predicted ship dates
- Optimize order batching by widget type
- Route orders based on inventory availability

---

### 2. Inventory Database (`inventory.db`)

**Purpose**: Track parts, bills of materials, and stock levels

#### Table: `bom` (Bill of Materials)

| Column | Type | Description |
|--------|------|-------------|
| `bom_id` | INTEGER PRIMARY KEY | Unique BoM entry ID |
| `widget_type` | TEXT | Which widget this part is for |
| `part_name` | TEXT | Part identifier (e.g., "Screw-3") |
| `quantity_needed` | INTEGER | How many needed per widget unit |
| `unit_cost` | REAL | Cost per part |

**Common Queries:**

```sql
-- Get all parts needed for a widget
SELECT part_name, quantity_needed, unit_cost
FROM bom
WHERE widget_type = 'Widget_Pro';

-- Calculate total manufacturing cost per widget type
SELECT widget_type, SUM(quantity_needed * unit_cost) as total_cost
FROM bom
GROUP BY widget_type;

-- Find parts shared across multiple widget types
SELECT part_name, COUNT(DISTINCT widget_type) as widget_count
FROM bom
GROUP BY part_name
HAVING widget_count > 1;

-- Get most expensive parts
SELECT * FROM bom ORDER BY unit_cost DESC LIMIT 10;
```

#### Table: `inventory_levels`

| Column | Type | Description |
|--------|------|-------------|
| `part_name` | TEXT PRIMARY KEY | Part identifier |
| `quantity_available` | INTEGER | Current stock level |

**Common Queries:**

```sql
-- Check if enough inventory exists for a given order (substitute ? with values)
SELECT
    b.part_name,
    b.quantity_needed * ? as needed,
    i.quantity_available as available,
    i.quantity_available - (b.quantity_needed * ?) as remaining
FROM bom b
JOIN inventory_levels i ON b.part_name = i.part_name
WHERE b.widget_type = ?;

-- Find parts with low stock
SELECT
    i.part_name,
    i.quantity_available,
    b.widget_type,
    b.quantity_needed
FROM inventory_levels i
JOIN bom b ON i.part_name = b.part_name
ORDER BY i.quantity_available ASC;

-- Get parts that are completely out of stock
SELECT * FROM inventory_levels WHERE quantity_available = 0;

-- Calculate total inventory value
SELECT
    i.part_name,
    i.quantity_available,
    AVG(b.unit_cost) as avg_unit_cost,
    i.quantity_available * AVG(b.unit_cost) as total_value
FROM inventory_levels i
JOIN bom b ON i.part_name = b.part_name
GROUP BY i.part_name;
```

**Agent Use Cases:**
- Demand forecasting to determine when to reorder
- Economic order quantity (EOQ) calculations
- Identifying parts that are bottlenecks for multiple widget types
- Inventory carrying cost analysis

---

### 3. MES Database (`mes.db`)

**Purpose**: Track manufacturing progress through production stages

#### Table: `production_tracking`

| Column | Type | Description |
|--------|------|-------------|
| `tracking_id` | INTEGER PRIMARY KEY | Unique tracking entry ID |
| `order_id` | INTEGER | Links to `orders.order_id` in CRM |
| `stage` | TEXT | Stage name: `assembly`, `test`, `inspection`, `shipping` |
| `start_datetime` | TEXT | When stage started (NULL if not yet started) |
| `completion_datetime` | TEXT | When stage completed (NULL if in progress or not started) |

**Stage Flow:**
```
assembly → test → inspection → shipping → [order marked order_shipped in CRM]
```

Each order has exactly four rows in `production_tracking`, one per stage. Stages proceed sequentially: a stage's `start_datetime` is set when the previous stage completes.

**Common Queries:**

```sql
-- Get full production status for an order
SELECT stage, start_datetime, completion_datetime
FROM production_tracking
WHERE order_id = ?
ORDER BY tracking_id;

-- Find all orders currently in a specific stage
SELECT DISTINCT order_id
FROM production_tracking
WHERE stage = 'assembly'
AND start_datetime IS NOT NULL
AND completion_datetime IS NULL;

-- Calculate average time spent per stage (hours)
SELECT
    stage,
    AVG(julianday(completion_datetime) - julianday(start_datetime)) * 24 as avg_hours
FROM production_tracking
WHERE completion_datetime IS NOT NULL
GROUP BY stage;

-- Find orders that have been in a stage longer than expected
SELECT
    order_id,
    stage,
    start_datetime,
    (julianday('now') - julianday(start_datetime)) * 24 as hours_in_stage
FROM production_tracking
WHERE completion_datetime IS NULL
AND start_datetime IS NOT NULL
ORDER BY hours_in_stage DESC;

-- Get complete production history for an order, joined with CRM
SELECT
    o.order_id,
    o.customer_name,
    o.widget_type,
    p.stage,
    p.start_datetime,
    p.completion_datetime
FROM orders o
JOIN production_tracking p ON o.order_id = p.order_id
WHERE o.order_id = ?
ORDER BY p.tracking_id;
```

**Agent Use Cases:**
- Predict order completion times based on current stage and historical durations
- Identify production bottlenecks
- Alert when orders are overdue at a stage
- Schedule preventive maintenance around production workload

---

### 4. ERP Database (`erp.db`)

**Purpose**: Manage employees and financial transactions

#### Table: `employees`

| Column | Type | Description |
|--------|------|-------------|
| `employee_id` | INTEGER PRIMARY KEY | Unique employee ID |
| `name` | TEXT | Employee full name |
| `title` | TEXT | Job title (e.g., "Assembly Worker", "Test Engineer") |
| `weekly_salary` | REAL | Weekly salary amount |

**Common Queries:**

```sql
-- Get all employees
SELECT * FROM employees ORDER BY name;

-- Calculate total weekly payroll
SELECT SUM(weekly_salary) as total_weekly_payroll FROM employees;

-- Get employees by role
SELECT * FROM employees WHERE title LIKE '%Engineer%';

-- Payroll cost breakdown by department
SELECT title, COUNT(*) as headcount, SUM(weekly_salary) as weekly_cost
FROM employees
GROUP BY title
ORDER BY weekly_cost DESC;
```

#### Table: `financial_transactions`

| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | INTEGER PRIMARY KEY | Unique transaction ID |
| `transaction_type` | TEXT | Type: `inventory_purchase`, `employee_payment`, `customer_payment` |
| `amount` | REAL | Amount (negative = expense/debit, positive = income/credit) |
| `date` | TEXT | Transaction date (YYYY-MM-DD) |
| `description` | TEXT | Human-readable description |
| `related_id` | INTEGER | Links to `order_id` or `employee_id` where applicable (NULL otherwise) |

**Transaction Types:**
- `inventory_purchase` (positive amount) — Parts purchased to restock inventory
- `inventory_purchase` (negative amount) — Parts consumed to fulfill an order (COGS)
- `employee_payment` (negative amount) — Weekly payroll disbursement
- `customer_payment` (positive amount) — Revenue received when an order ships

**Common Queries:**

```sql
-- Get all transactions for a specific date
SELECT * FROM financial_transactions WHERE date = '2026-03-15';

-- Total revenue from shipped orders
SELECT SUM(amount) as total_revenue
FROM financial_transactions
WHERE transaction_type = 'customer_payment';

-- Expense breakdown
SELECT
    transaction_type,
    SUM(ABS(amount)) as total
FROM financial_transactions
WHERE amount < 0
GROUP BY transaction_type;

-- Profit and loss summary
SELECT
    SUM(CASE WHEN transaction_type = 'customer_payment' THEN amount ELSE 0 END) as revenue,
    SUM(CASE WHEN transaction_type = 'inventory_purchase' AND amount < 0 THEN ABS(amount) ELSE 0 END) as cogs,
    SUM(CASE WHEN transaction_type = 'employee_payment' THEN ABS(amount) ELSE 0 END) as payroll,
    SUM(CASE WHEN transaction_type = 'inventory_purchase' AND amount > 0 THEN amount ELSE 0 END) as inventory_purchases,
    SUM(amount) as net_result
FROM financial_transactions;

-- Daily cash flow
SELECT
    date,
    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as cash_in,
    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as cash_out,
    SUM(amount) as net_cash_flow
FROM financial_transactions
GROUP BY date
ORDER BY date;

-- All transactions related to a specific order
SELECT * FROM financial_transactions WHERE related_id = ? AND transaction_type != 'employee_payment';
```

**Agent Use Cases:**
- Cash flow monitoring and forecasting
- Anomaly detection on transaction patterns
- Margin analysis by widget type
- Payroll verification and audit

---

## Business Rules & Constraints

These rules define the invariants your agent must respect when reading from or writing to the company systems. Violating them will put the databases into an inconsistent state.

### Order Processing Rules

1. **Inventory Check**: Before accepting an order into manufacturing, verify all required parts are available:
   ```python
   # For each part in the BoM:
   parts_needed = quantity_per_widget * order_quantity
   if inventory_available < parts_needed:
       # Do not process — flag for review or wait for restock
   ```

2. **Order Status Flow**: Status must advance in sequence, never skip or reverse:
   ```
   order_received → order_processing → order_shipped
   ```

3. **Manufacturing Stages**: Stages must complete in order; a stage cannot start until the previous one is complete:
   ```
   assembly → test → inspection → shipping
   ```

4. **Inventory Deduction**: When releasing an order to manufacturing, deduct all required parts atomically:
   ```sql
   UPDATE inventory_levels
   SET quantity_available = quantity_available - ?
   WHERE part_name = ?
   ```
   Never allow `quantity_available` to go negative.

5. **Financial Recording**: Every operational action that moves money must be recorded:
   - Release order to manufacturing → negative `inventory_purchase` (COGS)
   - Purchase replacement stock → positive `inventory_purchase`
   - Ship completed order → positive `customer_payment`
   - Pay employees → negative `employee_payment`

### Inventory Management

There are no hardcoded restock rules — your agent should determine its own restock strategy based on the data available:

- **Demand signal**: pending `order_received` orders and their BoM requirements
- **Lead time**: how long past restock transactions took to normalize levels (visible in `financial_transactions` and `inventory_levels` history)
- **Safety stock**: the minimum buffer appropriate for your business risk tolerance
- **Order economics**: cost of ordering frequently vs. carrying excess stock

The BoM tables give you everything needed to calculate exactly how many units of each part are required to fulfill any combination of pending orders.

### Financial Integrity

- Record transactions on the date the business event occurred, not the date your agent runs
- `related_id` should reference the `order_id` for order-related transactions and `employee_id` for payroll transactions
- Do not record the same transaction twice — check for existing entries before inserting

---

## Python Helper Functions

### Safe Database Connection

```python
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_connection(db_path, read_only=False):
    """Context manager for safe database connections."""
    conn = sqlite3.connect(db_path)
    if read_only:
        conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
        if not read_only:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Usage:
with get_connection('databases/crm.db', read_only=True) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE status = 'order_received'")
    for row in cursor.fetchall():
        print(row['order_id'], row['customer_name'])
```

### Check Inventory Availability

```python
def can_fulfill_order(widget_type, quantity):
    """Check if enough inventory exists to fulfill an order."""
    with get_connection('databases/inventory.db', read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.part_name, b.quantity_needed, i.quantity_available
            FROM bom b
            JOIN inventory_levels i ON b.part_name = i.part_name
            WHERE b.widget_type = ?
        """, (widget_type,))

        for row in cursor.fetchall():
            needed = row['quantity_needed'] * quantity
            if row['quantity_available'] < needed:
                return False, f"Insufficient {row['part_name']} (need {needed}, have {row['quantity_available']})"

        return True, "OK"

# Usage:
can_fulfill, msg = can_fulfill_order('Widget_Pro', 10)
if not can_fulfill:
    print(f"Cannot fulfill order: {msg}")
```

### Get Order Status with Production Detail

```python
def get_order_details(order_id):
    """Get complete order information including production stage status."""
    with get_connection('databases/crm.db', read_only=True) as crm_conn:
        cursor = crm_conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()

    if not order:
        return None

    with get_connection('databases/mes.db', read_only=True) as mes_conn:
        cursor = mes_conn.cursor()
        cursor.execute("""
            SELECT stage, start_datetime, completion_datetime
            FROM production_tracking
            WHERE order_id = ?
            ORDER BY tracking_id
        """, (order_id,))
        stages = cursor.fetchall()

    return {
        'order': dict(order),
        'stages': [dict(stage) for stage in stages]
    }

# Usage:
details = get_order_details(123)
print(f"Order {details['order']['order_id']} — {details['order']['status']}")
for stage in details['stages']:
    status = stage['completion_datetime'] or ('In progress' if stage['start_datetime'] else 'Not started')
    print(f"  {stage['stage']}: {status}")
```

### Calculate Inventory Value

```python
def calculate_inventory_value():
    """Calculate total value of current inventory at cost."""
    with get_connection('databases/inventory.db', read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                i.part_name,
                i.quantity_available,
                AVG(b.unit_cost) as avg_cost,
                i.quantity_available * AVG(b.unit_cost) as total_value
            FROM inventory_levels i
            JOIN bom b ON i.part_name = b.part_name
            GROUP BY i.part_name
        """)

        total = sum(row['total_value'] for row in cursor.fetchall())
        return total

# Usage:
value = calculate_inventory_value()
print(f"Total inventory value: ${value:,.2f}")
```

---

## Agent Implementation Patterns

### Pattern 1: Monitoring Agent

Watches the databases and alerts on business conditions. Works in both development and production — the only difference is how it decides when to run (see the Scheduling section below).

```python
class ManufacturingMonitor:
    def check_overdue_orders(self):
        """Alert on orders past their predicted ship date."""
        with get_connection('databases/crm.db', read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT order_id, customer_name, widget_type, predicted_ship_date
                FROM orders
                WHERE status = 'order_processing'
                AND predicted_ship_date < date('now')
                ORDER BY predicted_ship_date
            """)
            overdue = cursor.fetchall()

        if overdue:
            print(f"OVERDUE ORDERS ({len(overdue)}):")
            for order in overdue:
                print(f"  Order #{order['order_id']} — {order['customer_name']} "
                      f"({order['widget_type']}) was due {order['predicted_ship_date']}")

    def check_production_bottlenecks(self):
        """Alert on orders stuck in a stage longer than a threshold."""
        threshold_hours = 48
        with get_connection('databases/mes.db', read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    order_id, stage, start_datetime,
                    (julianday('now') - julianday(start_datetime)) * 24 as hours_in_stage
                FROM production_tracking
                WHERE completion_datetime IS NULL
                AND start_datetime IS NOT NULL
                AND (julianday('now') - julianday(start_datetime)) * 24 > ?
                ORDER BY hours_in_stage DESC
            """, (threshold_hours,))
            stuck = cursor.fetchall()

        if stuck:
            print(f"BOTTLENECK ALERT — orders in stage > {threshold_hours}h:")
            for row in stuck:
                print(f"  Order #{row['order_id']} stuck in {row['stage']} "
                      f"for {row['hours_in_stage']:.1f} hours")

    def run_checks(self):
        self.check_overdue_orders()
        self.check_production_bottlenecks()
```

### Pattern 2: Decision Agent

Makes business decisions based on current system state:

```python
class InventoryAgent:
    def assess_restock_needs(self):
        """
        Determine which parts need restocking based on current stock
        and pending order demand.
        """
        with get_connection('databases/inventory.db', read_only=True) as conn:
            cursor = conn.cursor()

            # Get current stock levels
            cursor.execute("SELECT part_name, quantity_available FROM inventory_levels")
            stock = {row['part_name']: row['quantity_available'] for row in cursor.fetchall()}

            # Get BoM requirements
            cursor.execute("SELECT part_name, widget_type, quantity_needed, unit_cost FROM bom")
            bom = cursor.fetchall()

        # Calculate parts required to fulfill all pending orders
        with get_connection('databases/crm.db', read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT widget_type, SUM(quantity) as total_qty
                FROM orders
                WHERE status = 'order_received'
                GROUP BY widget_type
            """)
            pending_demand = {row['widget_type']: row['total_qty'] for row in cursor.fetchall()}

        # Identify shortfalls
        shortfalls = {}
        for row in bom:
            demand_for_widget = pending_demand.get(row['widget_type'], 0)
            parts_needed = row['quantity_needed'] * demand_for_widget
            available = stock.get(row['part_name'], 0)
            if available < parts_needed:
                shortfall = parts_needed - available
                if row['part_name'] not in shortfalls or shortfalls[row['part_name']] < shortfall:
                    shortfalls[row['part_name']] = shortfall

        return shortfalls

    def restock_parts(self, shortfalls, restock_date):
        """Purchase parts to cover shortfalls and record transactions."""
        if not shortfalls:
            return

        inv_conn = sqlite3.connect('databases/inventory.db')
        erp_conn = sqlite3.connect('databases/erp.db')

        try:
            for part_name, shortfall_qty in shortfalls.items():
                # Get unit cost from BoM
                cursor = inv_conn.cursor()
                cursor.execute(
                    "SELECT AVG(unit_cost) as avg_cost FROM bom WHERE part_name = ?",
                    (part_name,)
                )
                avg_cost = cursor.fetchone()[0]
                total_cost = shortfall_qty * avg_cost

                # Update inventory
                inv_conn.execute(
                    "UPDATE inventory_levels SET quantity_available = quantity_available + ? WHERE part_name = ?",
                    (shortfall_qty, part_name)
                )

                # Record financial transaction
                erp_conn.execute("""
                    INSERT INTO financial_transactions
                        (transaction_type, amount, date, description)
                    VALUES (?, ?, ?, ?)
                """, ("inventory_purchase", total_cost, restock_date,
                      f"Restocked {part_name}: {shortfall_qty} units"))

            inv_conn.commit()
            erp_conn.commit()

        finally:
            inv_conn.close()
            erp_conn.close()
```

### Pattern 3: Optimization Agent

Prioritizes work for maximum business impact:

```python
class OrderPrioritizationAgent:
    def get_prioritized_orders(self):
        """
        Return unprocessed orders sorted by business priority:
        highest value first, then by urgency of predicted ship date,
        then grouped by widget type to minimize inventory fragmentation.
        """
        with get_connection('databases/crm.db', read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    order_id,
                    widget_type,
                    quantity,
                    unit_price,
                    quantity * unit_price as total_value,
                    predicted_ship_date
                FROM orders
                WHERE status = 'order_received'
            """)
            orders = [dict(row) for row in cursor.fetchall()]

        return sorted(orders, key=lambda x: (
            -x['total_value'],         # High value first
            x['predicted_ship_date'],  # Nearest deadline first
            x['widget_type']           # Group by type to batch inventory pulls
        ))
```

---

## Scheduling: Development vs. Production

Agents need a trigger to know when to run. The mechanism differs between the development environment and production.

### Development / Testing (with the simulator)

The simulator writes a `sim_state.json` file at the start and end of each simulated day. Poll this file to synchronize your agent with the simulation clock:

```python
import json
import time
from pathlib import Path

def wait_for_new_day(state_file='sim_state.json', poll_interval=0.5):
    """
    Block until the simulator signals that a new day is complete.
    Returns the current simulation date, or None if the simulation has finished.
    """
    last_seen_day = None

    while True:
        path = Path(state_file)
        if not path.exists():
            time.sleep(poll_interval)
            continue

        with open(path) as f:
            state = json.load(f)

        status = state['simulation']['status']
        day_number = state['simulation']['day_number']

        if status == 'finished':
            return None  # Simulation is done

        if status == 'day_complete' and day_number != last_seen_day:
            last_seen_day = day_number
            return state['simulation']['date']

        time.sleep(poll_interval)


# Development agent loop
if __name__ == '__main__':
    agent = ManufacturingMonitor()

    while True:
        sim_date = wait_for_new_day()
        if sim_date is None:
            print("Simulation complete.")
            break

        print(f"Running checks for {sim_date}")
        agent.run_checks()
```

`sim_state.json` fields your agent may use:

| Field | Description |
|-------|-------------|
| `simulation.date` | Current simulation date (YYYY-MM-DD) |
| `simulation.day_number` | Day counter (1-indexed) |
| `simulation.total_days` | Total days being simulated |
| `simulation.status` | `initializing`, `running`, `day_complete`, `finished`, `error` |
| `operations.pending` | Operations the simulation has disabled and expects an agent to handle |

> **Note:** Your agent's core business logic should never depend on `sim_state.json`. It is a development convenience only. The databases are the source of truth.

### Production

In a live environment, replace the state file poll with your real scheduling mechanism:

```python
# Option A: cron / scheduled task
#   Run the agent script on a schedule via cron, Task Scheduler, etc.
#   No polling needed — the OS is the trigger.

# Option B: event-driven (message queue, webhook)
import pika  # or kafka, redis pub/sub, etc.

def on_day_close_event(channel, method, properties, body):
    """Called when the ERP publishes an end-of-day event."""
    agent = ManufacturingMonitor()
    agent.run_checks()

# Option C: database polling (simplest production approach)
import time

def production_agent_loop(agent, poll_interval_seconds=300):
    """Poll the databases directly on a fixed interval."""
    while True:
        agent.run_checks()
        time.sleep(poll_interval_seconds)
```

The agent code that reads and writes the company databases is identical in all cases — only the trigger changes.

---

## Testing Your Agent

Test against a copy of the databases, never the originals.

### Copy Databases for Testing

```python
import shutil
from pathlib import Path

def setup_test_databases(source_dir='databases', test_dir='test_databases'):
    """Copy live databases to an isolated test directory."""
    src = Path(source_dir)
    dst = Path(test_dir)
    dst.mkdir(exist_ok=True)
    for db_file in src.glob('*.db'):
        shutil.copy(db_file, dst / db_file.name)
    return dst
```

### Validate Business Rules

```python
def validate_order_flow():
    """Ensure no orders were shipped without going through manufacturing."""
    with get_connection('databases/crm.db', read_only=True) as crm_conn:
        cursor = crm_conn.cursor()
        cursor.execute("SELECT order_id FROM orders WHERE status = 'order_shipped'")
        shipped_ids = {row['order_id'] for row in cursor.fetchall()}

    with get_connection('databases/mes.db', read_only=True) as mes_conn:
        cursor = mes_conn.cursor()
        cursor.execute("SELECT DISTINCT order_id FROM production_tracking")
        tracked_ids = {row['order_id'] for row in cursor.fetchall()}

    untracked = shipped_ids - tracked_ids
    assert len(untracked) == 0, \
        f"Found {len(untracked)} shipped orders with no MES records: {untracked}"


def validate_inventory_integrity():
    """Ensure no part has negative stock."""
    with get_connection('databases/inventory.db', read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT part_name, quantity_available
            FROM inventory_levels
            WHERE quantity_available < 0
        """)
        negative = cursor.fetchall()

    assert len(negative) == 0, \
        f"Found {len(negative)} parts with negative inventory: {[r['part_name'] for r in negative]}"


def validate_financial_balance():
    """Sanity check: revenue should exceed COGS for a healthy business."""
    with get_connection('databases/erp.db', read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                SUM(CASE WHEN transaction_type = 'customer_payment' THEN amount ELSE 0 END) as revenue,
                SUM(CASE WHEN transaction_type = 'inventory_purchase' AND amount < 0
                         THEN ABS(amount) ELSE 0 END) as cogs
            FROM financial_transactions
        """)
        row = cursor.fetchone()

    if row['revenue'] and row['cogs']:
        gross_margin = (row['revenue'] - row['cogs']) / row['revenue']
        assert gross_margin > 0, f"Negative gross margin detected: {gross_margin:.1%}"
```

---

## Common Pitfalls

### Always close connections

```python
# ❌ Connection left open — causes locks for other writers
conn = sqlite3.connect('databases/crm.db')
cursor.execute("SELECT * FROM orders")
# ... forgot conn.close()

# ✅ Use a context manager
with get_connection('databases/crm.db') as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
```

### Validate before modifying inventory

```python
# ❌ Could drive quantity_available negative
conn.execute("UPDATE inventory_levels SET quantity_available = quantity_available - 1000")

# ✅ Check first, then deduct
cursor.execute("SELECT quantity_available FROM inventory_levels WHERE part_name = ?", (part,))
current = cursor.fetchone()[0]
if current >= amount_needed:
    conn.execute(
        "UPDATE inventory_levels SET quantity_available = quantity_available - ?",
        (amount_needed,)
    )
else:
    raise ValueError(f"Insufficient stock for {part}: need {amount_needed}, have {current}")
```

### Use parameterized queries

```python
# ❌ SQL injection risk
cursor.execute(f"SELECT * FROM orders WHERE customer_name = '{name}'")

# ✅ Always use parameters
cursor.execute("SELECT * FROM orders WHERE customer_name = ?", (name,))
```

### Write transactions atomically

```python
# ❌ Partial update — inventory deducted but CRM status not updated if crash occurs
conn.execute("UPDATE inventory_levels ...")
conn.commit()
# ... crash here leaves databases inconsistent
conn2.execute("UPDATE orders SET status = 'order_processing' ...")
conn2.commit()

# ✅ Use a single connection when possible, or accept and handle partial failures
try:
    conn.execute("UPDATE inventory_levels ...")
    conn.execute("UPDATE orders SET status = 'order_processing' ...")
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

---

## Quick Reference

### Database Files
| File | System | Primary Use |
|------|--------|-------------|
| `databases/crm.db` | CRM | Orders from receipt to shipment |
| `databases/inventory.db` | Inventory | Parts stock and Bill of Materials |
| `databases/mes.db` | MES | Production stage tracking |
| `databases/erp.db` | ERP | Employees and financial transactions |

### Key Tables
| Table | Database | Description |
|-------|----------|-------------|
| `orders` | crm.db | All customer orders |
| `bom` | inventory.db | Parts required per widget type |
| `inventory_levels` | inventory.db | Current stock per part |
| `production_tracking` | mes.db | Manufacturing stage progress |
| `employees` | erp.db | Worker roster and salaries |
| `financial_transactions` | erp.db | All money movement |

### Status Values
- **Orders**: `order_received` → `order_processing` → `order_shipped`
- **Production stages**: `assembly` → `test` → `inspection` → `shipping`
- **Transaction types**: `inventory_purchase`, `employee_payment`, `customer_payment`

### Connection Template
```python
import sqlite3

with sqlite3.connect('databases/X.db') as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    results = cursor.fetchall()
```

---

## Getting Help

### During development with the simulator
- `show_dbs.py` — exports all database contents to markdown for inspection
- `sync_agent_example.py` — example of polling `sim_state.json` to synchronize with the simulation clock
- `AGENT_SYNC_GUIDE.md` — detailed guide to the state file format and synchronization patterns
- `AGENT_INTEGRATION.md` — patterns for replacing built-in simulation operations with agent logic

### In production
Your agent's connection to the company databases is the same regardless of environment. Swap the scheduling mechanism (state file poll → cron/event bus), point the database paths at your production system, and the business logic code is unchanged.
