"""
Utilities for the recipe-planner project.
Author: Myroslav Mokhammad Abdeljawwad
"""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import logging

# Configure a module-level logger
_logger = logging.getLogger(__name__)
if not _logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


def load_json(file_path: Path) -> Dict[str, Any]:
    """
    Load a JSON file and return its contents as a dictionary.
    Raises ValueError if the file cannot be parsed.
    """
    try:
        with file_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            _logger.debug("Loaded JSON from %s: %s keys", file_path, len(data))
            return data
    except FileNotFoundError as exc:
        raise ValueError(f"JSON file not found: {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {file_path}: {exc}") from exc


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load a YAML file and return its contents as a dictionary.
    Raises ValueError if the file cannot be parsed.
    """
    try:
        with file_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            _logger.debug("Loaded YAML from %s: %s keys", file_path, len(data))
            return data
    except FileNotFoundError as exc:
        raise ValueError(f"YAML file not found: {file_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {file_path}: {exc}") from exc


def validate_ingredient(
    ingredient_name: str, pantry: Set[str], available_swaps: Dict[str, List[str]]
) -> bool:
    """
    Check if an ingredient is either in the pantry or has a valid swap.
    """
    if ingredient_name in pantry:
        return True
    swaps = available_swaps.get(ingredient_name, [])
    return any(swap in pantry for swap in swaps)


def suggest_swap(
    ingredient: str,
    pantry: Set[str],
    available_swaps: Dict[str, List[str]],
) -> Optional[str]:
    """
    Return the first viable swap for an ingredient that is present in the pantry.
    If no swap exists, return None.
    """
    for candidate in available_swaps.get(ingredient, []):
        if candidate in pantry:
            _logger.info("Suggesting swap: %s -> %s", ingredient, candidate)
            return candidate
    return None


def compute_shopping_list(
    meal_ingredients: List[str],
    pantry: Set[str],
    available_swaps: Dict[str, List[str]],
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Given a list of required ingredients for a meal, the current pantry,
    and possible swaps, compute:
      - A list of items that must be purchased.
      - A list of tuples (original, swap) for suggested replacements.

    Returns a tuple: (to_buy, swaps)
    """
    to_buy: List[str] = []
    swaps: List[Tuple[str, str]] = []

    for ingredient in meal_ingredients:
        if validate_ingredient(ingredient, pantry, available_swaps):
            # Ingredient is satisfied either directly or via swap
            continue
        # Attempt a swap first
        swap_candidate = suggest_swap(ingredient, pantry, available_swaps)
        if swap_candidate:
            swaps.append((ingredient, swap_candidate))
            continue
        # No swap; must buy
        to_buy.append(ingredient)

    _logger.debug("Computed shopping list: %s items to buy, %s swaps", len(to_buy), len(swaps))
    return to_buy, swaps


def read_config(config_path: Path) -> Dict[str, Any]:
    """
    Load the project's configuration YAML file.
    Raises ValueError on errors.
    """
    config = load_yaml(config_path)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a mapping: {config_path}")
    _logger.debug("Loaded configuration with keys: %s", list(config.keys()))
    return config


def sanitize_quantity(value: Any) -> float:
    """
    Convert quantity input to a positive float.
    Raises ValueError if conversion fails or value is non-positive.
    """
    try:
        qty = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be numeric: {value}") from None
    if qty <= 0:
        raise ValueError(f"Quantity must be positive: {qty}")
    return qty


def parse_ingredient_entry(entry: Any) -> Tuple[str, float]:
    """
    Accept an ingredient entry in either of the forms:
      - {"name": "sugar", "quantity": 200}
      - ["flour", 1.5]
    Return a tuple (name, quantity).
    """
    if isinstance(entry, dict):
        name = entry.get("name")
        qty = entry.get("quantity")
    elif isinstance(entry, list) and len(entry) == 2:
        name, qty = entry
    else:
        raise ValueError(f"Invalid ingredient format: {entry}")

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Ingredient name must be a non-empty string: {name}")
    quantity = sanitize_quantity(qty)
    return name.strip().lower(), quantity


def aggregate_ingredients(
    meal_list: List[List[Any]],
) -> Dict[str, float]:
    """
    Given a list of meals (each a list of ingredient entries),
    produce an aggregated dict mapping ingredient names to total quantities.
    """
    totals: Dict[str, float] = {}
    for meal in meal_list:
        if not isinstance(meal, list):
            continue
        for entry in meal:
            name, qty = parse_ingredient_entry(entry)
            totals[name] = totals.get(name, 0.0) + qty
    _logger.debug("Aggregated ingredients: %s items", len(totals))
    return totals


def filter_recipes_by_diet(
    recipes: List[Dict[str, Any]],
    diet_tags: Set[str],
) -> List[Dict[str, Any]]:
    """
    Return only those recipes that contain all requested diet tags.
    Each recipe is expected to have a 'tags' key containing a list of strings.
    """
    filtered = []
    for recipe in recipes:
        tags = set(recipe.get("tags", []))
        if diet_tags.issubset(tags):
            filtered.append(recipe)
    _logger.info(
        "Filtered recipes: %s out of %s match diet tags %s",
        len(filtered),
        len(recipes),
        diet_tags,
    )
    return filtered


def save_json(data: Any, path: Path) -> None:
    """
    Write data to a JSON file with pretty formatting.
    """
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        _logger.debug("Saved JSON to %s", path)
    except Exception as exc:
        raise IOError(f"Failed to write JSON to {path}") from exc


def save_yaml(data: Any, path: Path) -> None:
    """
    Write data to a YAML file.
    """
    try:
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False)
        _logger.debug("Saved YAML to %s", path)
    except Exception as exc:
        raise IOError(f"Failed to write YAML to {path}") from exc