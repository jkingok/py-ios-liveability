"""
Main execution entry point for the Liveability application.

Invoked when running the module directly via `python -m liveability` or when launched
by BeeWare Briefcase runtime launchers.
"""

from .app import main

if __name__ == "__main__":
    if m := main():
        m.main_loop()
