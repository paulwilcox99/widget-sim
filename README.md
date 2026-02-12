# Manufacturing Company Simulator

A comprehensive Python-based simulator for testing software in a manufacturing company environment. This simulator creates realistic databases and steps through time to simulate daily operations, making it perfect for testing monitoring software, database applications, and business intelligence tools.

## 🎯 Overview

The simulator models a complete manufacturing operation with:
- **Customer orders** flowing through the system
- **Inventory management** with automatic restocking
- **Manufacturing stages** (assembly, test, inspection, shipping)
- **Financial tracking** (revenue, expenses, payroll)
- **Employee management** and weekly payroll

## ✨ Features

- ✅ **Realistic data generation** using Faker
- ✅ **Multiple databases** (CRM, Inventory, MES, ERP)
- ✅ **Time-based progression** - simulate days, weeks, or months
- ✅ **Financial modeling** with ~30% gross margins
- ✅ **Interactive step mode** for controlled testing
- ✅ **Automated workflows** for CI/CD integration
- ✅ **SQLite databases** (easily migrated to PostgreSQL/MongoDB)

## 📦 Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd widget

# Create virtual environment
python3 -m venv venv

# Install dependencies
./venv/bin/pip install faker

# Initialize databases
./venv/bin/python create_sim.py
```

## 🚀 Quick Start

### Run a 30-day simulation
```bash
./venv/bin/python run_simulation.py 30 "2026-03-01"
```

### Interactive step mode (for testing)
```bash
./venv/bin/python run_simulation.py 7 --step
```

### Generate individual orders
```bash
./venv/bin/python gen_order.py -n 5
```

## 📊 Database Structure

The simulator creates 5 SQLite databases:

### 1. `customers.db` - Customer Pool
- 1,000 pre-generated customers with realistic data

### 2. `crm.db` - Customer Relationship Management
- **Orders**: order_id, customer_name, widget_type, quantity, unit_price, date_ordered, status, date_shipped

### 3. `inventory.db` - Inventory & BoM
- **Bill of Materials**: Widget components and costs
- **Inventory Levels**: Real-time stock quantities

### 4. `mes.db` - Manufacturing Execution System
- **Production Tracking**: 4 stages (assembly, test, inspection, shipping)
- Start and completion timestamps for each stage

### 5. `erp.db` - Enterprise Resource Planning
- **Employees**: 200 workers with titles and weekly salaries
- **Financial Transactions**: All payments, purchases, and revenue

## 🛠️ Tools & Scripts

| Script | Purpose |
|--------|---------|
| `create_sim.py` | Initialize all databases from scratch |
| `gen_order.py` | Generate customer orders |
| `process_order.py` | Process orders and deduct inventory |
| `update_inventory.py` | Restock low inventory |
| `run_ops.py` | Advance manufacturing stages |
| `pay_employees.py` | Process weekly payroll (Fridays) |
| `show_dbs.py` | Export database contents to markdown |
| `run_simulation.py` | **Orchestrate multi-day simulation** |

## 📖 Usage Examples

### Basic Simulation
```bash
# Simulate 30 days
./venv/bin/python run_simulation.py 30

# Simulate with specific start date
./venv/bin/python run_simulation.py 30 "2026-03-01"

# Continue existing simulation (don't reset databases)
./venv/bin/python run_simulation.py 30 --no-init
```

### Step Mode (Interactive Testing)
```bash
# Step through 7 days interactively
./venv/bin/python run_simulation.py 7 --step

# After each day, choose:
#   - Press Enter: continue to next day
#   - Type 's': show current summary
#   - Type 'q': quit and show final summary
```

### Individual Operations
```bash
# Generate 10 orders
./venv/bin/python gen_order.py -n 10

# Process pending orders
./venv/bin/python process_order.py

# Advance manufacturing
./venv/bin/python run_ops.py "2026-03-15 10:00:00"

# Restock inventory
./venv/bin/python update_inventory.py

# Pay employees (only on Fridays)
./venv/bin/python pay_employees.py "2026-03-14"

# Export databases to markdown
./venv/bin/python show_dbs.py
```

## 🧪 Testing Monitoring Software

The simulator is designed for testing database monitoring tools. See [TESTING_WITH_MONITORS.md](TESTING_WITH_MONITORS.md) for detailed examples.

### Example: Monitor Database Changes
```python
from example_monitor import DatabaseMonitor

