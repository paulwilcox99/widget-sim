# Agent Developer Guide

## Overview

This guide is for developers building intelligent agents to control the manufacturing simulation. You'll learn how to access the databases, understand the data structures, and implement your own business logic.

## Quick Start

### Database Locations
All databases are SQLite files in the `databases/` directory:

```
databases/
├── customers.db    # Customer pool (mostly static)
├── crm.db         # Orders and customer interactions
├── inventory.db   # Parts, BoM, stock levels
├── mes.db         # Manufacturing execution tracking
└── erp.db         # Employees, financials
```

### Basic Access Pattern

```python
import sqlite3

# Read-only access (safe for agents monitoring)
conn = sqlite3.connect('databases/crm.db')
conn.execute("PRAGMA query_only = ON")  # Prevents accidental writes
cursor = conn.cursor()

cursor.execute("SELECT * FROM orders WHERE status = 'order_received'")
orders = cursor.fetchall()

conn.close()
```

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
| `unit_price` | REAL | Price per unit (already includes margin) |
| `date_ordered` | TEXT | When order was placed (YYYY-MM-DD HH:MM:SS) |
| `status` | TEXT | Current status (see below) |
| `date_shipped` | TEXT | When order was shipped (NULL if not shipped) |
| `predicted_ship_date` | TEXT | Estimated ship date (YYYY-MM-DD) |

**Status Values:**
- `order_received` - New order, not yet processed
- `order_processing` - Inventory deducted, in manufacturing
- `order_shipped` - Completed and shipped

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

-- Get orders that should have shipped by now
SELECT * FROM orders
WHERE status = 'order_processing'
AND predicted_ship_date < date('now');
```

**Agent Use Cases:**
- Prioritize high-value orders
- Predict delays based on inventory
- Optimize order batching
- Dynamic pricing based on demand

---

### 2. Inventory Database (`inventory.db`)

**Purpose**: Track parts, bills of materials, and stock levels

#### Table: `bom` (Bill of Materials)

| Column | Type | Description |
|--------|------|-------------|
| `bom_id` | INTEGER PRIMARY KEY | Unique BoM entry ID |
| `widget_type` | TEXT | Which widget this part is for |
| `part_name` | TEXT | Part identifier (e.g., "Screw-3") |
| `quantity_needed` | INTEGER | How many needed per widget |
| `unit_cost` | REAL | Cost per part (manufacturing cost) |

**Common Queries:**

```sql
-- Get all parts needed for a widget
SELECT part_name, quantity_needed, unit_cost
FROM bom
WHERE widget_type = 'Widget_Pro';

-- Calculate total cost to build one widget
SELECT widget_type, SUM(quantity_needed * unit_cost) as total_cost
FROM bom
GROUP BY widget_type;

-- Find parts used in multiple widgets
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
-- Check if enough inventory for an order
SELECT
    b.part_name,
    b.quantity_needed * ? as needed,  -- ? = order quantity
    i.quantity_available as available,
    i.quantity_available - (b.quantity_needed * ?) as remaining
FROM bom b
JOIN inventory_levels i ON b.part_name = i.part_name
WHERE b.widget_type = ?;  -- ? = widget type

-- Find parts below threshold
SELECT * FROM inventory_levels WHERE quantity_available < 200;

-- Get parts that are completely out of stock
SELECT * FROM inventory_levels WHERE quantity_available = 0;

-- Calculate total inventory value
SELECT
    i.part_name,
    i.quantity_available,
    b.unit_cost,
    i.quantity_available * b.unit_cost as total_value
FROM inventory_levels i
JOIN bom b ON i.part_name = b.part_name
GROUP BY i.part_name;
```

**Agent Use Cases:**
- Predict when to reorder (demand forecasting)
- Optimize order quantities (EOQ models)
- Identify bottleneck parts
- Calculate inventory carrying costs

---

### 3. MES Database (`mes.db`)

**Purpose**: Track manufacturing progress through production stages

#### Table: `production_tracking`

| Column | Type | Description |
|--------|------|-------------|
| `tracking_id` | INTEGER PRIMARY KEY | Unique tracking entry ID |
| `order_id` | INTEGER | Links to `orders.order_id` in CRM |
| `stage` | TEXT | Current stage: `assembly`, `test`, `inspection`, `shipping` |
| `start_datetime` | TEXT | When stage started (NULL if not started) |
| `completion_datetime` | TEXT | When stage completed (NULL if in progress) |

**Stage Flow:**
```
assembly → test → inspection → shipping → order_shipped
```

**Common Queries:**

```sql
-- Get production status for an order
SELECT stage, start_datetime, completion_datetime
FROM production_tracking
WHERE order_id = ?
ORDER BY tracking_id;

