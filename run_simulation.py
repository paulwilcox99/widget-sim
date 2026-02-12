#!/usr/bin/env python3
"""
Company Simulation Tool - Run a complete multi-day simulation of the manufacturing company.

This script orchestrates all company operations over multiple days:
- Order generation
- Order processing
- Manufacturing operations
- Inventory management
- Payroll processing
"""

import sys
import argparse
import subprocess
import random
from datetime import datetime, timedelta
from pathlib import Path


# Script paths
SCRIPT_DIR = Path(__file__).parent
VENV_PYTHON = SCRIPT_DIR / "venv" / "bin" / "python"

CREATE_SIM = SCRIPT_DIR / "create_sim.py"
GEN_ORDER = SCRIPT_DIR / "gen_order.py"
PROCESS_ORDER = SCRIPT_DIR / "process_order.py"
UPDATE_INVENTORY = SCRIPT_DIR / "update_inventory.py"
RUN_OPS = SCRIPT_DIR / "run_ops.py"
PAY_EMPLOYEES = SCRIPT_DIR / "pay_employees.py"


def run_command(script: Path, args: list = None, description: str = None) -> bool:
    """
    Run a script and return success status.

    Args:
        script: Path to script to run
        args: Optional list of arguments
        description: Optional description for logging

    Returns:
        True if successful, False otherwise
    """
    cmd = [str(VENV_PYTHON), str(script)]
    if args:
        cmd.extend(args)

    if description:
        print(f"  → {description}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"    ✗ Error: {result.stderr[:200]}")
            return False
        return True
    except Exception as e:
        print(f"    ✗ Exception: {e}")
        return False


def initialize_databases() -> bool:
    """
    Initialize all databases for a fresh simulation.

    Returns:
        True if successful, False otherwise
    """
    print("\n" + "=" * 70)
    print("INITIALIZING SIMULATION")
    print("=" * 70)

    cmd = [str(VENV_PYTHON), str(CREATE_SIM)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"✗ Failed to initialize databases: {result.stderr[:200]}")
            return False

        # Print output from create_sim
        print(result.stdout)
        return True
    except Exception as e:
        print(f"✗ Exception during initialization: {e}")
        return False


def simulate_day(day_num: int, current_date: datetime, total_days: int):
    """
    Simulate one day of company operations.

    Args:
        day_num: Current day number (1-indexed)
        current_date: Current simulation date
        total_days: Total number of days to simulate
    """
    date_str = current_date.strftime("%Y-%m-%d")
    day_name = current_date.strftime("%A")

    print("\n" + "=" * 70)
    print(f"DAY {day_num}/{total_days}: {date_str} ({day_name})")
    print("=" * 70)

    # Morning operations (09:00)
    morning_time = current_date.replace(hour=9, minute=0, second=0)
    morning_str = morning_time.strftime("%Y-%m-%d %H:%M:%S")

    # Generate random number of orders (0-20)
    num_orders = random.randint(0, 20)
    if num_orders > 0:
        print(f"\n📋 Generating {num_orders} new orders...")
        for i in range(num_orders):
            run_command(GEN_ORDER, [morning_str], None)
        print(f"  ✓ Generated {num_orders} orders at {morning_str}")
    else:
        print(f"\n📋 No new orders today")

    # Advance time by 1 hour (10:00)
    work_time = morning_time + timedelta(hours=1)
    work_str = work_time.strftime("%Y-%m-%d %H:%M:%S")

    # Process orders
    print(f"\n⚙️  Processing orders at {work_str}...")
    run_command(PROCESS_ORDER, [work_str], "Processing new orders")

    # Run manufacturing operations
    print(f"\n🏭 Running manufacturing operations at {work_str}...")
    run_command(RUN_OPS, [work_str], "Advancing production stages")

    # Update inventory every 3 days
    if day_num % 3 == 0:
        print(f"\n📦 Inventory restock day (every 3 days)...")
        run_command(UPDATE_INVENTORY, [date_str], "Checking and restocking inventory")

    # Pay employees on Fridays
    if current_date.weekday() == 4:  # Friday
        print(f"\n💰 Payroll day (Friday)...")
        run_command(PAY_EMPLOYEES, [date_str], "Processing employee payroll")

    print(f"\n✓ Day {day_num} complete")


def print_final_summary():
    """Print final simulation summary."""
    print("\n" + "=" * 70)
    print("SIMULATION COMPLETE - FINAL SUMMARY")
    print("=" * 70)

    try:
        # Import sqlite3 for summary queries
        import sqlite3

        # CRM Summary
        conn = sqlite3.connect('databases/crm.db')
        cursor = conn.cursor()
        cursor.execute('SELECT status, COUNT(*), SUM(quantity * unit_price) FROM orders GROUP BY status')
        print("\nORDER SUMMARY:")
        print("-" * 70)
        total_orders = 0
        total_value = 0
        for status, count, value in cursor.fetchall():
            total_orders += count
            total_value += value if value else 0
            print(f"  {status:20s}: {count:4d} orders | ${value if value else 0:12,.2f}")
        print(f"  {'TOTAL':20s}: {total_orders:4d} orders | ${total_value:12,.2f}")
        conn.close()

        # Financial Summary
        conn = sqlite3.connect('databases/erp.db')
        cursor = conn.cursor()

        print("\nFINANCIAL SUMMARY:")
        print("-" * 70)

        # Revenue
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM financial_transactions WHERE transaction_type = "customer_payment"')
        count, revenue = cursor.fetchone()
        revenue = revenue if revenue else 0
        print(f"  Revenue (shipped):     {count:4d} payments | ${revenue:12,.2f}")

        # COGS
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM financial_transactions WHERE transaction_type = "inventory_purchase" AND amount < 0')
        count, cogs = cursor.fetchone()
        cogs = abs(cogs) if cogs else 0
        print(f"  COGS (inventory used): {count:4d} txns     | ${cogs:12,.2f}")

        # Gross Profit
        gross_profit = revenue - cogs
        print(f"  Gross Profit:                           | ${gross_profit:12,.2f}")

        # Payroll
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM financial_transactions WHERE transaction_type = "employee_payment"')
        count, payroll = cursor.fetchone()
        payroll = abs(payroll) if payroll else 0
        print(f"  Payroll:               {count:4d} payments | ${payroll:12,.2f}")

        # Inventory purchases
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM financial_transactions WHERE transaction_type = "inventory_purchase" AND amount > 0')
        count, inv_cost = cursor.fetchone()
        inv_cost = inv_cost if inv_cost else 0
        print(f"  Inventory purchases:   {count:4d} orders   | ${inv_cost:12,.2f}")

        # Net profit
        net_profit = revenue - cogs - payroll - inv_cost
        print(f"  Net Profit/Loss:                        | ${net_profit:12,.2f}")

        # Cash flow
        cash_in = revenue
        cash_out = payroll + inv_cost
        net_cash = cash_in - cash_out
        print(f"\nCASH FLOW:")
        print(f"  Cash in:                                | ${cash_in:12,.2f}")
        print(f"  Cash out:                               | ${cash_out:12,.2f}")
        print(f"  Net Cash Flow:                          | ${net_cash:12,.2f}")

        conn.close()

        # Inventory Summary
        conn = sqlite3.connect('databases/inventory.db')
        cursor = conn.cursor()
        cursor.execute('SELECT MIN(quantity_available), MAX(quantity_available), AVG(quantity_available) FROM inventory_levels')
        min_inv, max_inv, avg_inv = cursor.fetchone()

        print("\nINVENTORY STATUS:")
        print("-" * 70)
        print(f"  Minimum stock level:   {min_inv:6d} units")
        print(f"  Maximum stock level:   {max_inv:6d} units")
        print(f"  Average stock level:   {avg_inv:6.0f} units")
        conn.close()

    except Exception as e:
        print(f"\n⚠ Could not generate summary: {e}")


def main():
    """Main simulation function."""
    parser = argparse.ArgumentParser(
        description="Run a multi-day simulation of the manufacturing company",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How it works:
  1. Initializes fresh databases
  2. For each day:
     - Generates 0-20 random orders at 09:00
     - Processes orders at 10:00
     - Advances manufacturing at 10:00
     - Updates inventory every 3 days
     - Pays employees on Fridays
  3. Displays final summary

Examples:
  %(prog)s 30                                # Simulate 30 days from today
  %(prog)s 30 "2026-02-01"                   # Simulate 30 days starting Feb 1
  %(prog)s 60 "2026-01-01"                   # Simulate 2 months from Jan 1
  %(prog)s 7 --step                          # Step through 7 days interactively
  %(prog)s 30 "2026-03-01" --step --no-init  # Step mode with existing DB
        """
    )
    parser.add_argument(
        "days",
        type=int,
        help="Number of days to simulate"
    )
    parser.add_argument(
        "start_date",
        nargs="?",
        default=None,
        help="Start date (YYYY-MM-DD). If not provided, uses current date."
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Skip database initialization (use existing databases)"
    )
    parser.add_argument(
        "--step",
        action="store_true",
        help="Run in step mode - pause after each day for user input"
    )

    args = parser.parse_args()

    # Validate inputs
    if args.days <= 0:
        print("Error: Number of days must be positive", file=sys.stderr)
        sys.exit(1)

    # Parse start date
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format: {args.start_date}", file=sys.stderr)
            print("Use YYYY-MM-DD format", file=sys.stderr)
            sys.exit(1)
    else:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Print simulation parameters
    print("=" * 70)
    print("MANUFACTURING COMPANY SIMULATION")
    print("=" * 70)
    print(f"Start date:     {start_date.strftime('%Y-%m-%d (%A)')}")
    print(f"Duration:       {args.days} days")
    end_date = start_date + timedelta(days=args.days - 1)
    print(f"End date:       {end_date.strftime('%Y-%m-%d (%A)')}")
    print(f"Initialize DB:  {'No (using existing)' if args.no_init else 'Yes (fresh start)'}")
    print(f"Step mode:      {'Yes (interactive)' if args.step else 'No (continuous)'}")

    # Initialize databases if requested
    if not args.no_init:
        if not initialize_databases():
            print("\n✗ Failed to initialize databases. Exiting.")
            sys.exit(1)

    # Run simulation
    try:
        current_date = start_date
        for day_num in range(1, args.days + 1):
            simulate_day(day_num, current_date, args.days)
            current_date += timedelta(days=1)

            # Step mode - pause for user input
            if args.step and day_num < args.days:
                print("\n" + "-" * 70)
                user_input = input("Press Enter to continue to next day (or 'q' to quit, 's' for summary): ").strip().lower()

                if user_input == 'q':
                    print("\n⚠ Simulation stopped by user")
                    print_final_summary()
                    sys.exit(0)
                elif user_input == 's':
                    print_final_summary()
                    print("\n" + "-" * 70)
                    input("Press Enter to continue simulation: ")

        # Print final summary
        print_final_summary()

        print("\n" + "=" * 70)
        print("✓ SIMULATION COMPLETED SUCCESSFULLY")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\n⚠ Simulation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Simulation error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
