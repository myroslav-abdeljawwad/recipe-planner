"""State management for the recipe‑planner project.
Author: Myroslav Mokhammad Abdeljawwad
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import yaml

# Configure module‑level logger
_logger = logging.getLogger(__name__)
if not _logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s:%(name)s: %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


# --------------------------------------------------------------------------- #
# Utility helpers
# --------------------------------------------------------------------------- #


def _ensure_file_exists(path: Path) -> None:
    """Create an empty file if it does not exist."""
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            _logger.debug("Created missing file %s", path)
        except OSError as exc:
            raise RuntimeError(f"Cannot create file {path}") from exc


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #


@dataclass
class Ingredient:
    """Represents an ingredient in the pantry."""

    name: str
    quantity: float  # In grams or units, depending on unit type
    unit: str

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError(f"Quantity for {self.name} cannot be negative")
        if not self.unit:
            raise ValueError("Unit must be specified")

    def to_dict(self) -> Dict[str, object]:
        return {"name": self.name, "quantity": self.quantity, "unit": self.unit}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Ingredient":
        return cls(
            name=str(data["name"]),
            quantity=float(data["quantity"]),
            unit=str(data["unit"]),
        )


@dataclass
class Meal:
    """Represents a meal with its required ingredients."""

    name: str
    ingredients: List[Tuple[str, float]]  # (ingredient_name, amount_needed)

    def to_dict(self) -> Dict[str, object]:
        return {"name": self.name, "ingredients": self.ingredients}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Meal":
        return cls(
            name=str(data["name"]),
            ingredients=[tuple(map(float, [ing[0], ing[1]])) for ing in data["ingredients"]],
        )


# --------------------------------------------------------------------------- #
# State class
# --------------------------------------------------------------------------- #


class PlannerState:
    """
    Central state holder for the recipe‑planner.

    This class is responsible for loading and persisting pantry contents,
    tracking planned meals, and providing helper methods such as
    ingredient availability checks and swap suggestions.
    """

    def __init__(
        self,
        pantry_path: Optional[Path] = None,
        plan_path: Optional[Path] = None,
    ) -> None:
        self._pantry_path = Path(pantry_path) if pantry_path else Path("data") / "pantry.json"
        self._plan_path = Path(plan_path) if plan_path else Path("data") / "meal_plan.yaml"

        _ensure_file_exists(self._pantry_path)
        _ensure_file_exists(self._plan_path)

        self.pantry: MutableMapping[str, Ingredient] = {}
        self.meal_plan: List[Meal] = []

        self.load()

    # --------------------------------------------------------------------- #
    # Persistence
    # --------------------------------------------------------------------- #

    def load(self) -> None:
        """Load pantry and meal plan from disk."""
        try:
            with open(self._pantry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.pantry = {
                    ing["name"]: Ingredient.from_dict(ing) for ing in data.get("ingredients", [])
                }
                _logger.debug("Loaded pantry from %s", self._pantry_path)
        except (FileNotFoundError, json.JSONDecodeError):
            _logger.warning("Pantry file missing or corrupted; starting with empty pantry.")
            self.pantry = {}

        try:
            with open(self._plan_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                meals_data = data.get("meals", [])
                self.meal_plan = [Meal.from_dict(m) for m in meals_data]
                _logger.debug("Loaded meal plan from %s", self._plan_path)
        except (FileNotFoundError, yaml.YAMLError):
            _logger.warning("Meal plan file missing or corrupted; starting with empty plan.")
            self.meal_plan = []

    def save(self) -> None:
        """Persist current state to disk."""
        pantry_data = {"ingredients": [ing.to_dict() for ing in self.pantry.values()]}
        with open(self._pantry_path, "w", encoding="utf-8") as f:
            json.dump(pantry_data, f, indent=2)
            _logger.debug("Saved pantry to %s", self._pantry_path)

        plan_data = {"meals": [meal.to_dict() for meal in self.meal_plan]}
        with open(self._plan_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(plan_data, f)
            _logger.debug("Saved meal plan to %s", self._plan_path)

    # --------------------------------------------------------------------- #
    # Pantry manipulation
    # --------------------------------------------------------------------- #

    def add_ingredient(self, name: str, quantity: float, unit: str) -> None:
        """Add or update an ingredient in the pantry."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        key = name.lower()
        existing = self.pantry.get(key)
        if existing:
            existing.quantity += quantity
            _logger.info("Updated %s: +%f %s", name, quantity, unit)
        else:
            self.pantry[key] = Ingredient(name=name, quantity=quantity, unit=unit)
            _logger.info("Added new ingredient %s (%f %s)", name, quantity, unit)

    def remove_ingredient(self, name: str, quantity: float) -> None:
        """Remove a specified amount of an ingredient."""
        key = name.lower()
        if key not in self.pantry:
            raise KeyError(f"Ingredient {name} not found in pantry")
        ing = self.pantry[key]
        if quantity <= 0 or quantity > ing.quantity:
            raise ValueError("Invalid removal quantity")
        ing.quantity -= quantity
        _logger.info("Removed %f %s from %s", quantity, ing.unit, name)
        if ing.quantity == 0:
            del self.pantry[key]
            _logger.debug("Ingredient %s depleted and removed", name)

    def get_ingredient(self, name: str) -> Optional[Ingredient]:
        """Retrieve an ingredient by name."""
        return self.pantry.get(name.lower())

    # --------------------------------------------------------------------- #
    # Meal plan manipulation
    # --------------------------------------------------------------------- #

    def add_meal(self, meal: Meal) -> None:
        """Append a meal to the current plan."""
        if any(m.name == meal.name for m in self.meal_plan):
            raise ValueError(f"Meal {meal.name} already planned")
        self.meal_plan.append(meal)
        _logger.info("Added meal %s to plan", meal.name)

    def remove_meal(self, name: str) -> None:
        """Remove a meal from the plan by name."""
        before = len(self.meal_plan)
        self.meal_plan = [m for m in self.meal_plan if m.name != name]
        after = len(self.meal_plan)
        if before == after:
            raise KeyError(f"Meal {name} not found in plan")
        _logger.info("Removed meal %s from plan", name)

    def clear_plan(self) -> None:
        """Clear all planned meals."""
        self.meal_plan.clear()
        _logger.info("Cleared entire meal plan")

    # --------------------------------------------------------------------- #
    # Utility methods
    # --------------------------------------------------------------------- #

    def check_availability(self, meal: Meal) -> Tuple[bool, List[str]]:
        """
        Verify if the pantry contains enough ingredients for a meal.

        Returns:
            (is_available, missing_ingredients)
        """
        missing = []
        for ing_name, amount_needed in meal.ingredients:
            ing = self.get_ingredient(ing_name)
            if not ing or ing.quantity < amount_needed:
                missing.append(f"{ing_name} ({amount_needed})")
        return not missing, missing

    def suggest_swaps(self, meal: Meal) -> List[Tuple[str, str]]:
        """
        Provide simple swap suggestions for missing ingredients.

        For each missing ingredient, find another available ingredient
        with the same unit type. This is a naive heuristic and can be
        expanded later.
        """
        swaps = []
        for ing_name, amount_needed in meal.ingredients:
            ing = self.get_ingredient(ing_name)
            if ing and ing.quantity >= amount_needed:
                continue  # Available

            # Find candidate with same unit
            for cand in self.pantry.values():
                if cand.unit == ing.unit and cand.name.lower() != ing_name.lower():
                    swaps.append((cand.name, ing_name))
                    break
        return swaps

    def total_pantry_weight(self) -> float:
        """Sum of all ingredient quantities (assuming same unit)."""
        return sum(ing.quantity for ing in self.pantry.values())

    # --------------------------------------------------------------------- #
    # Representation helpers
    # --------------------------------------------------------------------- #

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<PlannerState pantry={len(self.pantry)} meals={len(self.meal_plan)}>"

    def __str__(self) -> str:  # pragma: no cover - trivial
        lines = ["Pantry:"]
        for ing in sorted(self.pantry.values(), key=lambda i: i.name):
            lines.append(f"  {ing.name}: {ing.quantity} {ing.unit}")
        lines.append("\nMeal Plan:")
        for meal in self.meal_plan:
            lines.append(f"  - {meal.name}")
        return "\n".join(lines)