-- Find orders in a specific stage
SELECT DISTINCT order_id
FROM production_tracking
WHERE stage = 'assembly'
AND start_datetime IS NOT NULL
AND completion_datetime IS NULL;

-- Calculate average time per stage
SELECT
    stage,
    AVG(julianday(completion_datetime) - julianday(start_datetime)) * 24 as avg_hours
FROM production_tracking
WHERE completion_datetime IS NOT NULL
GROUP BY stage;

-- Find bottlenecks (orders stuck in a stage too long)
SELECT
    order_id,
    stage,
    start_datetime,
    (julianday('now') - julianday(start_datetime)) * 24 as hours_in_stage
FROM production_tracking
WHERE completion_datetime IS NULL
AND start_datetime IS NOT NULL
ORDER BY hours_in_stage DESC;

-- Get complete order history
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
- Optimize stage durations
- Predict completion times
- Identify production bottlenecks
- Schedule maintenance windows

---

### 4. ERP Database (`erp.db`)

**Purpose**: Manage employees and financial transactions

#### Table: `employees`

| Column | Type | Description |
|--------|------|-------------|
| `employee_id` | INTEGER PRIMARY KEY | Unique employee ID |
| `name` | TEXT | Employee full name |
| `title` | TEXT | Job title (e.g., "Assembly Worker") |
| `weekly_salary` | REAL | Weekly salary amount |

**Common Queries:**

```sql
-- Get all employees
SELECT * FROM employees ORDER BY name;

-- Calculate total weekly payroll
SELECT SUM(weekly_salary) as total_weekly_payroll FROM employees;

-- Get employees by role
SELECT * FROM employees WHERE title LIKE '%Engineer%';

-- Count employees by title
SELECT title, COUNT(*) as count, SUM(weekly_salary) as total_cost
FROM employees
GROUP BY title
ORDER BY total_cost DESC;
```

#### Table: `financial_transactions`

| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | INTEGER PRIMARY KEY | Unique transaction ID |
| `transaction_type` | TEXT | Type: `inventory_purchase`, `employee_payment`, `customer_payment` |
| `amount` | REAL | Amount (negative = expense, positive = income) |
| `date` | TEXT | Transaction date (YYYY-MM-DD) |
| `description` | TEXT | Human-readable description |
| `related_id` | INTEGER | Links to order_id or employee_id (NULL if not applicable) |

**Transaction Types:**
- `inventory_purchase` (positive amount) - Buying inventory
- `inventory_purchase` (negative amount) - Using inventory (COGS)
- `employee_payment` (negative amount) - Payroll
- `customer_payment` (positive amount) - Revenue from shipped orders

**Common Queries:**

```sql
-- Get all transactions for a date
SELECT * FROM financial_transactions WHERE date = '2026-03-15';

-- Calculate revenue (customer payments)
SELECT SUM(amount) as total_revenue
FROM financial_transactions
WHERE transaction_type = 'customer_payment';

-- Calculate total expenses
SELECT
    transaction_type,
    SUM(ABS(amount)) as total
FROM financial_transactions
WHERE amount < 0
GROUP BY transaction_type;

-- Get profit/loss statement
SELECT
    SUM(CASE WHEN transaction_type = 'customer_payment' THEN amount ELSE 0 END) as revenue,
    SUM(CASE WHEN transaction_type = 'inventory_purchase' AND amount < 0 THEN amount ELSE 0 END) as cogs,
    SUM(CASE WHEN transaction_type = 'employee_payment' THEN amount ELSE 0 END) as payroll,
    SUM(CASE WHEN transaction_type = 'inventory_purchase' AND amount > 0 THEN amount ELSE 0 END) as inventory_purchases,
    SUM(amount) as net_profit
FROM financial_transactions;

-- Get transactions for a specific order
SELECT * FROM financial_transactions WHERE related_id = ? AND transaction_type = 'customer_payment';

-- Calculate daily cash flow
SELECT
    date,
    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as cash_in,
    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as cash_out,
    SUM(amount) as net_cash_flow
FROM financial_transactions
GROUP BY date
ORDER BY date;
```

**Agent Use Cases:**
- Cash flow optimization
- Budget forecasting
- Dynamic payroll adjustments
- Financial anomaly detection

---

### 5. Customers Database (`customers.db`)

**Purpose**: Pool of 1,000 pre-generated customers for order creation

#### Table: `customers`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique customer ID |
| `name` | TEXT | Full name |
| `street_address` | TEXT | Street address |
| `city` | TEXT | City |
| `state` | TEXT | State abbreviation |
| `zip_code` | TEXT | ZIP code |
| `email` | TEXT | Email address |
| `phone` | TEXT | Phone number |

**Common Queries:**

