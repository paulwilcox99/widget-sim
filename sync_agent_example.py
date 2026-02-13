#!/usr/bin/env python3
"""
Synchronized Agent Example - Demonstrates using sim_state.json for synchronization.

This agent monitors the simulation state file and takes action when:
1. The simulation advances to a new day
2. Operations are disabled and need agent handling
3. Specific conditions are met in the databases
"""

import time
import subprocess
from pathlib import Path
from sim_state import SimulationState


class SynchronizedAgent:
    """Agent that synchronizes with simulation using state file."""

    def __init__(self):
        self.state = SimulationState()
        self.last_day = 0
        self.actions_taken = []

    def wait_for_simulation_start(self):
        """Wait for simulation to initialize."""
        print("🤖 AGENT: Waiting for simulation to start...")

        while True:
            state = self.state.read_state()
            if state and state["simulation"]["status"] != "initializing":
                print(f"🤖 AGENT: Simulation started at {state['simulation']['datetime']}")
                return state

            time.sleep(0.5)

    def wait_for_day_complete(self, expected_day: int):
        """Wait for a specific day to complete."""
        while True:
            state = self.state.read_state()
            if not state:
                time.sleep(0.1)
                continue

            current_day = state["simulation"]["day_number"]
            status = state["simulation"]["status"]

            # Day completed or simulation moved past this day
            if (current_day == expected_day and status == "day_complete") or \
               (current_day > expected_day):
                return state

            # Simulation finished
            if status in ["finished", "interrupted", "error"]:
                return None

            time.sleep(0.1)

    def handle_restock(self, sim_date: str):
        """Handle inventory restocking operation."""
        print(f"🤖 AGENT: Handling inventory restock for {sim_date}")

        result = subprocess.run(
            ['./venv/bin/python', 'update_inventory.py', sim_date],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("🤖 AGENT: ✓ Restock completed successfully")
            self.actions_taken.append(f"restock:{sim_date}")
            return True
        else:
            print(f"🤖 AGENT: ✗ Restock failed: {result.stderr[:100]}")
            return False

    def handle_process(self, sim_datetime: str):
        """Handle order processing operation."""
        print(f"🤖 AGENT: Handling order processing for {sim_datetime}")

        result = subprocess.run(
            ['./venv/bin/python', 'process_order.py', sim_datetime],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("🤖 AGENT: ✓ Order processing completed")
            self.actions_taken.append(f"process:{sim_datetime}")
            return True
        else:
            print(f"🤖 AGENT: ✗ Processing failed: {result.stderr[:100]}")
            return False

    def handle_ops(self, sim_datetime: str):
        """Handle manufacturing operations."""
        print(f"🤖 AGENT: Handling manufacturing operations for {sim_datetime}")

        result = subprocess.run(
            ['./venv/bin/python', 'run_ops.py', sim_datetime],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("🤖 AGENT: ✓ Manufacturing operations completed")
            self.actions_taken.append(f"ops:{sim_datetime}")
            return True
        else:
            print(f"🤖 AGENT: ✗ Operations failed: {result.stderr[:100]}")
            return False

    def handle_payroll(self, sim_date: str):
        """Handle payroll processing."""
        print(f"🤖 AGENT: Handling payroll for {sim_date}")

        result = subprocess.run(
            ['./venv/bin/python', 'pay_employees.py', sim_date],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("🤖 AGENT: ✓ Payroll processed successfully")
            self.actions_taken.append(f"payroll:{sim_date}")
            return True
        else:
            print(f"🤖 AGENT: ✗ Payroll failed: {result.stderr[:100]}")
            return False

    def process_pending_operations(self, state: dict):
        """Process all pending operations for current state."""
        pending = state["operations"]["pending"]

        if not pending:
            return

        sim_date = state["simulation"]["date"]
        sim_datetime = state["simulation"]["datetime"]

        print(f"\n🤖 AGENT: {len(pending)} pending operation(s) detected")

        for operation in pending:
            if operation == "restock":
                self.handle_restock(sim_date)
            elif operation == "process":
                self.handle_process(sim_datetime)
            elif operation == "ops":
                self.handle_ops(sim_datetime)
            elif operation == "payroll":
                self.handle_payroll(sim_date)

    def run(self):
        """Main agent loop - synchronizes with simulation."""
        print("=" * 70)
        print("🤖 SYNCHRONIZED AGENT")
        print("=" * 70)
        print("This agent monitors sim_state.json and handles disabled operations\n")

        # Wait for simulation to start
        initial_state = self.wait_for_simulation_start()

        disabled = initial_state["operations"]["disabled"]
        if disabled:
            print(f"🤖 AGENT: Will handle: {', '.join(disabled)}\n")
        else:
            print("🤖 AGENT: No operations disabled - monitoring only\n")

        # Monitor each day
        try:
            total_days = initial_state["simulation"]["total_days"]

            for day in range(1, total_days + 1):
                # Read current state
                state = self.state.read_state()
                if not state:
                    break

                current_day = state["simulation"]["day_number"]
                sim_date = state["simulation"]["date"]

                # Only process if we're on the expected day
                if current_day == day and state["simulation"]["status"] == "running":
                    print(f"\n{'='*70}")
                    print(f"🤖 AGENT: Day {day}/{total_days} - {sim_date}")
                    print(f"{'='*70}")

                    # Small delay to ensure simulation operations have started
                    time.sleep(1)

                    # Re-read state in case pending operations were updated
                    state = self.state.read_state()
                    if state:
                        self.process_pending_operations(state)

                # Wait for day to complete
                print(f"🤖 AGENT: Waiting for day {day} to complete...")
                result = self.wait_for_day_complete(day)

                if result is None:
                    print("🤖 AGENT: Simulation ended")
                    break

            # Final summary
            print(f"\n{'='*70}")
            print("🤖 AGENT: Simulation Complete")
            print(f"{'='*70}")
            print(f"Actions taken: {len(self.actions_taken)}")
            for action in self.actions_taken:
                print(f"  - {action}")

        except KeyboardInterrupt:
            print("\n\n🤖 AGENT: Stopped by user")
        except Exception as e:
            print(f"\n🤖 AGENT: Error - {e}")
            import traceback
            traceback.print_exc()


def main():
    """Run the synchronized agent."""
    agent = SynchronizedAgent()
    agent.run()


if __name__ == "__main__":
    main()
