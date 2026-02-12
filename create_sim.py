#!/usr/bin/env python3
"""
Manufacturing Company Simulator - Database Creation Tool

This script creates and initializes all databases for the simulation at day 0.
Run this script to set up a fresh simulation environment.
"""

import os
import sys
from pathlib import Path

from schemas import (
    SQLiteWrapper,
    create_customers_db,
    create_crm_db,
    create_inventory_db,
    create_mes_db,
    create_erp_db
)
from data_generators import (
    generate_customers,
    generate_employees,
    generate_boms,
    calculate_initial_inventory
)


# Database directory
DB_DIR = Path(__file__).parent / "databases"

# Database paths
CUSTOMERS_DB = DB_DIR / "customers.db"
CRM_DB = DB_DIR / "crm.db"
INVENTORY_DB = DB_DIR / "inventory.db"
MES_DB = DB_DIR / "mes.db"
ERP_DB = DB_DIR / "erp.db"


def create_databases_directory():
    """Create the databases directory if it doesn't exist."""
    DB_DIR.mkdir(exist_ok=True)
    print(f"✓ Created databases directory: {DB_DIR}")


def initialize_customers_database():
    """Create and populate the customers database."""
    print("\n[1/5] Initializing Customers Database...")

    # Remove existing database
    if CUSTOMERS_DB.exists():
        CUSTOMERS_DB.unlink()

    # Create schema
    create_customers_db(str(CUSTOMERS_DB))

    # Generate and insert customers
    customers = generate_customers(count=1000)
    db = SQLiteWrapper(str(CUSTOMERS_DB))
    db.executemany(
        "INSERT INTO customers (name, street_address, city, state, zip_code, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
        customers
    )
    db.commit()
    db.close()

    print(f"✓ Created {len(customers)} customers in {CUSTOMERS_DB.name}")


def initialize_crm_database():
    """Create the CRM database (empty, ready for orders)."""
    print("\n[2/5] Initializing CRM Database...")

    # Remove existing database
    if CRM_DB.exists():
        CRM_DB.unlink()

    # Create schema
    create_crm_db(str(CRM_DB))

    print(f"✓ Created CRM database at {CRM_DB.name} (ready for orders)")


def initialize_inventory_database():
    """Create and populate the inventory database with BoMs and initial stock."""
    print("\n[3/5] Initializing Inventory Database...")

    # Remove existing database
    if INVENTORY_DB.exists():
        INVENTORY_DB.unlink()

    # Create schema
    create_inventory_db(str(INVENTORY_DB))

    # Generate BoMs
    boms, widget_prices = generate_boms()
    print(f"  - Generated BoMs for 3 widget types:")
    widget_type_counts = {}
    for widget_type, _, _, _ in boms:
        widget_type_counts[widget_type] = widget_type_counts.get(widget_type, 0) + 1

    for widget_type in ["Widget_Pro", "Widget", "Widget_Classic"]:
        print(f"    • {widget_type}: {widget_type_counts[widget_type]} parts, ${widget_prices[widget_type]:.2f} retail price")

    # Insert BoMs
    db = SQLiteWrapper(str(INVENTORY_DB))
    db.executemany(
        "INSERT INTO bom (widget_type, part_name, quantity_needed, unit_cost) VALUES (?, ?, ?, ?)",
        boms
    )

    # Calculate and insert initial inventory
    inventory = calculate_initial_inventory(boms)
    db.executemany(
        "INSERT INTO inventory_levels (part_name, quantity_available) VALUES (?, ?)",
        inventory
    )

    db.commit()
    db.close()

    print(f"✓ Created {len(boms)} BoM entries and stocked {len(inventory)} unique parts")
    print(f"  - Initial inventory sufficient for 100 units of each widget type")

    # Save widget prices to a reference file
    prices_file = DB_DIR / "widget_prices.txt"
    with open(prices_file, 'w') as f:
        f.write("Widget Retail Prices\n")
        f.write("===================\n")
        for widget_type in ["Widget_Pro", "Widget", "Widget_Classic"]:
            f.write(f"{widget_type}: ${widget_prices[widget_type]:.2f}\n")
    print(f"✓ Saved widget prices to {prices_file.name}")


def initialize_mes_database():
    """Create the MES database (empty, ready for production tracking)."""
    print("\n[4/5] Initializing MES Database...")

    # Remove existing database
    if MES_DB.exists():
        MES_DB.unlink()

    # Create schema
    create_mes_db(str(MES_DB))

    print(f"✓ Created MES database at {MES_DB.name} (ready for production tracking)")


def initialize_erp_database():
    """Create and populate the ERP database with employees."""
    print("\n[5/5] Initializing ERP Database...")

    # Remove existing database
    if ERP_DB.exists():
        ERP_DB.unlink()

    # Create schema
    create_erp_db(str(ERP_DB))

    # Generate and insert employees
    employees = generate_employees(count=200)
    db = SQLiteWrapper(str(ERP_DB))
    db.executemany(
        "INSERT INTO employees (name, title, weekly_salary) VALUES (?, ?, ?)",
        employees
    )
    db.commit()

    # Calculate total weekly payroll
    db.execute("SELECT SUM(weekly_salary) FROM employees")
    total_payroll = db.fetchone()[0]

    db.close()

    print(f"✓ Created {len(employees)} employees in {ERP_DB.name}")
    print(f"  - Total weekly payroll: ${total_payroll:,.2f}")


def main():
    """Main function to create all databases."""
    print("=" * 60)
    print("Manufacturing Company Simulator - Database Initialization")
    print("=" * 60)

    try:
        create_databases_directory()
        initialize_customers_database()
        initialize_crm_database()
        initialize_inventory_database()
        initialize_mes_database()
        initialize_erp_database()

        print("\n" + "=" * 60)
        print("✓ All databases created successfully!")
        print("=" * 60)
        print(f"\nDatabase files located in: {DB_DIR.absolute()}")
        print("\nNext steps:")
        print("  - Run simulation tools to process orders")
        print("  - Use query tools to inspect database contents")

    except Exception as e:
        print(f"\n✗ Error during database creation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
