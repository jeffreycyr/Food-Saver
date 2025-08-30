# FoodSaver — Food Expiry Tracker

Single-file Flask app to track pantry items, suggest recipes, and send expiry reminders.

## Quickstart

1. Clone or create a folder and add the files from this project.
2. Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate  # Linux / macOS
.\.venv\Scripts\activate   # Windows PowerShell
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
python food_saver.py
```

Open http://127.0.0.1:5000 in your browser.

## Environment variables

- `FOOD_SAVER_DB` — optional, path to SQLite DB (defaults to `./food_saver.db`).
- `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_TO` — configure to enable email reminders.
- `FOOD_SAVER_SECRET` — optional Flask secret key.

## CLI options

- `--init` — initialize DB without seeding
- `--seed` — initialize DB and seed sample data
- `--test` — run quick internal tests
- `--db <path>` — override DB path
- `--auto-reminders` — start a background reminder scheduler
- `--reminder-interval <minutes>` — interval for automatic reminders

## License

MIT
