#!/usr/bin/env python3
"""Run the base management CLI against an explicit instance, including legacy instances."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_os.__main__ import main

if __name__ == "__main__":
    main()
