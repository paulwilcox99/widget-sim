#!/usr/bin/env python3
"""
Order Generation Tool - Create random orders in the CRM database.

This script generates a random order by selecting a customer from the customer pool,
choosing a widget type, quantity, and price, then inserting it into the CRM database.
"""

import sys
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from schemas import SQLiteWrapper


# Database directory
DB_DIR = Path(__file__).parent / "databases"
CUSTOMERS_DB = DB_DIR / "customers.db"
CRM_DB = DB_DIR / "crm.db"
INVENTORY_DB = DB_DIR / "inventory.db"

# Widget types
WIDGET_TYPES = ["Widget_Pro", "Widget", "Widget_Classic"]

# Target gross margin (30%)
TARGET_MARGIN = 0.30


def get_random_customer():
    """Select a random customer from the customers database."""
    db = SQLiteWrapper(str(CUSTOMERS_DB))

    # Get total count
    db.execute("SELECT COUNT(*) FROM customers")
    count = db.fetchone()[0]

    if count == 0:
        raise Exception("No customers in database!")

    # Select random customer
    random_id = random.randint(1, count)
    db.execute("SELECT name, street_address, city, state, zip_code, email, phone FROM customers WHERE id = ?", (random_id,))
    customer = db.fetchone()
    db.close()

    return customer


def calculate_predicted_ship_date(order_date):
    """Calculate predicted ship date (7-14 days from order)."""
    days_to_ship = random.randint(7, 14)
    order_dt = datetime.fromisoformat(order_date)
    ship_dt = order_dt + timedelta(days=days_to_ship)
    return ship_dt.strftime("%Y-%m-%d")


def get_widget_cost(widget_type):
    """
    Calculate the manufacturing cost for a widget based on its BoM.

    Args:
        widget_type: The type of widget

    Returns:
        Manufacturing cost per unit
    """
    db = SQLiteWrapper(str(INVENTORY_DB))
    db.execute(
        """
        SELECT SUM(quantity_needed * unit_cost)
        FROM bom
        WHERE widget_type = ?
        """,
        (widget_type,)
    )
    result = db.fetchone()
    db.close()

    cost = result[0] if result[0] else 100.0
    return cost


def calculate_sale_price(widget_type):
    """
    Calculate sale price to achieve target margin with some variance.

    Target margin is 30%, so if cost is $100, price should be ~$143
    (Revenue - Cost) / Revenue = 0.30
    Price = Cost / (1 - 0.30) = Cost / 0.70

    Add ±10% variance to simulate market conditions and negotiations.

    Args:
        widget_type: The type of widget

    Returns:
        Sale price per unit
    """
    cost = get_widget_cost(widget_type)

    # Calculate price for target margin
    base_price = cost / (1 - TARGET_MARGIN)

    # Add variance of ±10% to simulate market conditions
    variance = random.uniform(-0.10, 0.10)
    final_price = base_price * (1 + variance)

    return round(final_price, 2)


def create_order(order_datetime=None):
    """
    Create a random order and insert it into the CRM database.

    Args:
        order_datetime: ISO format datetime string (YYYY-MM-DD HH:MM:SS) or None for current time

    Returns:
        tuple: (order_id, order details dict)
    """
    # Use provided datetime or current time
    if order_datetime is None:
        order_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Get random customer
    customer = get_random_customer()
    customer_name = customer[0]

    # Generate random order details
    widget_type = random.choice(WIDGET_TYPES)
    quantity = random.randint(1, 20)
    unit_price = calculate_sale_price(widget_type)

    # Initial status is order_received
    status = "order_received"

    # Calculate predicted ship date
    predicted_ship_date = calculate_predicted_ship_date(order_datetime)

    # Insert into CRM database
    db = SQLiteWrapper(str(CRM_DB))
    db.execute(
        """
        INSERT INTO orders (customer_name, widget_type, quantity, unit_price,
                          date_ordered, status, date_shipped, predicted_ship_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (customer_name, widget_type, quantity, unit_price,
         order_datetime, status, None, predicted_ship_date)
    )

    # Get the order_id
    db.execute("SELECT last_insert_rowid()")
    order_id = db.fetchone()[0]

    db.commit()
    db.close()

    # Return order details
    order_details = {
        "order_id": order_id,
        "customer_name": customer_name,
        "customer_address": f"{customer[1]}, {customer[2]}, {customer[3]} {customer[4]}",
        "customer_email": customer[5],
        "customer_phone": customer[6],
        "widget_type": widget_type,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": quantity * unit_price,
        "date_ordered": order_datetime,
        "status": status,
        "predicted_ship_date": predicted_ship_date
    }

    return order_id, order_details


def main():
    """Main function to generate an order."""
    parser = argparse.ArgumentParser(
        description="Generate a random order in the CRM database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use current date/time
  %(prog)s "2026-02-12 09:30:00"             # Specific date and time
  %(prog)s "2026-02-12"                       # Specific date (time defaults to 00:00:00)
        """
    )
    parser.add_argument(
        "datetime",
        nargs="?",
        default=None,
        help="Order date/time in ISO format (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD). If not provided, uses current time."
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=1,
        help="Number of orders to generate (default: 1)"
    )

    args = parser.parse_args()

    # Validate datetime format if provided
    order_datetime = None
    if args.datetime:
        try:
            # Try parsing as full datetime
            dt = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M:%S")
            order_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Try parsing as date only
                dt = datetime.strptime(args.datetime, "%Y-%m-%d")
                order_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                print(f"Error: Invalid datetime format: {args.datetime}", file=sys.stderr)
                print("Use YYYY-MM-DD HH:MM:SS or YYYY-MM-DD format", file=sys.stderr)
                sys.exit(1)

    print("=" * 70)
    print("Order Generation Tool")
    print("=" * 70)

    # Generate orders
    for i in range(args.count):
        try:
            order_id, details = create_order(order_datetime)

            if args.count > 1:
                print(f"\n[Order {i+1}/{args.count}]")

            print(f"\n✓ Order #{order_id} created successfully!")
            print(f"\n  Customer: {details['customer_name']}")
            print(f"  Address:  {details['customer_address']}")
            print(f"  Email:    {details['customer_email']}")
            print(f"  Phone:    {details['customer_phone']}")
            print(f"\n  Product:  {details['widget_type']}")
            print(f"  Quantity: {details['quantity']} units")
            print(f"  Price:    ${details['unit_price']:.2f} per unit")
            print(f"  Total:    ${details['total_price']:.2f}")
            print(f"\n  Ordered:  {details['date_ordered']}")
            print(f"  Status:   {details['status']}")
            print(f"  Est. Ship: {details['predicted_ship_date']}")

            if i < args.count - 1:
                print("\n" + "-" * 70)

        except Exception as e:
            print(f"\n✗ Error creating order: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
