# Agent Integration Guide

## Overview

This guide explains how to build agents that implement real business operations for Acme Widget Works. An agent connects directly to the company databases, reads the current state of orders, inventory, manufacturing, and financials, and writes back its decisions exactly as a human operator would.

Agents are designed to be portable. The business logic you write against the company databases works unchanged whether you are running against the development simulator or a live production environment.

---

## Configuring the Development Environment

When developing an agent, you can tell the simulator to skip a built-in operation so your agent handles it instead. This lets you test your agent against a live-changing dataset without it competing with the simulator's default logic.

| Operation | Flag | What your agent takes over |
|-----------|------|---------------------------|
| **Order Processing** | `--disable process` | Release orders to manufacturing: check inventory, deduct parts, create MES entries |
| **Manufacturing Ops** | `--disable ops` | Advance production stages, ship completed orders, record revenue |
| **Inventory Restocking** | `--disable restock` | Monitor stock levels, purchase parts, record transactions |
| **Employee Payroll** | `--disable payroll` | Pay employees, record payroll transactions |

```bash
# Develop an inventory agent — simulator generates orders and runs ops, your agent handles restocking
./venv/bin/python run_simulation.py 30 --disable restock

# Develop multiple agents at once
./venv/bin/python run_simulation.py 30 --disable process --disable ops

# Use step mode to pause between days while you inspect results and run your agent manually
./venv/bin/python run_simulation.py 7 --step --disable restock
```

The `--disable` flags are simulator configuration for your development session. Your agent itself does not need to know about them or reference them.

---

## Agent Patterns

### Pattern 1: Inventory Restocking Agent

Monitors stock levels and purchases parts when needed. Reads from `inventory.db`, writes restocking decisions back to `inventory.db`, and records transactions in `erp.db`.

```python
import sqlite3
from contextlib import contextmanager

DB_DIR = "databases"

@contextmanager
def get_db(name, read_only=False):
    conn = sqlite3.connect(f"{DB_DIR}/{name}")
    conn.row_factory = sqlite3.Row
    if read_only:
        conn.execute("PRAGMA query_only = ON")
    try:
        yield conn
        if not read_only:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class InventoryRestockAgent:
    """Manages parts purchasing based on current stock and pending demand."""

    def run(self, run_date: str):
        shortfalls = self._assess_needs()
        if shortfalls:
            print(f"Restocking {len(shortfalls)} parts...")
            self._purchase_parts(shortfalls, run_date)
        else:
            print("Inventory sufficient — no action needed")

    def _assess_needs(self):
        """Identify parts insufficient to cover pending orders."""
        with get_db("inventory.db", read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT part_name, quantity_available FROM inventory_levels")
            stock = {row["part_name"]: row["quantity_available"] for row in cursor.fetchall()}
            cursor.execute("SELECT part_name, widget_type, quantity_needed, unit_cost FROM bom")
            bom = cursor.fetchall()

        with get_db("crm.db", read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT widget_type, SUM(quantity) as total_qty
                FROM orders WHERE status = 'order_received'
                GROUP BY widget_type
            """)
            demand = {row["widget_type"]: row["total_qty"] for row in cursor.fetchall()}

        shortfalls = {}
        for row in bom:
            needed = row["quantity_needed"] * demand.get(row["widget_type"], 0)
            available = stock.get(row["part_name"], 0)
            if available < needed:
                deficit = needed - available
                if row["part_name"] not in shortfalls or shortfalls[row["part_name"]]["deficit"] < deficit:
                    shortfalls[row["part_name"]] = {
                        "deficit": deficit,
                        "unit_cost": row["unit_cost"]
                    }
        return shortfalls

    def _purchase_parts(self, shortfalls, purchase_date):
        """Buy parts to cover shortfalls, update inventory, record transactions."""
        with get_db("inventory.db") as inv_conn:
            with get_db("erp.db") as erp_conn:
                for part_name, info in shortfalls.items():
                    qty = info["deficit"]
                    cost = round(qty * info["unit_cost"], 2)

                    inv_conn.execute(
                        "UPDATE inventory_levels SET quantity_available = quantity_available + ? WHERE part_name = ?",
                        (qty, part_name)
                    )
                    erp_conn.execute("""
                        INSERT INTO financial_transactions
                            (transaction_type, amount, date, description)
                        VALUES ('inventory_purchase', ?, ?, ?)
                    """, (cost, purchase_date, f"Restocked {part_name}: {qty} units"))

                    print(f"  {part_name}: +{qty} units (${cost:,.2f})")
```

### Pattern 2: Order Processing Agent

Accepts pending orders into manufacturing. Reads from `crm.db` and `inventory.db`, deducts parts, creates MES entries, and records COGS in `erp.db`.

