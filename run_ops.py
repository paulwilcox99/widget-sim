#!/usr/bin/env python3
"""
Manufacturing Operations Tool - Advance orders through production stages.

This script simulates the progression of orders through manufacturing stages
(assembly, test, inspection, shipping) based on elapsed time. Each stage has
a random duration of 3-72 hours.
"""

import sys
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict

from schemas import SQLiteWrapper


# Database directory
DB_DIR = Path(__file__).parent / "databases"
CRM_DB = DB_DIR / "crm.db"
MES_DB = DB_DIR / "mes.db"
ERP_DB = DB_DIR / "erp.db"

# Manufacturing stages in order
MES_STAGES = ["assembly", "test", "inspection", "shipping"]

# Stage duration range (in hours)
MIN_STAGE_DURATION = 3
MAX_STAGE_DURATION = 72


def get_orders_in_process() -> List[Tuple]:
    """
    Get all orders currently in processing.

    Returns:
        List of tuples: (order_id, customer_name, widget_type, quantity, unit_price)
    """
    db = SQLiteWrapper(str(CRM_DB))
    db.execute(
        """
        SELECT order_id, customer_name, widget_type, quantity, unit_price
        FROM orders
        WHERE status = 'order_processing'
        ORDER BY order_id
        """
    )
    orders = db.fetchall()
    db.close()
    return orders


def get_mes_tracking(order_id: int) -> Dict[str, Dict]:
    """
    Get MES tracking information for an order.

    Args:
        order_id: The order ID

    Returns:
        Dict mapping stage to {tracking_id, start_datetime, completion_datetime}
    """
    db = SQLiteWrapper(str(MES_DB))
    db.execute(
        """
        SELECT tracking_id, stage, start_datetime, completion_datetime
        FROM production_tracking
        WHERE order_id = ?
        ORDER BY tracking_id
        """,
        (order_id,)
    )
    rows = db.fetchall()
    db.close()

    tracking = {}
    for tracking_id, stage, start_dt, completion_dt in rows:
        tracking[stage] = {
            'tracking_id': tracking_id,
            'start_datetime': start_dt,
            'completion_datetime': completion_dt
        }

    return tracking


def update_stage_completion(tracking_id: int, completion_datetime: str):
    """
    Mark a stage as completed.

    Args:
        tracking_id: The tracking ID
        completion_datetime: Completion date/time
    """
    db = SQLiteWrapper(str(MES_DB))
    db.execute(
        """
        UPDATE production_tracking
        SET completion_datetime = ?
        WHERE tracking_id = ?
        """,
        (completion_datetime, tracking_id)
    )
    db.commit()
    db.close()


def update_stage_start(tracking_id: int, start_datetime: str):
    """
    Mark a stage as started.

    Args:
        tracking_id: The tracking ID
        start_datetime: Start date/time
    """
    db = SQLiteWrapper(str(MES_DB))
    db.execute(
        """
        UPDATE production_tracking
        SET start_datetime = ?
        WHERE tracking_id = ?
        """,
        (start_datetime, tracking_id)
    )
    db.commit()
    db.close()


def complete_order(order_id: int, ship_date: str):
    """
    Mark an order as shipped in CRM.

    Args:
        order_id: The order ID
        ship_date: Ship date (YYYY-MM-DD format)
    """
    db = SQLiteWrapper(str(CRM_DB))
    db.execute(
        """
        UPDATE orders
        SET status = 'order_shipped',
            date_shipped = ?
        WHERE order_id = ?
        """,
        (ship_date, order_id)
    )
    db.commit()
    db.close()


