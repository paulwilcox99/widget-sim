"""
Database schema definitions for the manufacturing company simulator.
Designed for SQLite but with future migration to other databases in mind.
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import List, Tuple


class DatabaseWrapper(ABC):
    """Abstract base class for database operations to enable future migrations."""

    @abstractmethod
    def execute(self, query: str, params: tuple = ()):
        pass

    @abstractmethod
    def executemany(self, query: str, params: List[tuple]):
        pass

    @abstractmethod
    def commit(self):
        pass

    @abstractmethod
    def close(self):
        pass


class SQLiteWrapper(DatabaseWrapper):
    """SQLite implementation of database wrapper."""

    def __init__(self, db_path: str):
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()

    def execute(self, query: str, params: tuple = ()):
        return self.cursor.execute(query, params)

    def executemany(self, query: str, params: List[tuple]):
        return self.cursor.executemany(query, params)

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()


# Schema definitions
CUSTOMERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    street_address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL
);
"""

CRM_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    widget_type TEXT NOT NULL CHECK(widget_type IN ('Widget_Pro', 'Widget', 'Widget_Classic')),
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    date_ordered TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('order_received', 'order_processing', 'order_shipped')),
    date_shipped TEXT,
    predicted_ship_date TEXT
);
"""

INVENTORY_BOM_SCHEMA = """
CREATE TABLE IF NOT EXISTS bom (
    bom_id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_type TEXT NOT NULL CHECK(widget_type IN ('Widget_Pro', 'Widget', 'Widget_Classic')),
    part_name TEXT NOT NULL,
    quantity_needed INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    UNIQUE(widget_type, part_name)
);
"""

INVENTORY_LEVELS_SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory_levels (
    part_name TEXT PRIMARY KEY,
    quantity_available INTEGER NOT NULL
);
"""

MES_SCHEMA = """
CREATE TABLE IF NOT EXISTS production_tracking (
    tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN ('assembly', 'test', 'inspection', 'shipping')),
    start_datetime TEXT,
    completion_datetime TEXT
);
"""

ERP_EMPLOYEES_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    weekly_salary REAL NOT NULL
);
"""

ERP_FINANCIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS financial_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('inventory_purchase', 'employee_payment', 'customer_payment')),
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    description TEXT,
    related_id INTEGER
);
"""


def create_customers_db(db_path: str):
    """Create the customers database."""
    db = SQLiteWrapper(db_path)
    db.execute(CUSTOMERS_SCHEMA)
    db.commit()
    db.close()


def create_crm_db(db_path: str):
    """Create the CRM database."""
    db = SQLiteWrapper(db_path)
    db.execute(CRM_SCHEMA)
    db.commit()
    db.close()


def create_inventory_db(db_path: str):
    """Create the inventory database."""
    db = SQLiteWrapper(db_path)
    db.execute(INVENTORY_BOM_SCHEMA)
    db.execute(INVENTORY_LEVELS_SCHEMA)
    db.commit()
    db.close()


def create_mes_db(db_path: str):
    """Create the MES database."""
    db = SQLiteWrapper(db_path)
    db.execute(MES_SCHEMA)
    db.commit()
    db.close()


def create_erp_db(db_path: str):
    """Create the ERP database."""
    db = SQLiteWrapper(db_path)
    db.execute(ERP_EMPLOYEES_SCHEMA)
    db.execute(ERP_FINANCIAL_SCHEMA)
    db.commit()
    db.close()
