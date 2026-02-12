#!/usr/bin/env python3
"""
Database Dump Tool - Export all database contents to readable text files.

This script exports all tables from each database into markdown-formatted text files
for easy review.
"""

import sqlite3
from pathlib import Path
from datetime import datetime


# Database directory
DB_DIR = Path(__file__).parent / "databases"
OUTPUT_DIR = Path(__file__).parent / "database_dumps"

# Database paths
DATABASES = {
    "customers": DB_DIR / "customers.db",
    "crm": DB_DIR / "crm.db",
    "inventory": DB_DIR / "inventory.db",
    "mes": DB_DIR / "mes.db",
    "erp": DB_DIR / "erp.db"
}


def get_table_names(conn):
    """Get all table names from a SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def get_table_info(conn, table_name):
    """Get column information for a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def format_table_as_markdown(conn, table_name):
    """Format a table's contents as markdown."""
    cursor = conn.cursor()

    # Get column info
    columns = get_table_info(conn, table_name)
    column_names = [col[1] for col in columns]

    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cursor.fetchone()[0]

    # Get all data
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    # Build markdown output
    output = []
    output.append(f"## Table: `{table_name}`")
    output.append(f"\n**Row Count:** {row_count}\n")

    if row_count == 0:
        output.append("*No data in this table*\n")
        return "\n".join(output)

    # Create markdown table header
    output.append("| " + " | ".join(column_names) + " |")
    output.append("| " + " | ".join(["---"] * len(column_names)) + " |")

    # Add data rows
    for row in rows:
        formatted_row = []
        for value in row:
            if value is None:
                formatted_row.append("*NULL*")
            elif isinstance(value, float):
                formatted_row.append(f"{value:.2f}")
            else:
                formatted_row.append(str(value))
        output.append("| " + " | ".join(formatted_row) + " |")

    output.append("")  # Empty line after table
    return "\n".join(output)


def dump_database(db_name, db_path, output_file):
    """Dump entire database to a markdown file."""
    if not db_path.exists():
        print(f"⚠ Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))

    # Get all tables
    tables = get_table_names(conn)

    # Build output
    output = []
    output.append(f"# Database Dump: {db_name}.db")
    output.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"**Location:** {db_path}")
    output.append(f"**Tables:** {len(tables)}\n")
    output.append("---\n")

    # Dump each table
    for table in tables:
        output.append(format_table_as_markdown(conn, table))
        output.append("---\n")

    conn.close()

    # Write to file
    with open(output_file, 'w') as f:
        f.write("\n".join(output))

    print(f"✓ Dumped {db_name}.db → {output_file.name} ({len(tables)} tables)")


def generate_summary():
    """Generate a summary file with statistics from all databases."""
    summary = []
    summary.append("# Database Summary")
    summary.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    summary.append("---\n")

    for db_name, db_path in DATABASES.items():
        if not db_path.exists():
            continue

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        tables = get_table_names(conn)

        summary.append(f"## {db_name}.db\n")

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            summary.append(f"- **{table}**: {count:,} rows")

        summary.append("")
        conn.close()

    return "\n".join(summary)


def main():
    """Main function to dump all databases."""
    print("=" * 60)
    print("Database Dump Tool - Exporting to Markdown Files")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"\n✓ Output directory: {OUTPUT_DIR}\n")

    # Dump each database
    for db_name, db_path in DATABASES.items():
        output_file = OUTPUT_DIR / f"{db_name}_dump.md"
        dump_database(db_name, db_path, output_file)

    # Generate summary
    summary_file = OUTPUT_DIR / "summary.md"
    summary_content = generate_summary()
    with open(summary_file, 'w') as f:
        f.write(summary_content)
    print(f"✓ Generated summary → {summary_file.name}")

    print("\n" + "=" * 60)
    print("✓ All databases dumped successfully!")
    print("=" * 60)
    print(f"\nOutput files in: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