def record_payment(order_id: int, customer_name: str, amount: float, date: str):
    """
    Record customer payment in ERP.

    Args:
        order_id: The order ID
        customer_name: Customer name
        amount: Payment amount
        date: Payment date
    """
    db = SQLiteWrapper(str(ERP_DB))
    db.execute(
        """
        INSERT INTO financial_transactions (transaction_type, amount, date, description, related_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("customer_payment", amount, date,
         f"Payment from {customer_name} for Order #{order_id}", order_id)
    )
    db.commit()
    db.close()


def advance_order(order_id: int, customer_name: str, widget_type: str,
                 quantity: int, unit_price: float, current_time: datetime) -> Tuple[int, bool]:
    """
    Advance an order through manufacturing stages.

    Args:
        order_id: The order ID
        customer_name: Customer name
        widget_type: Widget type
        quantity: Order quantity
        unit_price: Unit price
        current_time: Current simulation time

    Returns:
        Tuple of (stages_advanced, order_completed)
    """
    tracking = get_mes_tracking(order_id)
    stages_advanced = 0
    order_completed = False

    # Process stages in order
    for i, stage in enumerate(MES_STAGES):
        stage_info = tracking[stage]
        start_dt = stage_info['start_datetime']
        completion_dt = stage_info['completion_datetime']

        # Skip if already completed
        if completion_dt is not None:
            continue

        # Skip if not yet started
        if start_dt is None:
            break

        # Parse start datetime
        start_time = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")

        # Generate random duration for this stage (3-72 hours)
        duration_hours = random.uniform(MIN_STAGE_DURATION, MAX_STAGE_DURATION)
        expected_completion = start_time + timedelta(hours=duration_hours)

        # Check if stage should be completed
        if expected_completion <= current_time:
            # Complete this stage
            completion_datetime_str = expected_completion.strftime("%Y-%m-%d %H:%M:%S")
            update_stage_completion(stage_info['tracking_id'], completion_datetime_str)

            print(f"    ✓ {stage.capitalize()}: completed at {completion_datetime_str} ({duration_hours:.1f} hours)")
            stages_advanced += 1

            # Start next stage if available
            if i < len(MES_STAGES) - 1:
                next_stage = MES_STAGES[i + 1]
                next_stage_info = tracking[next_stage]

                # Start next stage at current time
                current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
                update_stage_start(next_stage_info['tracking_id'], current_time_str)
                print(f"    → {next_stage.capitalize()}: started at {current_time_str}")
            else:
                # All stages complete - ship the order
                ship_date = current_time.strftime("%Y-%m-%d")
                complete_order(order_id, ship_date)

                # Record payment
                total_amount = quantity * unit_price
                record_payment(order_id, customer_name, total_amount, ship_date)

                print(f"    📦 Order shipped on {ship_date}")
                print(f"    💰 Payment received: ${total_amount:,.2f}")
                order_completed = True

        else:
            # Stage not yet complete
            time_remaining = expected_completion - current_time
            hours_remaining = time_remaining.total_seconds() / 3600
            print(f"    ⏳ {stage.capitalize()}: in progress ({hours_remaining:.1f} hours remaining)")
            break  # Don't check further stages

    return stages_advanced, order_completed


def run_manufacturing_ops(current_datetime: str):
    """
    Main function to advance all orders through manufacturing.

    Args:
        current_datetime: Current date/time (YYYY-MM-DD HH:MM:SS)
    """
    current_time = datetime.strptime(current_datetime, "%Y-%m-%d %H:%M:%S")

    # Get all orders in process
    orders = get_orders_in_process()

    if len(orders) == 0:
        print("\n✓ No orders currently in manufacturing.")
        return

    print(f"\nProcessing {len(orders)} order(s):\n")

    total_stages_advanced = 0
    total_orders_completed = 0

    for order_id, customer_name, widget_type, quantity, unit_price in orders:
        print(f"Order #{order_id}: {customer_name} | {widget_type} x{quantity}")

        stages_advanced, order_completed = advance_order(
            order_id, customer_name, widget_type, quantity, unit_price, current_time
        )

        total_stages_advanced += stages_advanced

        if order_completed:
            total_orders_completed += 1

        print()

    # Summary
    print("=" * 70)
    print(f"Manufacturing update complete:")
    print(f"  - {total_stages_advanced} stage(s) advanced")
    print(f"  - {total_orders_completed} order(s) shipped")
    print(f"  - {len(orders) - total_orders_completed} order(s) still in production")
    print("=" * 70)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Advance orders through manufacturing stages based on elapsed time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How it works:
  - Each stage (assembly, test, inspection, shipping) takes 3-72 hours (random)
  - If current_time >= stage_start + random_duration, stage completes
  - Next stage starts immediately at current_time
  - When shipping completes, order is marked shipped and payment is recorded

Examples:
  %(prog)s                                    # Use current date/time
  %(prog)s "2026-02-14 10:00:00"             # Specific date and time
  %(prog)s "2026-02-14"                       # Specific date (time defaults to 00:00:00)
        """
    )
    parser.add_argument(
        "datetime",
        nargs="?",
        default=None,
        help="Current date/time in ISO format (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD). If not provided, uses current time."
    )

    args = parser.parse_args()

    # Validate datetime format if provided
    current_datetime = None
    if args.datetime:
        try:
            # Try parsing as full datetime
            dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M:%S")
            current_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Try parsing as date only
                dt = datetime.strptime(args.datetime, "%Y-%m-%d")
                current_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                print(f"Error: Invalid datetime format: {args.datetime}", file=sys.stderr)
                print("Use YYYY-MM-DD HH:MM:SS or YYYY-MM-DD format", file=sys.stderr)
                sys.exit(1)
    else:
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 70)
    print("Manufacturing Operations Tool")
    print("=" * 70)
    print(f"Current time: {current_datetime}")

    try:
        run_manufacturing_ops(current_datetime)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
