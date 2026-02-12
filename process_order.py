#!/usr/bin/env python3
"""
Order Processing Tool - Process new orders and update inventory, CRM, and MES databases.

This script finds all orders with status "order_received", checks inventory availability,
deducts the required parts, updates the order status to "order_processing", and creates
MES tracking entries for the manufacturing stages.
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict

from schemas import SQLiteWrapper


# Database directory
DB_DIR = Path(__file__).parent / "databases"
CRM_DB = DB_DIR / "crm.db"
INVENTORY_DB = DB_DIR / "inventory.db"
MES_DB = DB_DIR / "mes.db"
ERP_DB = DB_DIR / "erp.db"

# Manufacturing stages
MES_STAGES = ["assembly", "test", "inspection", "shipping"]


def get_unprocessed_orders() -> List[Tuple]:
    """
    Get all orders with status 'order_received'.

    Returns:
        List of tuples: (order_id, customer_name, widget_type, quantity, date_ordered)
    """
    db = SQLiteWrapper(str(CRM_DB))
    db.execute(
        """
        SELECT order_id, customer_name, widget_type, quantity, date_ordered
        FROM orders
        WHERE status = 'order_received'
        ORDER BY order_id
        """
    )
    orders = db.fetchall()
    db.close()
    return orders


def get_bom_for_widget(widget_type: str) -> List[Tuple]:
    """
    Get the Bill of Materials for a widget type.

    Args:
        widget_type: The type of widget (Widget_Pro, Widget, Widget_Classic)

    Returns:
        List of tuples: (part_name, quantity_needed, unit_cost)
    """
    db = SQLiteWrapper(str(INVENTORY_DB))
    db.execute(
        """
        SELECT part_name, quantity_needed, unit_cost
        FROM bom
        WHERE widget_type = ?
        ORDER BY part_name
        """,
        (widget_type,)
    )
    bom = db.fetchall()
    db.close()
    return bom


def check_inventory_availability(widget_type: str, quantity: int) -> Tuple[bool, List[str]]:
    """
    Check if there's enough inventory to build the requested quantity of widgets.

    Args:
        widget_type: The type of widget
        quantity: Number of widgets to build

    Returns:
        Tuple of (availability_flag, list_of_missing_parts)
    """
    bom = get_bom_for_widget(widget_type)
    db = SQLiteWrapper(str(INVENTORY_DB))

    missing_parts = []

    for part_name, qty_needed_per_widget, unit_cost in bom:
        total_needed = qty_needed_per_widget * quantity

        db.execute(
            "SELECT quantity_available FROM inventory_levels WHERE part_name = ?",
            (part_name,)
        )
        result = db.fetchone()

        if result is None:
            missing_parts.append(f"{part_name} (not in inventory)")
        else:
            available = result[0]
            if available < total_needed:
                missing_parts.append(f"{part_name} (need {total_needed}, have {available})")

    db.close()

    return (len(missing_parts) == 0, missing_parts)


def deduct_inventory(widget_type: str, quantity: int, order_id: int, process_date: str) -> float:
    """
    Deduct inventory for an order and record the financial transaction.

    Args:
        widget_type: The type of widget
        quantity: Number of widgets to build
        order_id: The order ID for reference
        process_date: Date of processing

    Returns:
        Total cost of inventory used
    """
    bom = get_bom_for_widget(widget_type)
    inventory_db = SQLiteWrapper(str(INVENTORY_DB))
    erp_db = SQLiteWrapper(str(ERP_DB))

    total_cost = 0.0

    for part_name, qty_needed_per_widget, unit_cost in bom:
        total_needed = qty_needed_per_widget * quantity
        part_cost = total_needed * unit_cost
        total_cost += part_cost

        # Deduct from inventory
        inventory_db.execute(
            """
            UPDATE inventory_levels
            SET quantity_available = quantity_available - ?
            WHERE part_name = ?
            """,
            (total_needed, part_name)
        )

    inventory_db.commit()
    inventory_db.close()

    # Record financial transaction for inventory usage
    erp_db.execute(
        """
        INSERT INTO financial_transactions (transaction_type, amount, date, description, related_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("inventory_purchase", -total_cost, process_date.split()[0],
         f"Inventory used for Order #{order_id} ({quantity}x {widget_type})", order_id)
    )
    erp_db.commit()
    erp_db.close()

    return total_cost


