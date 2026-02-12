"""
Data generation functions for the manufacturing company simulator.
Uses Faker to generate realistic customer and employee data.
"""

import random
from faker import Faker
from typing import List, Tuple, Dict, Set


fake = Faker()
Faker.seed(42)  # For reproducibility
random.seed(42)


def generate_customers(count: int = 1000) -> List[Tuple]:
    """
    Generate fake customer data.

    Returns list of tuples: (name, street_address, city, state, zip_code, email, phone)
    """
    customers = []
    for _ in range(count):
        customers.append((
            fake.name(),
            fake.street_address(),
            fake.city(),
            fake.state_abbr(),
            fake.zipcode(),
            fake.email(),
            fake.phone_number()
        ))
    return customers


# Job titles for manufacturing company
JOB_TITLES = [
    "Assembly Worker",
    "Test Engineer",
    "Quality Inspector",
    "Shipping Clerk",
    "Inventory Manager",
    "Production Supervisor",
    "Accountant",
    "Sales Representative",
    "Purchasing Agent",
    "Maintenance Technician",
    "Production Planner",
    "Warehouse Manager",
    "Quality Assurance Manager",
    "Manufacturing Engineer",
    "Supply Chain Coordinator",
    "HR Manager",
    "IT Support Specialist",
    "Operations Manager",
    "CEO",
    "CFO"
]


def generate_employees(count: int = 200) -> List[Tuple]:
    """
    Generate fake employee data.

    Returns list of tuples: (name, title, weekly_salary)
    Weekly salary ranges from ~$577/week ($30k/year) to ~$2,885/week ($150k/year)
    """
    employees = []
    for _ in range(count):
        title = random.choice(JOB_TITLES)

        # Salary ranges based on title (annual, then converted to weekly)
        if title in ["CEO", "CFO"]:
            annual_salary = random.uniform(120000, 150000)
        elif title in ["Operations Manager", "Quality Assurance Manager", "Warehouse Manager"]:
            annual_salary = random.uniform(70000, 100000)
        elif title in ["Manufacturing Engineer", "Production Supervisor", "IT Support Specialist", "HR Manager"]:
            annual_salary = random.uniform(55000, 75000)
        elif title in ["Test Engineer", "Accountant", "Production Planner"]:
            annual_salary = random.uniform(50000, 70000)
        else:
            annual_salary = random.uniform(30000, 55000)

        weekly_salary = round(annual_salary / 52, 2)

        employees.append((
            fake.name(),
            title,
            weekly_salary
        ))

    return employees


# Part categories and their naming patterns
PART_CATEGORIES = {
    "Screw": 20,
    "Bolt": 15,
    "Nut": 15,
    "Washer": 10,
    "Circuit-Board": 8,
    "Panel": 12,
    "Cable": 10,
    "Connector": 15,
    "Housing": 6,
    "Display": 5,
    "Button": 8,
    "Switch": 8,
    "Motor": 5,
    "Sensor": 10,
    "Battery": 4,
    "LED": 12,
    "Capacitor": 20,
    "Resistor": 20,
    "Chip": 10,
    "Frame": 5
}


def generate_part_name() -> str:
    """Generate a random part name like 'Screw-3' or 'Circuit-Board-5'."""
    category = random.choice(list(PART_CATEGORIES.keys()))
    number = random.randint(1, PART_CATEGORIES[category])
    return f"{category}-{number}"


def generate_boms() -> Tuple[List[Tuple], Dict[str, float]]:
    """
    Generate Bills of Materials for three widget types.

    Returns:
        - List of tuples: (widget_type, part_name, quantity_needed, unit_cost)
        - Dict of widget prices: {widget_type: unit_price}
    """
    widget_types = ["Widget_Pro", "Widget", "Widget_Classic"]
    boms = []
    all_parts: Set[str] = set()

    # Generate parts for each widget with some overlap
    widget_parts = {}

    for widget_type in widget_types:
        num_parts = random.randint(5, 25)
        parts = set()

        # Add unique parts
        while len(parts) < num_parts:
            parts.add(generate_part_name())

        widget_parts[widget_type] = parts
        all_parts.update(parts)

    # Create 30% overlap between widgets by sharing some parts
    common_parts = random.sample(list(all_parts), k=max(3, int(len(all_parts) * 0.15)))

    for widget_type in widget_types:
        # Add some common parts
        parts_to_add = random.sample(common_parts, k=random.randint(2, min(5, len(common_parts))))
        widget_parts[widget_type].update(parts_to_add)

    # Generate BOM entries with quantities and costs
    widget_costs = {}

    for widget_type in widget_types:
        total_cost = 0
        for part_name in widget_parts[widget_type]:
            quantity_needed = random.randint(1, 20)
            unit_cost = round(random.uniform(0.25, 25.00), 2)
            boms.append((widget_type, part_name, quantity_needed, unit_cost))
            total_cost += quantity_needed * unit_cost

        # Set retail price with markup (1.8x to 2.5x cost)
        markup = random.uniform(1.8, 2.5)
        widget_costs[widget_type] = round(total_cost * markup, 2)

    return boms, widget_costs


def calculate_initial_inventory(boms: List[Tuple]) -> List[Tuple]:
    """
    Calculate initial inventory levels to support building 100 units of each widget.

    Args:
        boms: List of (widget_type, part_name, quantity_needed, unit_cost)

    Returns:
        List of tuples: (part_name, quantity_available)
    """
    # Calculate max quantity needed for each part across all widgets
    part_requirements: Dict[str, int] = {}

    for widget_type, part_name, quantity_needed, unit_cost in boms:
        if part_name not in part_requirements:
            part_requirements[part_name] = 0
        # We want enough to build 100 of each widget type
        part_requirements[part_name] += quantity_needed * 100

    # Convert to list of tuples
    inventory = [(part_name, quantity) for part_name, quantity in part_requirements.items()]

    return inventory