```sql
-- Get random customer
SELECT * FROM customers ORDER BY RANDOM() LIMIT 1;

-- Get customers by state
SELECT * FROM customers WHERE state = 'CA';

-- Count customers by state
SELECT state, COUNT(*) FROM customers GROUP BY state ORDER BY COUNT(*) DESC;
```

**Note:** This database is mostly static and used only for generating realistic order data.

---

## Business Rules & Constraints

### Order Processing Rules

1. **Inventory Check**: Before processing an order, ensure sufficient inventory:
   ```python
   # For each part in the BoM:
   parts_needed = quantity_per_widget * order_quantity
   if inventory_available < parts_needed:
       return "INSUFFICIENT_INVENTORY"
   ```

2. **Order Status Flow**: Must follow sequence:
   ```
   order_received → order_processing → order_shipped
   ```

3. **Manufacturing Stages**: Must complete in order:
   ```
   assembly → test → inspection → shipping
   ```

4. **Inventory Deduction**: When processing order, deduct from `inventory_levels`:
   ```python
   UPDATE inventory_levels
   SET quantity_available = quantity_available - parts_needed
   WHERE part_name = ?
   ```

5. **Financial Recording**: Each operation creates transactions:
   - Process order → negative `inventory_purchase` (COGS)
   - Restock → positive `inventory_purchase` (expense)
   - Ship order → positive `customer_payment` (revenue)
   - Payroll → negative `employee_payment` (expense)

### Inventory Rules

1. **Restock Threshold**: Typically restock when inventory < parts for 10 widgets
2. **Restock Target**: Order enough for 100 widgets of each type
3. **No Negative Inventory**: Never let `quantity_available` < 0

### Financial Rules

1. **Pricing**: Order prices already include ~30% margin over cost
2. **COGS**: Track inventory usage as negative `inventory_purchase`
3. **Payroll**: Process only on Fridays
4. **Payment**: Record when order ships, not when ordered

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
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Usage:
with get_connection('databases/crm.db', read_only=True) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
    for row in cursor.fetchall():
        print(row['order_id'], row['customer_name'])
```

### Check Inventory Availability

```python
def can_fulfill_order(widget_type, quantity):
    """Check if enough inventory exists to fulfill order."""
    with get_connection('databases/inventory.db', read_only=True) as conn:
        cursor = conn.cursor()

        # Get required parts
        cursor.execute("""
            SELECT b.part_name, b.quantity_needed, i.quantity_available
            FROM bom b
            JOIN inventory_levels i ON b.part_name = i.part_name
            WHERE b.widget_type = ?
        """, (widget_type,))

        for row in cursor.fetchall():
            needed = row['quantity_needed'] * quantity
            available = row['quantity_available']
            if available < needed:
                return False, f"Insufficient {row['part_name']}"

        return True, "OK"

# Usage:
can_fulfill, msg = can_fulfill_order('Widget_Pro', 10)
if not can_fulfill:
    print(f"Cannot fulfill order: {msg}")
```

### Get Order Status

```python
def get_order_details(order_id):
    """Get complete order information including production status."""
    with get_connection('databases/crm.db', read_only=True) as crm_conn:
        cursor = crm_conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()

    if not order:
        return None

    # Get production tracking
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
print(f"Order {details['order']['order_id']} - {details['order']['status']}")
for stage in details['stages']:
    print(f"  {stage['stage']}: {stage['completion_datetime'] or 'In progress'}")
```

### Calculate Inventory Value

```python
def calculate_inventory_value():
    """Calculate total value of current inventory."""
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

        total = 0
        for row in cursor.fetchall():
            total += row['total_value']

        return total

# Usage:
value = calculate_inventory_value()
print(f"Total inventory value: ${value:,.2f}")
```

---

## Agent Implementation Patterns

### Pattern 1: Monitoring Agent

Continuously monitors databases and alerts on conditions:

```python
import time
import sqlite3

