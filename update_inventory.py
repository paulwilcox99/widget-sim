#!/usr/bin/env python3
"""
Inventory Restocking Tool - Automatically restock low inventory levels.

This script scans inventory levels and orders more parts when levels fall below
the threshold needed to build 10 units of each widget type. When restocking,
it orders enough to build 100 units of each widget type.
"""

import sys
import argparse
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from schemas import SQLiteWrapper


# Database directory
DB_DIR = Path(__file__).parent / "databases"
INVENTORY_DB = DB_DIR / "inventory.db"
ERP_DB = DB_DIR / "erp.db"

# Thresholds
LOW_INVENTORY_THRESHOLD = 10  # Parts needed to build 10 of each widget
RESTOCK_TARGET = 100          # Parts needed to build 100 of each widget


def get_all_parts_with_requirements() -> Dict[str, Dict]:
    """
    Get all parts with their current inventory and BoM requirements.

    Returns:
        Dict mapping part_name to {
            'current_qty': int,
            'bom_entries': [(widget_type, qty_needed, unit_cost), ...],
            'threshold': int,  # qty needed for 10 of each widget
            'target': int      # qty needed for 100 of each widget
        }
    """
    db = SQLiteWrapper(str(INVENTORY_DB))

    # Get all parts from inventory
    db.execute("SELECT part_name, quantity_available FROM inventory_levels ORDER BY part_name")
    inventory = {row[0]: row[1] for row in db.fetchall()}

    # Get all BoM entries
    db.execute("SELECT part_name, widget_type, quantity_needed, unit_cost FROM bom ORDER BY part_name")
    bom_entries = db.fetchall()

    db.close()

    # Build parts dictionary
    parts = {}
    for part_name in inventory:
        parts[part_name] = {
            'current_qty': inventory[part_name],
            'bom_entries': [],
            'threshold': 0,
            'target': 0
        }

    # Add BoM information
    for part_name, widget_type, qty_needed, unit_cost in bom_entries:
        if part_name in parts:
            parts[part_name]['bom_entries'].append((widget_type, qty_needed, unit_cost))
            parts[part_name]['threshold'] += qty_needed * LOW_INVENTORY_THRESHOLD
            parts[part_name]['target'] += qty_needed * RESTOCK_TARGET

    return parts


def identify_low_inventory_parts(parts: Dict[str, Dict]) -> List[str]:
    """
    Identify parts that are below the low inventory threshold.

    Args:
        parts: Dictionary of parts with their requirements

    Returns:
        List of part names that need restocking
    """
    low_parts = []
    for part_name, info in parts.items():
        if info['current_qty'] < info['threshold']:
            low_parts.append(part_name)

    return low_parts


def calculate_restock_amount(part_info: Dict) -> Tuple[int, float]:
    """
    Calculate how much to order and the cost.

    Args:
        part_info: Part information dictionary

    Returns:
        Tuple of (quantity_to_order, total_cost)
    """
    current_qty = part_info['current_qty']
    target_qty = part_info['target']

    # Order enough to reach target
    qty_to_order = target_qty - current_qty

    if qty_to_order <= 0:
        return 0, 0.0

    # Calculate cost with ±10% variance
    # Use weighted average of unit costs from all BoMs
    total_cost = 0.0
    total_weight = 0

    for widget_type, qty_needed, unit_cost in part_info['bom_entries']:
        # Apply random variance of ±10%
        variance = random.uniform(-0.10, 0.10)
        purchase_price = unit_cost * (1 + variance)

        # Weight by quantity needed in BoM
        weight = qty_needed
        total_cost += purchase_price * weight
        total_weight += weight

    # Calculate average purchase price
    avg_purchase_price = total_cost / total_weight if total_weight > 0 else 0.0

    # Total cost for the order
    total_order_cost = avg_purchase_price * qty_to_order

    return qty_to_order, total_order_cost


def restock_inventory(restock_date: str) -> Tuple[int, float]:
    """
    Main restocking function - check inventory and restock low parts.

    Args:
        restock_date: Date of restocking (YYYY-MM-DD format)

    Returns:
        Tuple of (parts_restocked_count, total_cost)
    """
    # Get all parts with requirements
    parts = get_all_parts_with_requirements()

    # Identify low inventory parts
    low_parts = identify_low_inventory_parts(parts)

    if len(low_parts) == 0:
        print("\n✓ All parts have sufficient inventory.")
        return 0, 0.0

    print(f"\nFound {len(low_parts)} part(s) below threshold:\n")

    inventory_db = SQLiteWrapper(str(INVENTORY_DB))
    erp_db = SQLiteWrapper(str(ERP_DB))

    total_cost = 0.0
    parts_restocked = 0

    for part_name in sorted(low_parts):
        part_info = parts[part_name]
        current_qty = part_info['current_qty']
        threshold = part_info['threshold']
        target = part_info['target']

        # Calculate restock amount
        qty_to_order, order_cost = calculate_restock_amount(part_info)

        if qty_to_order <= 0:
            continue

        print(f"{part_name}:")
        print(f"  Current: {current_qty} units (threshold: {threshold})")
        print(f"  Ordering: {qty_to_order} units to reach target of {target}")
        print(f"  Cost: ${order_cost:,.2f}")

        # Update inventory
        new_qty = current_qty + qty_to_order
        inventory_db.execute(
            "UPDATE inventory_levels SET quantity_available = ? WHERE part_name = ?",
            (new_qty, part_name)
        )

        # Record financial transaction
        erp_db.execute(
            """
            INSERT INTO financial_transactions (transaction_type, amount, date, description, related_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("inventory_purchase", order_cost, restock_date,
             f"Restocked {part_name}: {qty_to_order} units", None)
        )

        total_cost += order_cost
        parts_restocked += 1
        print()

    # Commit changes
    inventory_db.commit()
    erp_db.commit()

    inventory_db.close()
    erp_db.close()

    return parts_restocked, total_cost


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Monitor and restock inventory when levels are low",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How it works:
  - Checks if parts are below threshold (enough to build 10 of each widget type)
  - If low, orders enough to build 100 of each widget type
  - Purchase price is BoM cost ±10% random variance
  - Records financial transactions in ERP database

Examples:
  %(prog)s                                    # Use current date
  %(prog)s "2026-02-12"                       # Specific date
        """
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Restocking date in ISO format (YYYY-MM-DD). If not provided, uses current date."
    )

    args = parser.parse_args()

    # Validate date format if provided
    restock_date = None
    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
            restock_date = dt.strftime("%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format: {args.date}", file=sys.stderr)
            print("Use YYYY-MM-DD format", file=sys.stderr)
            sys.exit(1)
    else:
        restock_date = datetime.now().strftime("%Y-%m-%d")

    print("=" * 70)
    print("Inventory Restocking Tool")
    print("=" * 70)
    print(f"Date: {restock_date}")
    print(f"Threshold: Parts to build {LOW_INVENTORY_THRESHOLD} of each widget type")
    print(f"Restock target: Parts to build {RESTOCK_TARGET} of each widget type")

    try:
        parts_restocked, total_cost = restock_inventory(restock_date)

        if parts_restocked > 0:
            print("=" * 70)
            print(f"✓ Restocking complete:")
            print(f"  - {parts_restocked} part(s) restocked")
            print(f"  - Total cost: ${total_cost:,.2f}")
            print("=" * 70)

    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
