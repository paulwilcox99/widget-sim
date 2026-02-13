"""
Simulation State Management - Provides synchronization between simulation and agents.

The simulation writes state to a JSON file that agents can monitor to:
- Know current simulation time
- Detect when to take action
- Coordinate with simulation operations
- Track simulation progress
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Set


class SimulationState:
    """Manages simulation state file for agent synchronization."""

    def __init__(self, state_file: Path = Path("sim_state.json")):
        self.state_file = state_file

    def write_state(self,
                   sim_date: str,
                   sim_time: str,
                   day_number: int,
                   total_days: int,
                   status: str,
                   disabled_operations: Set[str] = None,
                   pending_operations: list = None):
        """
        Write current simulation state to file.

        Args:
            sim_date: Simulation date (YYYY-MM-DD)
            sim_time: Simulation time (HH:MM:SS)
            day_number: Current day number
            total_days: Total days to simulate
            status: Simulation status (initializing, running, day_complete, paused, finished)
            disabled_operations: Set of operations that are disabled
            pending_operations: List of operations that need to be performed
        """
        if disabled_operations is None:
            disabled_operations = set()
        if pending_operations is None:
            pending_operations = []

        state = {
            "simulation": {
                "date": sim_date,
                "time": sim_time,
                "datetime": f"{sim_date} {sim_time}",
                "day_number": day_number,
                "total_days": total_days,
                "status": status,
                "progress_percent": round((day_number / total_days) * 100, 1)
            },
            "operations": {
                "disabled": list(disabled_operations),
                "pending": pending_operations
            },
            "metadata": {
                "last_update": datetime.now().isoformat(),
                "state_version": "1.0"
            }
        }

        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def read_state(self) -> dict:
        """
        Read current simulation state from file.

        Returns:
            Dictionary with simulation state, or None if file doesn't exist
        """
        if not self.state_file.exists():
            return None

        with open(self.state_file, 'r') as f:
            return json.load(f)

    def wait_for_status(self, target_status: str, timeout: float = None) -> bool:
        """
        Wait for simulation to reach a specific status.

        Args:
            target_status: Status to wait for
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            True if status reached, False if timeout
        """
        import time
        start_time = time.time()

        while True:
            state = self.read_state()
            if state and state["simulation"]["status"] == target_status:
                return True

            if timeout and (time.time() - start_time) > timeout:
                return False

            time.sleep(0.1)

    def get_pending_operations(self) -> list:
        """
        Get list of operations that need to be performed by agents.

        Returns:
            List of operation names
        """
        state = self.read_state()
        if not state:
            return []

        return state["operations"]["pending"]

    def is_operation_disabled(self, operation: str) -> bool:
        """
        Check if an operation is disabled (should be handled by agent).

        Args:
            operation: Operation name (process, ops, restock, payroll)

        Returns:
            True if operation is disabled
        """
        state = self.read_state()
        if not state:
            return False

        return operation in state["operations"]["disabled"]

    def clear_state(self):
        """Remove state file (cleanup)."""
        if self.state_file.exists():
            self.state_file.unlink()