```python
class OrderProcessingAgent:
    """Releases orders from the queue into manufacturing."""

    def run(self, process_datetime: str):
        with get_db("crm.db", read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT order_id, widget_type, quantity
                FROM orders WHERE status = 'order_received'
                ORDER BY order_id
            """)
            pending = cursor.fetchall()

        for order in pending:
            ok, issues = self._check_inventory(order["widget_type"], order["quantity"])
            if ok:
                self._process_order(order["order_id"], order["widget_type"],
                                    order["quantity"], process_datetime)
            else:
                print(f"Order #{order['order_id']} skipped — {'; '.join(issues)}")

    def _check_inventory(self, widget_type, quantity):
        with get_db("inventory.db", read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.part_name, b.quantity_needed, i.quantity_available
                FROM bom b
                JOIN inventory_levels i ON b.part_name = i.part_name
                WHERE b.widget_type = ?
            """, (widget_type,))
            shortfalls = [
                f"{r['part_name']} (need {r['quantity_needed'] * quantity}, have {r['quantity_available']})"
                for r in cursor.fetchall()
                if r["quantity_available"] < r["quantity_needed"] * quantity
            ]
        return len(shortfalls) == 0, shortfalls

    def _process_order(self, order_id, widget_type, quantity, process_datetime):
        with get_db("inventory.db", read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT part_name, quantity_needed, unit_cost FROM bom WHERE widget_type = ?",
                (widget_type,)
            )
            bom = cursor.fetchall()

        total_cost = sum(p["quantity_needed"] * quantity * p["unit_cost"] for p in bom)

        with get_db("inventory.db") as inv:
            for part in bom:
                inv.execute(
                    "UPDATE inventory_levels SET quantity_available = quantity_available - ? WHERE part_name = ?",
                    (part["quantity_needed"] * quantity, part["part_name"])
                )

        with get_db("crm.db") as crm:
            crm.execute(
                "UPDATE orders SET status = 'order_processing' WHERE order_id = ?",
                (order_id,)
            )

        with get_db("mes.db") as mes:
            for stage in ["assembly", "test", "inspection", "shipping"]:
                mes.execute(
                    "INSERT INTO production_tracking (order_id, stage, start_datetime) VALUES (?, ?, ?)",
                    (order_id, stage, process_datetime if stage == "assembly" else None)
                )

        with get_db("erp.db") as erp:
            erp.execute("""
                INSERT INTO financial_transactions
                    (transaction_type, amount, date, description, related_id)
                VALUES ('inventory_purchase', ?, ?, ?, ?)
            """, (-round(total_cost, 2), process_datetime[:10],
                  f"Inventory consumed for Order #{order_id} ({quantity}x {widget_type})",
                  order_id))

        print(f"Order #{order_id} released to manufacturing (COGS: ${total_cost:,.2f})")
```

### Pattern 3: Decision-Making Agent

Uses business data to make intelligent choices rather than applying fixed rules:

```python
class PricingAdvisorAgent:
    """
    Monitors margin on recent orders and flags orders priced below target.
    Read-only — does not modify any data.
    """

    def run(self, run_date: str, lookback_days: int = 7):
        with get_db("crm.db", read_only=True) as crm:
            cursor = crm.cursor()
            cursor.execute("""
                SELECT order_id, widget_type, quantity, unit_price,
                       quantity * unit_price as revenue
                FROM orders
                WHERE date_ordered >= date(?, ?)
                AND status != 'order_received'
            """, (run_date, f"-{lookback_days} days"))
            orders = cursor.fetchall()

        with get_db("inventory.db", read_only=True) as inv:
            cursor = inv.cursor()
            cursor.execute("""
                SELECT widget_type, SUM(quantity_needed * unit_cost) as mfg_cost
                FROM bom GROUP BY widget_type
            """)
            costs = {row["widget_type"]: row["mfg_cost"] for row in cursor.fetchall()}

        for order in orders:
            mfg_cost = costs.get(order["widget_type"], 0) * order["quantity"]
            margin = (order["revenue"] - mfg_cost) / order["revenue"] if order["revenue"] else 0
            if margin < 0.20:
                print(f"Low margin alert: Order #{order['order_id']} "
                      f"({order['widget_type']}) margin={margin:.1%}")


class WorkflowOptimizationAgent:
    """Returns pending orders sorted for maximum business impact."""

    def get_prioritized_orders(self):
        with get_db("crm.db", read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT order_id, widget_type, quantity, unit_price,
                       quantity * unit_price as total_value, predicted_ship_date
                FROM orders WHERE status = 'order_received'
            """)
            orders = [dict(row) for row in cursor.fetchall()]

        # Highest value first, then nearest deadline, then batch by widget type
        return sorted(orders, key=lambda x: (
            -x["total_value"],
            x["predicted_ship_date"],
            x["widget_type"]
        ))
```

---

## Scheduling

Agents are triggered by date and time. See the [Agent Synchronization Guide](AGENT_SYNC_GUIDE.md) for patterns on scheduling agents via cron, event bus, or fixed-interval polling, and for how to run agents alongside the simulator during development.

---

## Testing Your Agent

### 1. Run the simulator with one operation disabled, manually trigger your agent each day

```bash
# Terminal 1 — simulator handles everything except restocking
./venv/bin/python run_simulation.py 7 --step --disable restock
```

After each simulated day pauses, run your agent in a second terminal:
```bash
python restock_agent.py 2026-03-01
```

### 2. Validate database integrity after each action

```python
def check_no_negative_inventory():
    with get_db("inventory.db", read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT part_name, quantity_available FROM inventory_levels WHERE quantity_available < 0"
        )
        problems = cursor.fetchall()
    assert not problems, f"Negative inventory: {[p['part_name'] for p in problems]}"

def check_transaction_integrity():
    with get_db("erp.db", read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) as net FROM financial_transactions")
        net = cursor.fetchone()["net"] or 0
    print(f"Net financial position: ${net:,.2f}")
```

### 3. Compare outcomes

Run the simulator with and without your agent for the same date range, then compare the final financial summary to measure whether your agent improved on the default behavior.

---

## Tips for Agent Development

1. **Write to databases directly** — your agent's interface is the company databases, not simulator scripts or utilities
2. **Start with read-only monitoring** — understand the data flow before writing anything
3. **Test one operation at a time** — disable a single operation and verify your agent handles it correctly before tackling multiple
4. **Log your decisions** — record what your agent decided and why; raw database state alone is hard to debug
5. **Check invariants after every write** — no negative inventory, no duplicate transactions, status transitions in order
6. **Make agents idempotent** — running an agent twice for the same date should produce the same result, not duplicate records