class MonitoringAgent:
    def __init__(self):
        self.alert_threshold = 100  # Low inventory threshold

    def check_inventory(self):
        """Alert on low inventory."""
        with get_connection('databases/inventory.db', read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT part_name, quantity_available
                FROM inventory_levels
                WHERE quantity_available < ?
            """, (self.alert_threshold,))

            low_parts = cursor.fetchall()

        if low_parts:
            print(f"⚠️  LOW INVENTORY ALERT:")
            for part in low_parts:
                print(f"   {part['part_name']}: {part['quantity_available']} units")

    def run(self):
        """Main monitoring loop."""
        while True:
            self.check_inventory()
            time.sleep(60)  # Check every minute
```

### Pattern 2: Decision Agent

Makes intelligent decisions based on data:

```python
class RestockDecisionAgent:
    def should_restock(self):
        """Intelligent restocking decision."""
        # Get current inventory levels
        # Analyze order backlog
        # Predict future demand
        # Consider lead times
        # Make decision

        with get_connection('databases/inventory.db', read_only=True) as conn:
            cursor = conn.cursor()

            # Get critically low parts
            cursor.execute("""
                SELECT COUNT(*) FROM inventory_levels WHERE quantity_available < 50
            """)
            critical_count = cursor.fetchone()[0]

        # Simple rule: restock if 3+ parts are critically low
        return critical_count >= 3
```

### Pattern 3: Optimization Agent

Optimizes operations for efficiency:

```python
class OrderPrioritizationAgent:
    def prioritize_orders(self):
        """Return orders in optimal processing sequence."""
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

            orders = cursor.fetchall()

        # Sort by: high value first, urgent dates, then by widget type (batching)
        return sorted(orders, key=lambda x: (
            -x['total_value'],  # High value first (negative for desc)
            x['predicted_ship_date'],  # Urgent first
            x['widget_type']  # Group by type
        ))
```

---

## Testing Your Agent

### Unit Test Database State

```python
def test_inventory_check():
    """Test that inventory checking works correctly."""
    # Setup: Insert test data
    with get_connection('databases/inventory.db') as conn:
        conn.execute("UPDATE inventory_levels SET quantity_available = 5 WHERE part_name = 'Screw-1'")

    # Test
    can_fulfill, msg = can_fulfill_order('Widget_Pro', 100)

    # Assert
    assert not can_fulfill, "Should detect insufficient inventory"
    assert "Screw-1" in msg, "Should identify which part is low"
```

### Validate Business Rules

```python
def validate_order_flow():
    """Ensure orders follow proper status progression."""
    with get_connection('databases/crm.db', read_only=True) as conn:
        cursor = conn.cursor()

        # Check: No orders skip from received to shipped
        cursor.execute("""
            SELECT order_id FROM orders
            WHERE status = 'order_shipped'
            AND order_id NOT IN (
                SELECT DISTINCT order_id FROM production_tracking
            )
        """)

        invalid = cursor.fetchall()

    assert len(invalid) == 0, f"Found {len(invalid)} orders that skipped manufacturing"
```

---

## Common Pitfalls

### ❌ Don't: Forget to close connections
```python
conn = sqlite3.connect('databases/crm.db')
# ... do work ...
# ❌ Forgot conn.close() - will cause locks!
```

### ✅ Do: Use context managers
```python
with get_connection('databases/crm.db') as conn:
    # ... do work ...
# ✅ Automatically closed
```

### ❌ Don't: Modify databases without checking
```python
# ❌ Could create negative inventory!
conn.execute("UPDATE inventory_levels SET quantity_available = quantity_available - 1000")
```

### ✅ Do: Validate before modifying
```python
# ✅ Check first
cursor.execute("SELECT quantity_available FROM inventory_levels WHERE part_name = ?", (part,))
current = cursor.fetchone()[0]
if current >= amount_needed:
    conn.execute("UPDATE inventory_levels SET quantity_available = quantity_available - ?", (amount_needed,))
```

### ❌ Don't: Use string formatting for SQL
```python
# ❌ SQL injection risk!
cursor.execute(f"SELECT * FROM orders WHERE customer_name = '{name}'")
```

### ✅ Do: Use parameterized queries
```python
# ✅ Safe
cursor.execute("SELECT * FROM orders WHERE customer_name = ?", (name,))
```

---

## Quick Reference

### Database Files
- `databases/crm.db` - Orders
- `databases/inventory.db` - Parts & stock
- `databases/mes.db` - Manufacturing
- `databases/erp.db` - Money & people
- `databases/customers.db` - Customer pool

### Key Tables
- `orders` - All customer orders
- `bom` - What parts make each widget
- `inventory_levels` - Current stock
- `production_tracking` - Manufacturing stages
- `financial_transactions` - All money movement
- `employees` - Worker roster

### Status Values
- Orders: `order_received`, `order_processing`, `order_shipped`
- Stages: `assembly`, `test`, `inspection`, `shipping`
- Transaction types: `inventory_purchase`, `employee_payment`, `customer_payment`

### Connection Template
```python
import sqlite3
with sqlite3.connect('databases/X.db') as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    results = cursor.fetchall()
```

---

## Getting Help

- **Example Code**: See `example_monitor.py` and `sync_agent_example.py`
- **Database Tool**: Use `show_dbs.py` to export all data to markdown
- **Sync**: Read `AGENT_SYNC_GUIDE.md` for state file synchronization
- **Integration**: Read `AGENT_INTEGRATION.md` for patterns and examples

Good luck building your intelligent agent! 🤖
