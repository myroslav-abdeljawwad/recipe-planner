"""
recipe-planner – Planner core
Author: Myroslav Mokhammad Abdeljawwad

This module implements the main planning logic used by the terminal wizard.
It loads recipes from YAML, ingredients from JSON, and uses a simple
constraint‑based approach to create a weekly meal plan while respecting
pantry availability.  The public API is intentionally small:
`generate_weekly_plan`, `suggest_swap`, and `update_pantry`.

The design keeps business logic isolated from I/O so that unit tests can
exercise the core without touching the filesystem.
"""

from __future__ import annotations

import json
import logging
import random
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional

# --------------------------------------------------------------------------- #
# Configuration and constants
# --------------------------------------------------------------------------- #

LOGGER = logging.getLogger(__name__)
DEFAULT_MEALS_FILE = Path("data/meals.yaml")
DEFAULT_INGREDIENTS_FILE = Path("data/ingredients.json")

# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #

class Ingredient:
    """Represents a pantry item with quantity and unit."""

    def __init__(self, name: str, amount: float, unit: str):
        self.name = name.lower()
        self.amount = amount
        self.unit = unit

    def consume(self, quantity: float) -> None:
        if quantity < 0:
            raise ValueError("Quantity to consume must be non‑negative")
        self.amount -= quantity
        LOGGER.debug(
            "Consumed %s of %s; remaining: %.2f %s",
            quantity,
            self.name,
            self.amount,
            self.unit,
        )

    def add(self, quantity: float) -> None:
        if quantity < 0:
            raise ValueError("Quantity to add must be non‑negative")
        self.amount += quantity
        LOGGER.debug(
            "Added %s of %s; total: %.2f %s",
            quantity,
            self.name,
            self.amount,
            self.unit,
        )


class RecipeIngredient:
    """Ingredient needed for a recipe."""

    def __init__(self, name: str, amount: float, unit: str):
        self.name = name.lower()
        self.amount = amount
        self.unit = unit


class Recipe:
    """Represents a meal with its required ingredients."""

    def __init__(self, name: str, ingredients: List[RecipeIngredient]):
        self.name = name
        self.ingredients = ingredients

    @classmethod
    def from_dict(cls, data: Dict) -> "Recipe":
        ing_list = [
            RecipeIngredient(ing["name"], ing["amount"], ing["unit"])
            for ing in data.get("ingredients", [])
        ]
        return cls(name=data["name"], ingredients=ing_list)


# --------------------------------------------------------------------------- #
# Core planner logic
# --------------------------------------------------------------------------- #