monitor = DatabaseMonitor()
monitor.capture_baseline()

# Run simulation in step mode
# After each day:
changes = monitor.analyze_changes()
valid = monitor.check_invariants()
```

### Automated Testing
```bash
# Use named pipe for programmatic control
mkfifo /tmp/sim_control
./venv/bin/python run_simulation.py 30 --step < /tmp/sim_control &

# Control from another process
echo "" > /tmp/sim_control  # Advance one day
your_monitor --analyze databases/
echo "" > /tmp/sim_control  # Advance another day
```

## 💰 Financial Model

The simulator generates realistic financial data:

- **Revenue**: Based on orders shipped (~$6,200/unit for Widget_Pro)
- **COGS**: ~70% of revenue (30% gross margin)
- **Payroll**: 200 employees × ~$1,191/week average
- **Inventory**: Restocked every 3 days when levels are low

**Example 30-Day Results:**
```
Revenue (102 orders):        $4,488,798.81
COGS:                        $3,192,147.09
Gross Profit:                $1,296,651.72  (28.9% margin)
Payroll (4 weeks):           $  957,020.20
Net Profit:                  $  339,631.52
```

## 📁 Project Structure

```
widget/
├── create_sim.py              # Database initialization
├── schemas.py                 # Database schemas and wrappers
├── data_generators.py         # Faker-based data generation
├── gen_order.py              # Order generation tool
├── process_order.py          # Order processing tool
├── update_inventory.py       # Inventory restocking tool
├── run_ops.py                # Manufacturing operations tool
├── pay_employees.py          # Payroll processing tool
├── show_dbs.py               # Database export tool
├── run_simulation.py         # Main simulation orchestrator
├── example_monitor.py        # Example monitoring script
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── STEP_MODE_GUIDE.md       # Interactive step mode guide
├── TESTING_WITH_MONITORS.md # Testing guide
├── .gitignore               # Git ignore rules
├── venv/                    # Virtual environment (not in git)
└── databases/               # SQLite database files (not in git)
    ├── customers.db
    ├── crm.db
    ├── inventory.db
    ├── mes.db
    └── erp.db
```

## 🎓 Learning Resources

- **[STEP_MODE_GUIDE.md](STEP_MODE_GUIDE.md)** - Interactive step mode usage
- **[TESTING_WITH_MONITORS.md](TESTING_WITH_MONITORS.md)** - Integration with monitoring software
- **[example_monitor.py](example_monitor.py)** - Working monitoring example

## 🔧 Configuration

### Widget Types
The simulator includes 3 widget types with different costs:
- **Widget_Pro**: ~$4,826 cost, ~$6,200-7,600 sale price
- **Widget**: ~$1,491 cost, ~$1,900-2,350 sale price
- **Widget_Classic**: ~$2,647 cost, ~$3,400-4,200 sale price

### Simulation Parameters
- **Orders per day**: 0-20 (random)
- **Manufacturing stages**: 4 (3-72 hours each)
- **Inventory restock**: Every 3 days
- **Payroll**: Every Friday
- **Employees**: 200 workers

## 🤝 Contributing

This simulator is designed for testing purposes. Feel free to:
- Add new widget types
- Modify cost structures
- Add new databases or tables
- Create custom workflows
- Integrate with your monitoring tools

## 📝 License

This is a testing tool - use it however you need!

## 🐛 Troubleshooting

### Database locked errors
```bash
# Ensure no other processes are accessing databases
lsof databases/*.db
```

### Permission errors
```bash
# Make scripts executable
chmod +x *.py
```

### Missing dependencies
```bash
# Reinstall requirements
./venv/bin/pip install -r requirements.txt
```

## 📞 Support

See individual script help messages:
```bash
./venv/bin/python run_simulation.py --help
./venv/bin/python gen_order.py --help
# etc.
```

## 🎯 Use Cases

- ✅ Test database monitoring software
- ✅ Validate business intelligence tools
- ✅ Train on SQL queries with realistic data
- ✅ Demonstrate data pipelines
- ✅ Test ETL processes
- ✅ Benchmark database performance
- ✅ Develop data analytics dashboards

---

**Built with Python 3.10+ and SQLite**
