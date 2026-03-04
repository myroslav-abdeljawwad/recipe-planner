#!/usr/bin/env python3
"""
Recipe Planner Main Entry Point

This script initializes the environment, parses command line arguments,
and launches the terminal wizard that auto‑plans meals, suggests ingredient swaps,
and tracks pantry in real time.

Author: Myroslav Mokhammad Abdeljawwad
"""

import os
import sys
import logging
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv
except ImportError:
    # dotenv is optional; warn but continue
    logging.warning("python-dotenv not installed; environment variables may be missing.")
else:
    load_dotenv()

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Local imports (after dotenv to ensure env vars are loaded)
try:
    from cli.command import run_cli
    from planner.planner import MealPlanner
    from planner.state import PantryState
except Exception as exc:  # pragma: no cover
    logger.critical("Failed to import project modules: %s", exc, exc_info=True)
    sys.exit(1)

def _resolve_data_path(relative: str) -> Path:
    """
    Resolve a path relative to the project's root directory.
    The script may be executed from any working directory; this helper ensures
    deterministic access to data files such as ingredients.json and meals.yaml.
    """
    base = Path(__file__).parent.parent.resolve()
    return base / relative

def _load_initial_state() -> PantryState:
    """
    Load pantry state from a JSON file if it exists, otherwise start with an empty state.
    The state is stored in data/pantry_state.json to persist across sessions.
    """
    state_file = _resolve_data_path("data/pantry_state.json")
    if state_file.exists():
        try:
            return PantryState.load_from_file(state_file)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Failed to load pantry state from %s; starting fresh. Error: %s",
                state_file, exc
            )
    return PantryState()

def main() -> None:
    """
    Main entry point for the recipe-planner package.
    Sets up the planner with available meals and ingredients,
    loads the current pantry state, and starts the CLI wizard.
    """
    # Resolve data files
    ingredients_path = _resolve_data_path("data/ingredients.json")
    meals_path = _resolve_data_path("data/meals.yaml")

    if not ingredients_path.exists():
        logger.error("Ingredients file missing: %s", ingredients_path)
        sys.exit(1)

    if not meals_path.exists():
        logger.error("Meals file missing: %s", meals_path)
        sys.exit(1)

    # Initialize planner
    try:
        planner = MealPlanner(
            ingredients_file=ingredients_path,
            meals_file=meals_path
        )
    except Exception as exc:  # pragma: no cover
        logger.critical("Failed to initialize MealPlanner: %s", exc, exc_info=True)
        sys.exit(1)

    # Load pantry state
    pantry_state = _load_initial_state()

    # Run the interactive CLI wizard
    try:
        run_cli(planner=planner, pantry=pantry_state)
    except KeyboardInterrupt:  # Allow graceful exit on Ctrl+C
        logger.info("Interrupted by user; exiting.")
    finally:
        # Persist pantry state before exit
        try:
            pantry_state.save_to_file(_resolve_data_path("data/pantry_state.json"))
            logger.debug("Pantry state saved to disk.")
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Could not persist pantry state: %s", exc, exc_info=True
            )

if __name__ == "__main__":
    main()