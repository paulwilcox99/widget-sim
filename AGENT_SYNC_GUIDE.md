# Agent Synchronization Guide

## Overview

Agents for Acme Widget Works are triggered by date and time and work directly against the company databases. There is no special synchronization protocol — an agent simply runs on a schedule, reads the current state of the business from the databases, makes decisions, and writes results back.

This is the same model whether you are running in development (triggered manually or by cron against the simulator's databases) or in production (triggered by your scheduler against live systems).

---

## How Agents Are Triggered

Agents receive a date as input — either passed as an argument or derived from the current date — and use that date to scope their work and timestamp any records they write.

```python
#!/usr/bin/env python3
"""
Inventory restock agent.
Run daily via cron: 0 8 * * * /usr/bin/python3 /path/to/restock_agent.py
"""

import sys
from datetime import date


def main():
    # Accept an optional date argument for testing; default to today
    if len(sys.argv) > 1:
        run_date = sys.argv[1]   # YYYY-MM-DD
    else:
        run_date = date.today().isoformat()

    agent = RestockAgent(db_dir="/path/to/databases")
    agent.run(run_date)


if __name__ == "__main__":
    main()
```

Cron example — run restocking agent every morning at 8 AM:
```
0 8 * * * /usr/bin/python3 /opt/agents/restock_agent.py >> /var/log/restock_agent.log 2>&1
```

Payroll agent — run every Friday:
```
0 9 * * 5 /usr/bin/python3 /opt/agents/payroll_agent.py >> /var/log/payroll_agent.log 2>&1
```

---

## Agent Structure

Every agent follows the same pattern: receive a date, read from the databases, decide, write back.

```python
import sqlite3
from contextlib import contextmanager


@contextmanager
def get_db(db_path, read_only=False):
    """Context manager for safe database connections."""
    conn = sqlite3.connect(db_path)
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


class RestockAgent:
    def __init__(self, db_dir="databases"):
        self.crm_db    = f"{db_dir}/crm.db"
        self.inv_db    = f"{db_dir}/inventory.db"
        self.erp_db    = f"{db_dir}/erp.db"

    def run(self, run_date: str):
        """
        Entry point. Called by the scheduler with today's date.
        Reads current state, decides what to purchase, writes results.
        """
        shortfalls = self._assess_shortfalls()

        if not shortfalls:
            print(f"{run_date}: inventory sufficient, no action needed")
            return

        print(f"{run_date}: restocking {len(shortfalls)} parts")
        self._purchase_parts(shortfalls, run_date)

    def _assess_shortfalls(self):
        """Compare current stock against what pending orders require."""
        with get_db(self.inv_db, read_only=True) as inv:
            cursor = inv.cursor()
            cursor.execute("SELECT part_name, quantity_available FROM inventory_levels")
            stock = {row["part_name"]: row["quantity_available"] for row in cursor.fetchall()}
            cursor.execute("SELECT part_name, widget_type, quantity_needed, unit_cost FROM bom")
            bom = cursor.fetchall()

        with get_db(self.crm_db, read_only=True) as crm:
            cursor = crm.cursor()
            cursor.execute("""
                SELECT widget_type, SUM(quantity) as total
                FROM orders WHERE status = 'order_received'
                GROUP BY widget_type
            """)
            demand = {row["widget_type"]: row["total"] for row in cursor.fetchall()}

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
        """Write inventory increases and financial transactions."""
        with get_db(self.inv_db) as inv:
            with get_db(self.erp_db) as erp:
                for part_name, info in shortfalls.items():
                    qty  = info["deficit"]
                    cost = round(qty * info["unit_cost"], 2)

                    inv.execute(
                        "UPDATE inventory_levels SET quantity_available = quantity_available + ? WHERE part_name = ?",
                        (qty, part_name)
                    )
                    erp.execute("""
                        INSERT INTO financial_transactions
                            (transaction_type, amount, date, description)
                        VALUES ('inventory_purchase', ?, ?, ?)
                    """, (cost, purchase_date, f"Restocked {part_name}: {qty} units"))

                    print(f"  {part_name}: +{qty} units (${cost:,.2f})")
```

---

## Multi-Agent Coordination

When multiple agents run on the same databases, each agent owns a specific domain and they coordinate through the data itself — not through any shared messaging layer.

| Agent | Reads | Writes |
|-------|-------|--------|
| Order processing agent | `crm.db` orders (status=order_received), `inventory.db` bom + levels | `inventory.db` levels, `crm.db` status, `mes.db` tracking, `erp.db` transactions |
| Manufacturing ops agent | `crm.db` orders (status=order_processing), `mes.db` tracking | `mes.db` tracking, `crm.db` status + date_shipped, `erp.db` transactions |
| Restock agent | `inventory.db` levels + bom, `crm.db` pending orders | `inventory.db` levels, `erp.db` transactions |
| Payroll agent | `erp.db` employees | `erp.db` transactions |

Because each agent touches different tables (or uses row-level status fields to claim work), they do not need to know about each other. The databases are the coordination layer.

---

## Handling Day-of-Week Logic

Some operations only run on certain days. The agent checks the date it receives:

```python
from datetime import date, datetime

def run(self, run_date: str):
    dt = datetime.strptime(run_date, "%Y-%m-%d")

    # Payroll only on Fridays (weekday 4)
    if dt.weekday() != 4:
        print(f"{run_date} is not a Friday — payroll skipped")
        return

    self._process_payroll(run_date)

def _process_payroll(self, pay_date):
    with get_db(self.erp_db, read_only=True) as erp:
        cursor = erp.cursor()
        cursor.execute("SELECT employee_id, name, title, weekly_salary FROM employees")
        employees = cursor.fetchall()

    with get_db(self.erp_db) as erp:
        for emp in employees:
            erp.execute("""
                INSERT INTO financial_transactions
                    (transaction_type, amount, date, description, related_id)
                VALUES ('employee_payment', ?, ?, ?, ?)
            """, (-emp["weekly_salary"], pay_date,
                  f"Weekly salary: {emp['name']} ({emp['title']})", emp["employee_id"]))

    print(f"Payroll complete: {len(employees)} employees paid")
```

---

## Idempotency

Agents should be safe to run more than once for the same date without creating duplicate records. Check before writing:

```python
def _already_paid_today(self, pay_date):
    """Return True if payroll was already processed for this date."""
    with get_db(self.erp_db, read_only=True) as erp:
        cursor = erp.cursor()
        cursor.execute("""
            SELECT COUNT(*) as n FROM financial_transactions
            WHERE transaction_type = 'employee_payment' AND date = ?
        """, (pay_date,))
        return cursor.fetchone()["n"] > 0

def run(self, run_date):
    if self._already_paid_today(run_date):
        print(f"{run_date}: payroll already processed, skipping")
        return
    self._process_payroll(run_date)
```

---

## Developing Against the Simulator

The simulator generates realistic business activity across the company databases each simulated day. To develop your agent against it:

1. Start the simulator with the operation your agent will handle disabled:
   ```bash
   ./venv/bin/python run_simulation.py 30 "2026-03-01" --disable restock --step
   ```

2. After each simulated day completes, run your agent manually with that day's date:
   ```bash
   python restock_agent.py 2026-03-01
   ```

3. Use `--step` mode so you can inspect the databases between days before advancing.

The agent receives the date as a plain argument, reads the databases, and writes back — exactly as it will in production. There is nothing simulator-specific in the agent code.
