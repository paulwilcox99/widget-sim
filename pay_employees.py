#!/usr/bin/env python3
"""
Employee Payroll Tool - Pay employees on Fridays.

This script checks if the provided date is a Friday and, if so, processes
weekly payroll by creating payment transactions in the ERP database for all employees.
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from schemas import SQLiteWrapper


# Database directory
DB_DIR = Path(__file__).parent / "databases"
ERP_DB = DB_DIR / "erp.db"


def is_friday(date: datetime) -> bool:
    """
    Check if a date is a Friday.

    Args:
        date: datetime object to check

    Returns:
        True if Friday, False otherwise
    """
    # weekday() returns 0=Monday, 1=Tuesday, ..., 4=Friday, 5=Saturday, 6=Sunday
    return date.weekday() == 4


def get_all_employees() -> List[Tuple]:
    """
    Get all employees from the ERP database.

    Returns:
        List of tuples: (employee_id, name, title, weekly_salary)
    """
    db = SQLiteWrapper(str(ERP_DB))
    db.execute(
        """
        SELECT employee_id, name, title, weekly_salary
        FROM employees
        ORDER BY employee_id
        """
    )
    employees = db.fetchall()
    db.close()
    return employees


def pay_employee(employee_id: int, name: str, title: str, weekly_salary: float, pay_date: str):
    """
    Create a payment transaction for an employee.

    Args:
        employee_id: Employee ID
        name: Employee name
        title: Employee title
        weekly_salary: Weekly salary amount
        pay_date: Payment date (YYYY-MM-DD format)
    """
    db = SQLiteWrapper(str(ERP_DB))
    db.execute(
        """
        INSERT INTO financial_transactions (transaction_type, amount, date, description, related_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("employee_payment", -weekly_salary, pay_date,
         f"Weekly salary for {name} ({title})", employee_id)
    )
    db.commit()
    db.close()


def process_payroll(pay_date_str: str):
    """
    Main payroll processing function.

    Args:
        pay_date_str: Payment date string (YYYY-MM-DD)
    """
    # Parse the date
    pay_date = datetime.strptime(pay_date_str, "%Y-%m-%d")
    day_name = pay_date.strftime("%A")

    print(f"\nPayroll date: {pay_date_str} ({day_name})")

    # Check if it's Friday
    if not is_friday(pay_date):
        print(f"\n⚠ {pay_date_str} is a {day_name}, not a Friday.")
        print("Payroll is only processed on Fridays. No payments made.")
        return

    print(f"✓ {pay_date_str} is a Friday - processing payroll...\n")

    # Get all employees
    employees = get_all_employees()

    if len(employees) == 0:
        print("⚠ No employees found in database.")
        return

    total_payroll = 0.0
    payment_count = 0

    # Pay each employee
    for employee_id, name, title, weekly_salary in employees:
        pay_employee(employee_id, name, title, weekly_salary, pay_date_str)
        total_payroll += weekly_salary
        payment_count += 1

        if payment_count <= 10:  # Show first 10 payments
            print(f"  ✓ {name} ({title}): ${weekly_salary:,.2f}")
        elif payment_count == 11:
            print(f"  ... ({len(employees) - 10} more employees)")

    print(f"\n{'=' * 70}")
    print(f"Payroll complete:")
    print(f"  - {payment_count} employee(s) paid")
    print(f"  - Total payroll: ${total_payroll:,.2f}")
    print(f"{'=' * 70}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Process weekly employee payroll on Fridays",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How it works:
  - Checks if the provided date is a Friday
  - If Friday, creates payment transactions for all employees
  - Payment amount is the weekly_salary from employees table
  - Records as negative amount (expense) in financial_transactions

Examples:
  %(prog)s                                    # Use current date
  %(prog)s "2026-02-14"                       # Specific date (Friday)
  %(prog)s "2026-02-15"                       # Specific date (Saturday - no payment)
        """
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Payroll date in ISO format (YYYY-MM-DD). If not provided, uses current date."
    )

    args = parser.parse_args()

    # Validate date format if provided
    pay_date = None
    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
            pay_date = dt.strftime("%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid date format: {args.date}", file=sys.stderr)
            print("Use YYYY-MM-DD format", file=sys.stderr)
            sys.exit(1)
    else:
        pay_date = datetime.now().strftime("%Y-%m-%d")

    print("=" * 70)
    print("Employee Payroll Tool")
    print("=" * 70)

    try:
        process_payroll(pay_date)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