def update_order_status(order_id: int):
    """
    Update order status from 'order_received' to 'order_processing'.

    Args:
        order_id: The order ID to update
    """
    db = SQLiteWrapper(str(CRM_DB))
    db.execute(
        """
        UPDATE orders
        SET status = 'order_processing'
        WHERE order_id = ?
        """,
        (order_id,)
    )
    db.commit()
    db.close()


def create_mes_entries(order_id: int, start_date: str):
    """
    Create MES tracking entries for all manufacturing stages.
    The assembly stage is marked as started with the provided date.

    Args:
        order_id: The order ID to track
        start_date: Date when processing starts (for assembly stage)
    """
    db = SQLiteWrapper(str(MES_DB))

    for stage in MES_STAGES:
        if stage == "assembly":
            # Assembly starts immediately
            db.execute(
                """
                INSERT INTO production_tracking (order_id, stage, start_datetime, completion_datetime)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, stage, start_date, None)
            )
        else:
            # Other stages not yet started
            db.execute(
                """
                INSERT INTO production_tracking (order_id, stage, start_datetime, completion_datetime)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, stage, None, None)
            )

    db.commit()
    db.close()


def process_orders(process_datetime: str):
    """
    Main processing function - process all unprocessed orders.

    Args:
        process_datetime: Date/time when processing occurs
    """
    # Get unprocessed orders
    orders = get_unprocessed_orders()

    if len(orders) == 0:
        print("\n✓ No unprocessed orders found.")
        return

    print(f"\nFound {len(orders)} unprocessed order(s):\n")

    processed_count = 0
    skipped_count = 0

    for order_id, customer_name, widget_type, quantity, date_ordered in orders:
        print(f"Order #{order_id}: {customer_name} | {widget_type} x{quantity}")

        # Check inventory availability
        available, missing_parts = check_inventory_availability(widget_type, quantity)

        if not available:
            print(f"  ✗ INSUFFICIENT INVENTORY - Cannot process")
            for missing in missing_parts:
                print(f"    - {missing}")
            skipped_count += 1
            print()
            continue

        # Process the order
        try:
            # Deduct inventory
            inventory_cost = deduct_inventory(widget_type, quantity, order_id, process_datetime)

            # Update CRM status
            update_order_status(order_id)

            # Create MES entries
            create_mes_entries(order_id, process_datetime)

            print(f"  ✓ Processed successfully")
            print(f"    - Inventory deducted (cost: ${inventory_cost:.2f})")
            print(f"    - Status updated to: order_processing")
            print(f"    - MES tracking started at: {process_datetime}")
            processed_count += 1

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            skipped_count += 1

        print()

    # Summary
    print("=" * 70)
    print(f"Processing complete:")
    print(f"  - {processed_count} order(s) processed")
    print(f"  - {skipped_count} order(s) skipped (insufficient inventory or errors)")
    print("=" * 70)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Process new orders and update inventory, CRM, and MES databases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use current date/time
  %(prog)s "2026-02-12 10:00:00"             # Specific date and time
  %(prog)s "2026-02-12"                       # Specific date (time defaults to 00:00:00)
        """
    )
    parser.add_argument(
        "datetime",
        nargs="?",
        default=None,
        help="Processing date/time in ISO format (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD). If not provided, uses current time."
    )

    args = parser.parse_args()

    # Validate datetime format if provided
    process_datetime = None
    if args.datetime:
        try:
            # Try parsing as full datetime
            dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M:%S")
            process_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Try parsing as date only
                dt = datetime.strptime(args.datetime, "%Y-%m-%d")
                process_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                print(f"Error: Invalid datetime format: {args.datetime}", file=sys.stderr)
                print("Use YYYY-MM-DD HH:MM:SS or YYYY-MM-DD format", file=sys.stderr)
                sys.exit(1)
    else:
        process_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 70)
    print("Order Processing Tool")
    print("=" * 70)
    print(f"Processing date/time: {process_datetime}")

    try:
        process_orders(process_datetime)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
