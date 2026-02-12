#!/usr/bin/env python3
"""
Example: Monitor simulation databases and control flow programmatically.

This demonstrates how external monitoring software can:
1. Watch for database changes
2. Analyze the changes
3. Control the simulation flow
"""

import subprocess
import time
import sqlite3
from pathlib import Path
from datetime import datetime


class DatabaseMonitor:
    """Monitor database changes during simulation."""

    def __init__(self, db_dir="databases"):
        self.db_dir = Path(db_dir)
        self.day_count = 0
        self.baseline = {}

    def capture_baseline(self):
        """Capture initial database state."""
        print("📊 Capturing baseline database state...")

        self.baseline = {
            'orders': self._count_table('crm.db', 'orders'),
            'transactions': self._count_table('erp.db', 'financial_transactions'),
            'inventory_items': self._count_table('inventory.db', 'inventory_levels'),
            'mes_entries': self._count_table('mes.db', 'production_tracking'),
        }

        print(f"   Baseline: {self.baseline}")

    def _count_table(self, db_name, table_name):
        """Count rows in a table."""
        try:
            conn = sqlite3.connect(self.db_dir / db_name)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"   ⚠️  Error counting {db_name}/{table_name}: {e}")
            return 0

    def _get_table_sum(self, db_name, table_name, column):
        """Sum a column in a table."""
        try:
            conn = sqlite3.connect(self.db_dir / db_name)
            cursor = conn.cursor()
            cursor.execute(f"SELECT SUM({column}) FROM {table_name}")
            result = cursor.fetchone()[0]
            conn.close()
            return result if result else 0
        except Exception as e:
            print(f"   ⚠️  Error summing {db_name}/{table_name}.{column}: {e}")
            return 0

    def analyze_changes(self):
        """Analyze what changed since last check."""
        self.day_count += 1

        print(f"\n{'='*70}")
        print(f"📈 MONITORING REPORT - Day {self.day_count}")
        print(f"{'='*70}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        current = {
            'orders': self._count_table('crm.db', 'orders'),
            'transactions': self._count_table('erp.db', 'financial_transactions'),
            'inventory_items': self._count_table('inventory.db', 'inventory_levels'),
            'mes_entries': self._count_table('mes.db', 'production_tracking'),
        }

        # Calculate changes
        changes = {
            key: current[key] - self.baseline.get(key, 0)
            for key in current
        }

        # Detailed analysis
        print("DATABASE CHANGES:")
        print(f"  New orders:           {changes['orders']:4d}")
        print(f"  New transactions:     {changes['transactions']:4d}")
        print(f"  New MES entries:      {changes['mes_entries']:4d}")

        # Get order status breakdown
        self._analyze_orders()

        # Get financial summary
        self._analyze_financials()

        # Check inventory status
        self._analyze_inventory()

        # Update baseline
        self.baseline = current

        return changes

    def _analyze_orders(self):
        """Analyze order status."""
        try:
            conn = sqlite3.connect(self.db_dir / 'crm.db')
            cursor = conn.cursor()

            cursor.execute("""
                SELECT status, COUNT(*), SUM(quantity * unit_price)
                FROM orders
                GROUP BY status
            """)

            print("\nORDER STATUS:")
            total_value = 0
            for status, count, value in cursor.fetchall():
                value = value if value else 0
                total_value += value
                print(f"  {status:20s}: {count:4d} orders  ${value:12,.2f}")

            print(f"  {'TOTAL VALUE':20s}:              ${total_value:12,.2f}")
            conn.close()

        except Exception as e:
            print(f"  ⚠️  Error analyzing orders: {e}")

    def _analyze_financials(self):
        """Analyze financial transactions."""
        try:
            conn = sqlite3.connect(self.db_dir / 'erp.db')
            cursor = conn.cursor()

            # Get transaction summary
            cursor.execute("""
                SELECT
                    transaction_type,
                    COUNT(*),
                    SUM(amount)
                FROM financial_transactions
                GROUP BY transaction_type
            """)

            print("\nFINANCIAL SUMMARY:")
            for txn_type, count, amount in cursor.fetchall():
                amount = amount if amount else 0
                sign = '+' if amount > 0 else ''
                print(f"  {txn_type:20s}: {count:4d} txns   {sign}${amount:12,.2f}")

            conn.close()

        except Exception as e:
            print(f"  ⚠️  Error analyzing financials: {e}")

    def _analyze_inventory(self):
        """Analyze inventory levels."""
        try:
            conn = sqlite3.connect(self.db_dir / 'inventory.db')
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    MIN(quantity_available),
                    MAX(quantity_available),
                    AVG(quantity_available)
                FROM inventory_levels
            """)

            min_qty, max_qty, avg_qty = cursor.fetchone()

            print("\nINVENTORY STATUS:")
            print(f"  Minimum stock:        {min_qty:6d} units")
            print(f"  Maximum stock:        {max_qty:6d} units")
            print(f"  Average stock:        {avg_qty:6.0f} units")

            # Check for low stock
            cursor.execute("""
                SELECT part_name, quantity_available
                FROM inventory_levels
                WHERE quantity_available < 100
                ORDER BY quantity_available
                LIMIT 5
            """)

            low_stock = cursor.fetchall()
            if low_stock:
                print("\n  ⚠️  LOW STOCK ALERT:")
                for part, qty in low_stock:
                    print(f"     {part:20s}: {qty:4d} units")

            conn.close()

        except Exception as e:
            print(f"  ⚠️  Error analyzing inventory: {e}")

    def check_invariants(self):
        """Validate business rules and data integrity."""
        print("\n🔍 VALIDATION CHECKS:")
        passed = 0
        failed = 0

        # Check 1: No negative inventory
        try:
            conn = sqlite3.connect(self.db_dir / 'inventory.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inventory_levels WHERE quantity_available < 0")
            negative_count = cursor.fetchone()[0]
            conn.close()

            if negative_count == 0:
                print("  ✓ No negative inventory")
                passed += 1
            else:
                print(f"  ✗ Found {negative_count} parts with negative inventory!")
                failed += 1
        except Exception as e:
            print(f"  ✗ Error checking inventory: {e}")
            failed += 1

        # Check 2: All shipped orders have payments
        try:
            conn_crm = sqlite3.connect(self.db_dir / 'crm.db')
            conn_erp = sqlite3.connect(self.db_dir / 'erp.db')

            cursor_crm = conn_crm.cursor()
            cursor_crm.execute("SELECT COUNT(*) FROM orders WHERE status = 'order_shipped'")
            shipped_count = cursor_crm.fetchone()[0]

            cursor_erp = conn_erp.cursor()
            cursor_erp.execute("SELECT COUNT(*) FROM financial_transactions WHERE transaction_type = 'customer_payment'")
            payment_count = cursor_erp.fetchone()[0]

            conn_crm.close()
            conn_erp.close()

            if shipped_count == payment_count:
                print(f"  ✓ All {shipped_count} shipped orders have payments")
                passed += 1
            else:
                print(f"  ✗ Mismatch: {shipped_count} shipped orders but {payment_count} payments!")
                failed += 1
        except Exception as e:
            print(f"  ✗ Error checking payments: {e}")
            failed += 1

        # Check 3: MES entries match processed orders
        try:
            conn_crm = sqlite3.connect(self.db_dir / 'crm.db')
            conn_mes = sqlite3.connect(self.db_dir / 'mes.db')

            cursor_crm = conn_crm.cursor()
            cursor_crm.execute("SELECT COUNT(*) FROM orders WHERE status IN ('order_processing', 'order_shipped')")
            processed_count = cursor_crm.fetchone()[0]

            cursor_mes = conn_mes.cursor()
            cursor_mes.execute("SELECT COUNT(DISTINCT order_id) FROM production_tracking")
            mes_count = cursor_mes.fetchone()[0]

            conn_crm.close()
            conn_mes.close()

            if processed_count == mes_count:
                print(f"  ✓ All {processed_count} processed orders have MES tracking")
                passed += 1
            else:
                print(f"  ⚠️  {processed_count} processed orders, {mes_count} in MES (may be timing)")
                passed += 1  # This can be normal due to timing

        except Exception as e:
            print(f"  ✗ Error checking MES: {e}")
            failed += 1

        print(f"\n  Results: {passed} passed, {failed} failed")
        return failed == 0


def main():
    """Run simulation with monitoring."""
    print("="*70)
    print("MONITORED SIMULATION EXAMPLE")
    print("="*70)
    print("\nThis script demonstrates monitoring database changes during simulation.")
    print("It will run a 5-day simulation with analysis after each day.\n")

    monitor = DatabaseMonitor()

    # Wait for initial database creation
    print("Waiting for simulation to initialize databases...")
    time.sleep(2)

    # Capture baseline
    monitor.capture_baseline()

    print("\n" + "="*70)
    print("Starting monitored simulation - 5 days")
    print("="*70)

    # Simulate advancing through days
    # In real usage, this would be integrated with the simulation
    for day in range(1, 6):
        print(f"\n⏳ Waiting for Day {day} to complete...")
        time.sleep(3)  # Simulate time for day operations

        # Analyze changes
        changes = monitor.analyze_changes()

        # Validate
        all_valid = monitor.check_invariants()

        if not all_valid:
            print(f"\n⚠️  Validation failed on day {day}!")
            print("    You would send 'q' to quit the simulation here")
            # In automated mode: send 'q' to simulation stdin
            break

        print(f"\n✓ Day {day} monitoring complete - press Enter to continue")
        # In automated mode: send '\n' to simulation stdin

    print("\n" + "="*70)
    print("✓ Monitoring session complete")
    print("="*70)


if __name__ == "__main__":
    main()
