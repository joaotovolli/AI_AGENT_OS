#!/usr/bin/env python3
"""Check tracked content before publishing. Does not print matched secret values."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_os.github import GitHub
from agent_os.state import State

GitHub(ROOT, State(ROOT)).scan_index()
print("Tracked content check passed")
