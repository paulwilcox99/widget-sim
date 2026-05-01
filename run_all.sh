#!/usr/bin/env bash
# Orchestrates the widget-sim + LLM inventory agent together in auto mode.
# Usage: ./run_all.sh [DAYS] [START_DATE]
#   DAYS        number of simulation days (default: 30)
#   START_DATE  YYYY-MM-DD start date (default: today)
#   MODEL       OpenAI model override via env var (default: gpt-3.5-turbo)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$SCRIPT_DIR"
AGENT_DIR="$SCRIPT_DIR/simple-inventory"

DAYS="${1:-30}"
START_DATE="${2:-$(date +%Y-%m-%d)}"
MODEL="${MODEL:-gpt-3.5-turbo}"
DELAY=5   # seconds the sim pauses between days so agent can act

BLUE='\033[0;34m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'
RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

die()  { echo -e "\n${RED}[ERROR]${NC} $*" >&2; exit 1; }
info() { echo -e "${GREEN}[SETUP]${NC} $*"; }

# ── API key ────────────────────────────────────────────────────────────────────
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    if [[ -f "$AGENT_DIR/.env" ]]; then
        set -a; source "$AGENT_DIR/.env"; set +a
    fi
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
        die "OPENAI_API_KEY is not set.\n\n  Export it:       export OPENAI_API_KEY='sk-...'\n  Or create file:  $AGENT_DIR/.env with OPENAI_API_KEY=sk-..."
    fi
fi

# ── Virtual environments ───────────────────────────────────────────────────────
if [[ ! -f "$SIM_DIR/venv/bin/python" ]]; then
    info "Creating simulator venv and installing dependencies..."
    python3 -m venv "$SIM_DIR/venv" || die "Failed to create simulator venv"
    "$SIM_DIR/venv/bin/pip" install -q -r "$SIM_DIR/requirements.txt" \
        || die "Failed to install simulator dependencies"
fi

if [[ ! -f "$AGENT_DIR/venv/bin/python" ]]; then
    info "Creating agent venv and installing dependencies..."
    python3 -m venv "$AGENT_DIR/venv" || die "Failed to create agent venv"
    "$AGENT_DIR/venv/bin/pip" install -q -r "$AGENT_DIR/requirements.txt" \
        || die "Failed to install agent dependencies"
fi

# ── Databases ─────────────────────────────────────────────────────────────────
if [[ ! -f "$SIM_DIR/databases/crm.db" ]]; then
    info "Initializing simulation databases..."
    (cd "$SIM_DIR" && ./venv/bin/python create_sim.py) \
        || die "Failed to initialize databases"
fi

# ── FIFOs for prefixed, interleaved output ────────────────────────────────────
SIM_FIFO=$(mktemp -u /tmp/widget_sim_XXXXXX)
AGENT_FIFO=$(mktemp -u /tmp/widget_agent_XXXXXX)
mkfifo "$SIM_FIFO" "$AGENT_FIFO"

# ── Cleanup ───────────────────────────────────────────────────────────────────
SIM_PID="" AGENT_PID=""
cleanup() {
    echo -e "\n${YELLOW}[INFO] Shutting down...${NC}"
    [[ -n "${SIM_PID:-}" ]]   && kill "$SIM_PID"   2>/dev/null || true
    [[ -n "${AGENT_PID:-}" ]] && kill "$AGENT_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    rm -f "$SIM_FIFO" "$AGENT_FIFO"
    echo -e "${YELLOW}[INFO] Done.${NC}"
}
trap cleanup EXIT INT TERM

# ── Header ────────────────────────────────────────────────────────────────────
echo -e "\n${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Widget Manufacturing Sim + LLM Inventory Agent${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
printf "  Days: %-6s  Start: %-12s  Model: %s\n" "$DAYS" "$START_DATE" "$MODEL"
printf "  Delay: %ss between sim days  |  Restocking: handled by LLM agent\n" "$DELAY"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}\n"

# ── FIFO readers — prefix each output line ─────────────────────────────────────
while IFS= read -r line; do printf "${BLUE}[SIM]${NC}   %s\n" "$line"; done < "$SIM_FIFO" &
while IFS= read -r line; do printf "${CYAN}[AGENT]${NC} %s\n" "$line"; done < "$AGENT_FIFO" &

# ── Launch simulator ──────────────────────────────────────────────────────────
(cd "$SIM_DIR" && exec ./venv/bin/python run_simulation.py \
    "$DAYS" "$START_DATE" --disable restock --delay "$DELAY") \
    > "$SIM_FIFO" 2>&1 &
SIM_PID=$!

# Small delay so the simulator writes sim_state.json before the agent looks for it
sleep 2

# ── Launch agent ──────────────────────────────────────────────────────────────
(cd "$AGENT_DIR" && exec ./venv/bin/python -u llm_inventory_agent.py \
    --simulation --model "$MODEL" --check-interval 2) \
    > "$AGENT_FIFO" 2>&1 &
AGENT_PID=$!

echo -e "  ${BLUE}[SIM]${NC}   PID $SIM_PID"
echo -e "  ${CYAN}[AGENT]${NC} PID $AGENT_PID"
echo -e "  Press Ctrl+C to stop both.\n"

# ── Wait for simulator to finish, then let agent drain ────────────────────────
wait "$SIM_PID" || true
echo -e "\n${GREEN}[INFO] Simulator finished. Waiting for agent to exit...${NC}"

# Agent exits on its own when it reads status=finished from sim_state.json.
# Give it up to 30s before force-killing.
for i in $(seq 1 30); do
    kill -0 "$AGENT_PID" 2>/dev/null || break
    sleep 1
done
kill "$AGENT_PID" 2>/dev/null || true

echo -e "${GREEN}[INFO] Simulation complete.${NC}"
