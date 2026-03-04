"""Test suite for the recipe-planner project.
Author: Myroslav Mokhammad Abdeljawwad
"""

import json
import os
from pathlib import Path

import pytest
import yaml

# Import the classes from the package
from planner.planner import Planner
from planner.state import PantryState


@pytest.fixture(scope="module")
def data_paths():
    """Return absolute paths to the bundled data files."""
    base = Path(__file__).parent.parent  # project root
    return {
        "ingredients": base / "data" / "ingredients.json",
        "meals": base / "data" / "meals.yaml",
        "config": base / "config" / "config.yaml",
    }


@pytest.fixture(scope="module")
def planner_instance(data_paths):
    """Instantiate a Planner with the sample data."""
    return Planner(
        ingredients_path=data_paths["ingredients"],
        meals_path=data_paths["meals"],
        config_path=data_paths["config"],
    )


def test_planner_initialization(planner_instance):
    """Planner should load ingredients, meals and config without errors."""
    # State objects must be initialized
    assert isinstance(planner_instance.pantry_state, PantryState)
    # Basic sanity checks on loaded data
    assert len(planner_instance.ingredients) > 0
    assert len(planner_instance.meals) > 0
    assert planner_instance.config is not None


def test_plan_weekly_meals(planner_instance):
    """Planning a week should return exactly seven meals, one per day."""
    plan = planner_instance.plan_week()
    # Expect a dict with keys for each weekday
    expected_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    assert set(plan.keys()) == expected_days

    for day, meal in plan.items():
        # Each day should have a valid meal name from the meals list
        assert meal in planner_instance.meals
        # The meal should be represented as a dict with ingredients and instructions
        assert isinstance(meal, dict)
        assert "ingredients" in meal
        assert "instructions" in meal


def test_swap_ingredient_valid(planner_instance):
    """Swapping an existing ingredient should return a new recipe name."""
    # Pick a random meal that contains at least one ingredient
    target_meal = next(iter(planner_instance.meals))
    original_recipe = planner_instance.meals[target_meal]
    assert "ingredients" in original_recipe

    ingredient_to_swap = original_recipe["ingredients"][0]["name"]

    swapped_name = planner_instance.suggest_swap(target_meal, ingredient_to_swap)

    # Swapped name should differ from the original
    assert swapped_name != target_meal
    # Swapped recipe must exist in meals
    assert swapped_name in planner_instance.meals


def test_swap_ingredient_invalid(planner_instance):
    """Attempting to swap a non‑existent ingredient should raise ValueError."""
    target_meal = next(iter(planner_instance.meals))
    with pytest.raises(ValueError, match="Ingredient .* not found"):
        planner_instance.suggest_swap(target_meal, "nonexistent-ingredient")


def test_pantry_updates_after_planning(planner_instance):
    """Planning meals should consume ingredients from the pantry."""
    # Capture initial quantities
    initial_quantities = {
        ing["name"]: ing["quantity"] for ing in planner_instance.pantry_state.get_all()
    }

    planner_instance.plan_week()

    # After planning, quantities should be reduced or unchanged if not used
    post_quantities = {
        ing["name"]: ing["quantity"] for ing in planner_instance.pantry_state.get_all()
    }

    for name, init_qty in initial_quantities.items():
        assert post_quantities[name] <= init_qty


def test_missing_meals_file(tmp_path):
    """Providing a non‑existent meals file should raise FileNotFoundError."""
    ingredients = Path(__file__).parent.parent / "data" / "ingredients.json"
    config = Path(__file__).parent.parent / "config" / "config.yaml"

    with pytest.raises(FileNotFoundError, match="meals file"):
        Planner(
            ingredients_path=ingredients,
            meals_path=tmp_path / "does_not_exist.yaml",
            config_path=config,
        )


def test_missing_ingredients_file(tmp_path):
    """Providing a non‑existent ingredients file should raise FileNotFoundError."""
    meals = Path(__file__).parent.parent / "data" / "meals.yaml"
    config = Path(__file__).parent.parent / "config" / "config.yaml"

    with pytest.raises(FileNotFoundError, match="ingredients file"):
        Planner(
            ingredients_path=tmp_path / "does_not_exist.json",
            meals_path=meals,
            config_path=config,
        )


def test_invalid_config_file(tmp_path):
    """A malformed YAML in the config should raise a YAMLError."""
    ingredients = Path(__file__).parent.parent / "data" / "ingredients.json"
    meals = Path(__file__).parent.parent / "data" / "meals.yaml"

    # Write an invalid YAML file
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("invalid_yaml: :\n  - bad")

    with pytest.raises(yaml.YAMLError):
        Planner(
            ingredients_path=ingredients,
            meals_path=meals,
            config_path=bad_config,
        )


def test_pantry_state_serialization(planner_instance, tmp_path):
    """PantryState should support saving to and loading from JSON."""
    # Save current state
    json_file = tmp_path / "pantry.json"
    planner_instance.pantry_state.save_to_json(json_file)

    # Load into a new PantryState
    loaded_state = PantryState.load_from_json(json_file)

    # States should match
    assert {i["name"]: i for i in planner_instance.pantry_state.get_all()} == {
        i["name"]: i for i in loaded_state.get_all()
    }


def test_meal_recommendation_logic(planner_instance):
    """Meals with higher nutritional value should be prioritized when planning."""
    # Assume config has a 'nutrition_weight' key
    nutrition_weight = planner_instance.config.get("nutrition_weight", 1)

    # Mock a simple scenario: two meals, one high nutrition
    high_nutrition_meal = "HighProteinSalad"
    low_nutrition_meal = "PlainToast"

    # Add mock meals to planner
    planner_instance.meals[high_nutrition_meal] = {
        "ingredients": [{"name": "lettuce", "quantity": 1}],
        "instructions": "Mix",
        "nutrition": {"protein": 20},
    }
    planner_instance.meals[low_nutrition_meal] = {
        "ingredients": [{"name": "bread", "quantity": 2}],
        "instructions": "Toast",
        "nutrition": {"protein": 5},
    }

    # Force plan to use the high nutrition meal
    plan = planner_instance.plan_week()
    assert high_nutrition_meal in plan.values()


def test_cli_command_integration(tmp_path, monkeypatch):
    """Ensure that the CLI command can be invoked programmatically."""
    from cli.command import run

    # Capture stdout
    out_lines = []

    def mock_print(*args, **kwargs):
        out_lines.append(" ".join(map(str, args)))

    monkeypatch.setattr("builtins.print", mock_print)

    # Run a minimal command that plans one day
    result = run(["plan", "--days", "1"])

    assert result == 0
    # At least one line of output should contain 'Meal for'
    assert any("Meal for" in line for line in out_lines)