class Planner:
    """
    Handles loading recipes, generating a weekly plan, and updating pantry.
    """

    def __init__(
        self,
        meals_file: Path = DEFAULT_MEALS_FILE,
        ingredients_file: Path = DEFAULT_INGREDIENTS_FILE,
    ) -> None:
        self.meals_file = meals_file
        self.ingredients_file = ingredients_file
        self.recipes: List[Recipe] = []
        self.pantry: Dict[str, Ingredient] = {}
        self._load_data()

    # --------------------------------------------------------------------- #
    # Data loading helpers
    # --------------------------------------------------------------------- #

    def _load_data(self) -> None:
        """Load recipes and pantry from disk."""
        LOGGER.debug("Loading data from %s and %s", self.meals_file, self.ingredients_file)
        try:
            with open(self.meals_file, encoding="utf-8") as fh:
                meals_yaml = yaml.safe_load(fh)
        except FileNotFoundError as exc:
            raise RuntimeError(f"Meals file not found: {self.meals_file}") from exc

        if not isinstance(meals_yaml, list):
            raise ValueError("Meals YAML must contain a list of recipes")

        self.recipes = [Recipe.from_dict(rec) for rec in meals_yaml]

        try:
            with open(self.ingredients_file, encoding="utf-8") as fh:
                pantry_json = json.load(fh)
        except FileNotFoundError as exc:
            raise RuntimeError(f"Pantry file not found: {self.ingredients_file}") from exc

        if not isinstance(pantry_json, dict):
            raise ValueError("Ingredients JSON must be a dictionary")

        self.pantry = {
            name.lower(): Ingredient(name, data["amount"], data["unit"])
            for name, data in pantry_json.items()
        }
        LOGGER.debug("Loaded %d recipes and %d pantry items", len(self.recipes), len(self.pantry))

    # --------------------------------------------------------------------- #
    # Planning algorithms
    # --------------------------------------------------------------------- #

    def _recipe_fits(self, recipe: Recipe) -> bool:
        """Check if the pantry has enough for a recipe."""
        for ing in recipe.ingredients:
            pantry_ing = self.pantry.get(ing.name)
            if not pantry_ing or pantry_ing.amount < ing.amount:
                return False
        return True

    def _consume_recipe(self, recipe: Recipe) -> None:
        """Consume the required ingredients from pantry."""
        for ing in recipe.ingredients:
            pantry_ing = self.pantry[ing.name]
            pantry_ing.consume(ing.amount)

    def generate_weekly_plan(
        self,
        days: int = 7,
        max_per_meal_type: Optional[int] = None,
    ) -> List[str]:
        """
        Return a list of recipe names for the given number of days.

        Parameters
        ----------
        days : int
            Number of days to plan for.
        max_per_meal_type : int, optional
            Maximum times a single recipe can appear in the week.
        """
        if days <= 0:
            raise ValueError("Days must be positive")

        available = [r for r in self.recipes if self._recipe_fits(r)]
        if not available:
            raise RuntimeError("No recipes fit current pantry constraints")

        plan: List[str] = []
        usage: Dict[str, int] = {}
        attempts = 0
        max_attempts = days * 10

        while len(plan) < days and attempts < max_attempts:
            candidate = random.choice(available)
            if max_per_meal_type is not None:
                if usage.get(candidate.name, 0) >= max_per_meal_type:
                    attempts += 1
                    continue
            # Verify again after potential pantry changes
            if not self._recipe_fits(candidate):
                attempts += 1
                continue

            plan.append(candidate.name)
            usage[candidate.name] = usage.get(candidate.name, 0) + 1
            self._consume_recipe(candidate)
            LOGGER.debug("Added %s to plan; remaining pantry: %s", candidate.name, {k: v.amount for k, v in self.pantry.items()})
        if len(plan) < days:
            raise RuntimeError(f"Could not generate full plan after {max_attempts} attempts")
        return plan

    # --------------------------------------------------------------------- #
    # Pantry manipulation
    # --------------------------------------------------------------------- #

    def update_pantry(self, updates: Iterable[Tuple[str, float]]) -> None:
        """
        Update pantry quantities.

        Parameters
        ----------
        updates : iterable of (name, amount)
            Positive amounts add to stock; negative amounts consume.
        """
        for name, qty in updates:
            key = name.lower()
            if key not in self.pantry:
                raise KeyError(f"Ingredient {name} not found in pantry")
            if qty >= 0:
                self.pantry[key].add(qty)
            else:
                self.pantry[key].consume(-qty)

    # --------------------------------------------------------------------- #
    # Ingredient swap suggestions
    # --------------------------------------------------------------------- #

    def suggest_swap(
        self,
        recipe_name: str,
        missing_ing: str,
    ) -> Optional[Tuple[str, float]]:
        """
        Suggest an alternative ingredient that can replace a missing one.

        Parameters
        ----------
        recipe_name : str
            Name of the recipe to analyze.
        missing_ing : str
            Ingredient name that is lacking in pantry.

        Returns
        -------
        Tuple[alternative_name, quantity_needed] or None if no swap possible.
        """
        candidate = next((r for r in self.recipes if r.name == recipe_name), None)
        if not candidate:
            raise ValueError(f"Recipe {recipe_name} not found")

        missing_req = next(
            (ing.amount for ing in candidate.ingredients if ing.name == missing_ing.lower()),
            None,
        )
        if missing_req is None:
            raise ValueError(f"{missing_ing} not required by {recipe_name}")

        # Very naive swap: look for any ingredient that the pantry has at least
        # half the amount needed and could substitute (same unit).
        for alt, ing_obj in self.pantry.items():
            if alt == missing_ing.lower():
                continue
            if ing_obj.unit != next((ing.unit for ing in candidate.ingredients if ing.name == missing_ing.lower()), None):
                continue
            if ing_obj.amount >= missing_req * 0.5:
                return (alt, missing_req - ing_obj.amount)
        return None

# --------------------------------------------------------------------------- #
# Public helper functions used by CLI
# --------------------------------------------------------------------------- #

def load_planner(
    meals_file: Path = DEFAULT_MEALS_FILE,
    ingredients_file: Path = DEFAULT_INGREDIENTS_FILE,
) -> Planner:
    """Convenience factory for the CLI."""
    return Planner(meals_file, ingredients_file)

def generate_weekly_plan(
    planner: Planner,
    days: int = 7,
    max_per_meal_type: Optional[int] = None,
) -> List[str]:
    """Wrapper around Planner.generate_weekly_plan."""
    return planner.generate_weekly_plan(days, max_per_meal_type)