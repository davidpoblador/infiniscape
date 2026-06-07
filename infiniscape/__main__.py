# ABOUTME: Entry point so `python -m infiniscape` launches the world TUI.
# ABOUTME: Delegates to the interactive app loop.

from .app import main

if __name__ == "__main__":
    main()
