#!/usr/bin/env python3
"""
recipe-planner CLI command module.
Author: Myroslav Mokhammad Abdeljawwad
"""

import os
import sys
import json
import yaml
import click
from pathlib import Path

# Local imports – adjust package name if needed
try:
    from planner.state import PantryState, load_state, save_state
    from planner.planner import plan_meals, suggest_swaps
except ImportError as exc:  # pragma: no cover
    click.echo(f"Failed to import project modules: {exc}", err=True)
    sys.exit(1)

# Load configuration (minimal example)
CONFIG_PATH = Path("config/config.yaml")
if CONFIG_PATH.exists():
    with CONFIG_PATH.open() as f:
        config = yaml.safe_load(f) or {}
else:
    config = {}

DEFAULT_DAYS = config.get("default_days", 7)


def _ensure_state_file(state_path: Path):
    """
    Ensure the pantry state file exists; create an empty one if not.
    """
    if not state_path.exists():
        click.echo(f"Creating new pantry state at {state_path}")
        save_state(PantryState(pantry={}), state_path)


@click.group()
def cli() -> None:
    """recipe-planner: Terminal wizard for meal planning and pantry tracking."""
    pass


@cli.command(name="plan")
@click.option(
    "-d",
    "--days",
    default=DEFAULT_DAYS,
    show_default=True,
    type=int,
    help="Number of days to generate a plan for.",
)
@click.option(
    "-s",
    "--state-file",
    type=click.Path(dir_okay=False, writable=True),
    default="data/pantry_state.json",
    show_default=True,
    help="Path to pantry state JSON file.",
)
def command_plan(days: int, state_file: str) -> None:
    """Generate a meal plan for the next *days* days."""
    try:
        if days <= 0:
            raise ValueError("Number of days must be positive.")
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    state_path = Path(state_file).expanduser()
    _ensure_state_file(state_path)
    pantry_state = load_state(state_path)

    try:
        plan = plan_meals(pantry_state, days)
    except Exception as exc:  # pragma: no cover
        click.echo(f"Planning failed: {exc}", err=True)
        sys.exit(1)

    click.echo("Meal Plan:")
    for idx, meal in enumerate(plan, start=1):
        click.echo(f"{idx}. {meal['name']} - Ingredients: {', '.join(meal['ingredients'])}")


@cli.command(name="suggest-swap")
@click.argument("ingredient", type=str)
@click.option(
    "-s",
    "--state-file",
    type=click.Path(dir_okay=False, writable=True),
    default="data/pantry_state.json",
    show_default=True,
    help="Path to pantry state JSON file.",
)
def command_suggest_swap(ingredient: str, state_file: str) -> None:
    """Suggest alternative ingredients for *INGREDIENT*."""
    state_path = Path(state_file).expanduser()
    if not state_path.exists():
        click.echo(f"Pantry state file {state_path} does not exist.", err=True)
        sys.exit(1)

    pantry_state = load_state(state_path)

    try:
        swaps = suggest_swaps(pantry_state, ingredient)
    except Exception as exc:  # pragma: no cover
        click.echo(f"Swap suggestion failed: {exc}", err=True)
        sys.exit(1)

    if not swaps:
        click.echo(f"No alternative suggestions found for '{ingredient}'.")
    else:
        click.echo(f"Alternative ingredients for '{ingredient}':")
        for alt in swaps:
            click.echo(f"- {alt}")


@cli.command(name="add-to-pantry")
@click.argument("item", type=str)
@click.option(
    "-q",
    "--quantity",
    default=1,
    show_default=True,
    type=int,
    help="Quantity to add.",
)
@click.option(
    "-s",
    "--state-file",
    type=click.Path(dir_okay=False, writable=True),
    default="data/pantry_state.json",
    show_default=True,
    help="Path to pantry state JSON file.",
)
def command_add_to_pantry(item: str, quantity: int, state_file: str) -> None:
    """Add an item with *QUANTITY* to the pantry."""
    if quantity <= 0:
        click.echo("Quantity must be positive.", err=True)
        sys.exit(1)

    state_path = Path(state_file).expanduser()
    _ensure_state_file(state_path)
    pantry_state = load_state(state_path)

    pantry_state.pantry[item] = pantry_state.pantry.get(item, 0) + quantity
    save_state(pantry_state, state_path)
    click.echo(f"Added {quantity} of '{item}' to pantry.")


@cli.command(name="remove-from-pantry")
@click.argument("item", type=str)
@click.option(
    "-q",
    "--quantity",
    default=1,
    show_default=True,
    type=int,
    help="Quantity to remove.",
)
@click.option(
    "-s",
    "--state-file",
    type=click.Path(dir_okay=False, writable=True),
    default="data/pantry_state.json",
    show_default=True,
    help="Path to pantry state JSON file.",
)
def command_remove_from_pantry(item: str, quantity: int, state_file: str) -> None:
    """Remove an item with *QUANTITY* from the pantry."""
    if quantity <= 0:
        click.echo("Quantity must be positive.", err=True)
        sys.exit(1)

    state_path = Path(state_file).expanduser()
    if not state_path.exists():
        click.echo(f"Pantry state file {state_path} does not exist.", err=True)
        sys.exit(1)

    pantry_state = load_state(state_path)

    current_qty = pantry_state.pantry.get(item, 0)
    if current_qty == 0:
        click.echo(f"Item '{item}' is not in the pantry.", err=True)
        sys.exit(1)

    new_qty = max(current_qty - quantity, 0)
    if new_qty == 0:
        pantry_state.pantry.pop(item)
    else:
        pantry_state.pantry[item] = new_qty

    save_state(pantry_state, state_path)
    click.echo(f"Removed {quantity} of '{item}' from pantry.")


@cli.command(name="show-pantry")
@click.option(
    "-s",
    "--state-file",
    type=click.Path(dir_okay=False),
    default="data/pantry_state.json",
    show_default=True,
    help="Path to pantry state JSON file.",
)
def command_show_pantry(state_file: str) -> None:
    """Display current pantry contents."""
    state_path = Path(state_file).expanduser()
    if not state_path.exists():
        click.echo(f"Pantry state file {state_path} does not exist.", err=True)
        sys.exit(1)

    pantry_state = load_state(state_path)
    if not pantry_state.pantry:
        click.echo("Pantry is empty.")
        return

    click.echo("Current Pantry:")
    for item, qty in sorted(pantry_state.pantry.items()):
        click.echo(f"- {item}: {qty}")


if __name__ == "__main__":
    cli()