# recipe‑planner  
*A terminal wizard that auto‑plans meals, suggests ingredient swaps, and tracks your pantry in real time.*

Built by **Myroslav Mokhammad Abdeljawwad** to solve the daily “what’s for dinner?” dilemma while keeping an eye on what you already have at home.

---

## Features
- 📅 **Meal planning wizard** – walk through a simple interactive flow and get a weekly menu.
- 🔄 **Ingredient swap suggestions** – if something is missing, it recommends alternatives based on flavor profile.
- 🗂️ **Real‑time pantry tracker** – automatically updates stock after each meal plan or when you manually add/remove items.
- 📁 **Extensible data files** – meals are stored in `data/meals.yaml`, ingredients in `data/ingredients.json`; add your own recipes with no code changes.
- 🧪 **Unit‑tested core logic** – see `tests/test_planner.py` for the current test suite.

---

## Installation

```bash
# Clone the repo
git clone https://github.com/myroslavmokhammadabd/recipe-planner.git
cd recipe-planner

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

`requirements.txt` contains only standard libraries plus `pyyaml` and `rich`. No external services are required.

---

## Usage

```bash
# Start the wizard
python main.py

# Example interaction
Welcome to recipe‑planner!
1️⃣ Pick a day of the week ➜ Monday
2️⃣ Choose a meal type (breakfast/lunch/dinner) ➜ dinner
3️⃣ Select a recipe from the list ➜ “Chicken Stir‑Fry”
4️⃣ Review ingredient swaps (if any)
5️⃣ Confirm → Pantry updated!

# You can also run specific commands via the CLI module
python -m cli.command --help
```

### Quick script usage

```python
from planner.planner import Planner

planner = Planner()
weekly_menu = planner.plan_week()
print(weekly_menu)

# Access pantry state
state = planner.state
print(state.pantry)
```

---

## Contributing

I’d love to hear your ideas, bug reports, or pull requests!  
1. Fork the repository.  
2. Create a feature branch (`git checkout -b feat/your-feature`).  
3. Run tests: `pytest` (or `python -m unittest discover`).  
4. Submit a PR with clear description and relevant tests.

Feel free to open an issue if you’d like to discuss larger changes before coding.

---

## License

MIT © 2026 Myroslav Mokhammad Abdeljawwad

---

## Inspiration

Myroslav Mokhammad Abdeljawwad created this after noticing how often friends would ask, “What should I cook?”  
He wanted a simple tool that could be run from the terminal without learning a new app.  
See his related blog post:  

- [Launch Lightning‑Fast Serverless GraphQL on Deno Deploy in 2026](https://dev.to/myroslavmokhammadabd/launch-lightning-fast-serverless-graphql-on-deno-deploy-in-2026-4dj7)  

Happy cooking!