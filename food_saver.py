\"\"\"
FoodSaver — Food Expiry Tracker
Single-file Flask application (food_saver.py)

Features:
- Add / edit / delete pantry items with name, quantity, purchase date, expiry date, notes.
- List items sorted by days until expiry and grouped (Expired, Urgent (<=3 days), Soon (4-14 days), Later).
- Simple recipe suggestion engine: built-in recipes matched against available ingredients (fuzzy: matches if most ingredients are present).
- Manual trigger to send email reminders for items that are expiring soon (uses SMTP configured via environment variables).
- SQLite DB stored as `food_saver.db` next to the script (override with FOOD_SAVER_DB or --db).
- Quick "seed sample data" mode for testing.

Run:
    pip install -r requirements.txt
    python food_saver.py       # starts the web app on http://127.0.0.1:5000

Optional environment variables for email reminders (if you want to enable):
    EMAIL_SMTP_HOST (e.g. smtp.gmail.com)
    EMAIL_SMTP_PORT (e.g. 587)
    EMAIL_USERNAME
    EMAIL_PASSWORD
    EMAIL_FROM  (optional)
    EMAIL_TO    (comma-separated list)
    FOOD_SAVER_DB (optional, path to sqlite file)
    FOOD_SAVER_SECRET (optional flask secret key)

Manual reminder endpoint (GET) available at /send-reminders

Note: this is a single-file demo app designed for local use and experimentation. It is intentionally lightweight and avoids external dependencies beyond Flask.
\"\"\"

from flask import Flask, request, redirect, url_for, render_template_string, flash, send_file
import sqlite3
from contextlib import closing
from datetime import datetime, date
import os
import smtplib
from email.message import EmailMessage
import argparse
import threading
import time

try:
    base_dir = os.path.abspath(os.path.dirname(__file__))
except NameError:
    # __file__ may not be defined in some environments (interactive shells, certain runners)
    base_dir = os.path.abspath(os.getcwd())
# Allow overriding the DB location with an environment variable or CLI flag.
DB_PATH = os.environ.get('FOOD_SAVER_DB') or os.path.join(base_dir, 'food_saver.db')

app = Flask(__name__)
app.secret_key = os.environ.get('FOOD_SAVER_SECRET', 'dev-secret')

# -----------------------
# Database helpers
# -----------------------

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(seed=False):
    with closing(get_db_connection()) as db:
        c = db.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                qty TEXT DEFAULT '1',
                purchase_date DATE,
                expiry_date DATE,
                notes TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT
            )
        ''')
        db.commit()

        if seed:
            # sample items
            sample_items = [
                ('Milk', '1 L', '2025-08-25', '2025-09-02', '2% lactose-free'),
                ('Eggs', '12', '2025-08-20', '2025-09-03', 'Large'),
                ('Spinach', '1 bag', '2025-08-28', '2025-09-01', 'Baby spinach'),
                ('Tomato', '3', '2025-08-27', '2025-09-05', ''),
                ('Cheddar cheese', '200 g', '2025-07-20', '2025-10-01', ''),
                ('Bread', '1 loaf', '2025-08-29', '2025-09-01', '')
            ]
            for it in sample_items:
                c.execute('INSERT INTO items (name, qty, purchase_date, expiry_date, notes) VALUES (?, ?, ?, ?, ?)', it)

            # sample recipes (very simple)
            sample_recipes = [
                ('Cheesy Scrambled Eggs', 'eggs,cheddar cheese,butter,salt,pepper', 'Beat eggs, melt butter, cook gently, add cheese.'),
                ('Tomato Spinach Salad', 'tomato,spinach,olive oil,salt,pepper', 'Toss chopped tomato with spinach and dressing.'),
                ('French Toast', 'bread,eggs,milk,cinnamon,butter', 'Dip bread in egg-milk mix and fry.'),
            ]
            for r in sample_recipes:
                c.execute('INSERT INTO recipes (name, ingredients, instructions) VALUES (?, ?, ?)', r)
            db.commit()

# -----------------------
# Utility functions
# -----------------------

def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None

def days_until(d):
    if not d:
        return None
    today = date.today()
    return (d - today).days

def categorize(days):
    if days is None:
        return 'unknown'
    if days < 0:
        return 'expired'
    if days <= 3:
        return 'urgent'
    if days <= 14:
        return 'soon'
    return 'later'

# -----------------------
# Recipe matching
# -----------------------

def load_recipes():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, name, ingredients, instructions FROM recipes')
    rows = cur.fetchall()
    conn.close()
    recipes = []
    for r in rows:
        ingredients = [x.strip().lower() for x in r['ingredients'].split(',') if x.strip()]
        recipes.append({'id': r['id'], 'name': r['name'], 'ingredients': ingredients, 'instructions': r['instructions']})
    return recipes

def match_recipes(available_items):
    # available_items: list of ingredient names (lowercased)
    recipes = load_recipes()
    matches = []
    aval_set = set([i.lower() for i in available_items])
    for rec in recipes:
        req = set(rec['ingredients'])
        matched = req & aval_set
        # score = matched / required
        score = len(matched) / max(1, len(req))
        if score >= 0.5:  # threshold: at least half the ingredients
            matches.append((score, rec))
    matches.sort(key=lambda x: x[0], reverse=True)
    return [r for s, r in matches]

# -----------------------
# Routes / Views
# -----------------------

INDEX_HTML = '''
<!doctype html>
<title>FoodSaver — Pantry</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:20px}
.card{border-radius:8px;padding:12px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}
.grid{display:flex;gap:12px}
.left{flex:2}
.right{flex:1}
.badge{display:inline-block;padding:4px 8px;border-radius:999px;font-size:0.9em}
.badge.expired{background:#ffd6d6}
.badge.urgent{background:#ffecc2}
.badge.soon{background:#fff4d6}
.badge.later{background:#e6fff0}
.item-row{display:flex;justify-content:space-between;align-items:center;padding:8px;border-bottom:1px solid #eee}
.small{font-size:0.9em;color:#555}
.form-row{margin-bottom:8px}
</style>
<h1>FoodSaver — Pantry</h1>
<p class="small">Local-only demo. Add items with expiry dates and find recipes that use things you already have.</p>
<div class="grid">
  <div class="left">
    <div class="card">
      <h3>Items (sorted by days-to-expiry)</h3>
      {% for item in items %}
        <div class="item-row">
          <div>
            <strong>{{item['name']}}</strong> <span class="small">x{{item['qty']}}</span>
            <div class="small">Expiry: {{item['expiry_date'] or '—'}} ({{item['days']}} days)</div>
          </div>
          <div>
            <span class="badge {{item['category']}}">{{item['category']}}</span>
            <a href="/edit/{{item['id']}}">edit</a> • <a href="/delete/{{item['id']}}" onclick="return confirm('Delete?')">delete</a>
          </div>
        </div>
      {% else %}
        <p>No items yet.</p>
      {% endfor %}
    </div>

    <div class="card">
      <h3>Recipe suggestions</h3>
      {% if recipes %}
        {% for r in recipes %}
          <div style="margin-bottom:10px">
            <strong>{{r['name']}}</strong>
            <div class="small">Ingredients: {{r['ingredients']|join(', ')}}</div>
            <div class="small">{{r['instructions']}}</div>
          </div>
        {% endfor %}
      {% else %}
        <p class="small">No recipe suggestions with current ingredients. Add more pantry items or add recipes in the Recipes page.</p>
      {% endif %}
    </div>
  </div>

  <div class="right">
    <div class="card">
      <h3>Add item</h3>
      <form action="/add" method="post">
        <div class="form-row"><input name="name" placeholder="Name (e.g. Milk)" required></div>
        <div class="form-row"><input name="qty" placeholder="Quantity (e.g. 1 L)"></div>
        <div class="form-row"><label class="small">Purchase date</label><input type="date" name="purchase_date"></div>
        <div class="form-row"><label class="small">Expiry date</label><input type="date" name="expiry_date"></div>
        <div class="form-row"><input name="notes" placeholder="Notes"></div>
        <div><button>Add item</button></div>
      </form>
      <p class="small"><a href="/recipes">Manage recipes</a> • <a href="/send-reminders">Send reminders (manual)</a></p>
    </div>

    <div class="card">
      <h3>Quick actions</h3>
      <p class="small"><a href="/export">Export CSV</a></p>
      <form action="/seed" method="post" onsubmit="return confirm('This will add sample items and recipes to your local DB. Continue?')">
        <button type="submit">Seed sample data</button>
      </form>
    </div>
  </div>
</div>
'''

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, name, qty, purchase_date, expiry_date, notes FROM items')
    rows = cur.fetchall()
    conn.close()
    items = []
    available_names = []
    for r in rows:
        ed = parse_date(r['expiry_date']) if r['expiry_date'] else None
        d = days_until(ed) if ed else None
        cat = categorize(d)
        itm = {'id': r['id'], 'name': r['name'], 'qty': r['qty'], 'purchase_date': r['purchase_date'], 'expiry_date': r['expiry_date'], 'notes': r['notes'], 'days': d if d is not None else '—', 'category': cat}
        items.append(itm)
        available_names.append(r['name'].lower())
    # sort by days (None/— goes to end)
    items.sort(key=lambda x: (9999 if x['days']=='—' else x['days']))
    recipes = match_recipes(available_names)
    return render_template_string(INDEX_HTML, items=items, recipes=recipes)

# -----------------------
# CRUD for items
# -----------------------

@app.route('/add', methods=['POST'])
def add_item():
    name = request.form.get('name').strip()
    qty = request.form.get('qty') or ''
    purchase_date = request.form.get('purchase_date')
    expiry_date = request.form.get('expiry_date')
    notes = request.form.get('notes') or ''
    if not name:
        flash('Name required')
        return redirect(url_for('index'))
    # validate dates
    if purchase_date and not parse_date(purchase_date):
        flash('Invalid purchase date format; use YYYY-MM-DD')
        return redirect(url_for('index'))
    if expiry_date and not parse_date(expiry_date):
        flash('Invalid expiry date format; use YYYY-MM-DD')
        return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO items (name, qty, purchase_date, expiry_date, notes) VALUES (?, ?, ?, ?, ?)', (name, qty, purchase_date, expiry_date, notes))
    conn.commit()
    conn.close()
    flash('Item added')
    return redirect(url_for('index'))

EDIT_HTML = '''
<!doctype html>
<title>Edit item</title>
<h1>Edit {{item['name']}}</h1>
<form method="post">
  <div><label>Name</label><input name="name" value="{{item['name']}}"></div>
  <div><label>Qty</label><input name="qty" value="{{item['qty']}}"></div>
  <div><label>Purchase date</label><input type="date" name="purchase_date" value="{{item['purchase_date']}}"></div>
  <div><label>Expiry date</label><input type="date" name="expiry_date" value="{{item['expiry_date']}}"></div>
  <div><label>Notes</label><input name="notes" value="{{item['notes']}}"></div>
  <div><button>Save</button> <a href="/">Cancel</a></div>
</form>
'''

@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, name, qty, purchase_date, expiry_date, notes FROM items WHERE id=?', (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash('Item not found')
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name').strip()
        qty = request.form.get('qty') or ''
        purchase_date = request.form.get('purchase_date')
        expiry_date = request.form.get('expiry_date')
        notes = request.form.get('notes') or ''
        cur.execute('UPDATE items SET name=?, qty=?, purchase_date=?, expiry_date=?, notes=? WHERE id=?', (name, qty, purchase_date, expiry_date, notes, item_id))
        conn.commit()
        conn.close()
        flash('Saved')
        return redirect(url_for('index'))
    item = dict(row)
    conn.close()
    return render_template_string(EDIT_HTML, item=item)

@app.route('/delete/<int:item_id>')
def delete_item(item_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM items WHERE id=?', (item_id,))
    conn.commit()
    conn.close()
    flash('Deleted')
    return redirect(url_for('index'))

# -----------------------
# Recipes management
# -----------------------

RECIPES_HTML = '''
<!doctype html>
<title>Recipes</title>
<h1>Recipes</h1>
<p><a href="/">Back</a></p>
<form method="post" action="/recipes/add">
  <h3>Add recipe</h3>
  <div><input name="name" placeholder="Recipe name" required></div>
  <div><input name="ingredients" placeholder="Comma-separated ingredients (e.g. eggs, milk, bread)" required></div>
  <div><input name="instructions" placeholder="Short instructions"></div>
  <div><button>Add recipe</button></div>
</form>
<hr>
{% for r in recipes %}
  <div style="margin-bottom:12px">
    <strong>{{r['name']}}</strong>
    <div class="small">Ingredients: {{r['ingredients']}}</div>
    <div class="small">{{r['instructions']}}</div>
    <div><a href="/recipes/delete/{{r['id']}}">Delete</a></div>
  </div>
{% else %}
  <p>No recipes yet.</p>
{% endfor %}
'''

@app.route('/recipes')
def recipes_page():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, name, ingredients, instructions FROM recipes')
    rows = cur.fetchall()
    conn.close()
    recs = [dict(r) for r in rows]
    return render_template_string(RECIPES_HTML, recipes=recs)

@app.route('/recipes/add', methods=['POST'])
def recipes_add():
    name = request.form.get('name')
    ingredients = request.form.get('ingredients')
    instructions = request.form.get('instructions')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO recipes (name, ingredients, instructions) VALUES (?, ?, ?)', (name, ingredients, instructions))
    conn.commit()
    conn.close()
    flash('Recipe added')
    return redirect(url_for('recipes_page'))

@app.route('/recipes/delete/<int:rid>')
def recipes_delete(rid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM recipes WHERE id=?', (rid,))
    conn.commit()
    conn.close()
    flash('Recipe deleted')
    return redirect(url_for('recipes_page'))

# -----------------------
# Export
# -----------------------

@app.route('/export')
def export_csv():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, name, qty, purchase_date, expiry_date, notes FROM items')
    rows = cur.fetchall()
    conn.close()
    import csv
    from io import StringIO, BytesIO
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['id', 'name', 'qty', 'purchase_date', 'expiry_date', 'notes'])
    for r in rows:
        cw.writerow([r['id'], r['name'], r['qty'], r['purchase_date'], r['expiry_date'], r['notes']])
    mem = BytesIO()
    mem.write(si.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, mimetype='text/csv', as_attachment=True, download_name='food_saver_export.csv')

# -----------------------
# Seed sample data
# -----------------------

@app.route('/seed', methods=['POST'])
def seed():
    init_db(seed=True)
    flash('Seeded sample data')
    return redirect(url_for('index'))

# -----------------------
# Reminders (manual trigger)
# -----------------------

def get_items_expiring_within(days_threshold=3):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, name, qty, purchase_date, expiry_date, notes FROM items')
    rows = cur.fetchall()
    conn.close()
    urgent = []
    for r in rows:
        ed = parse_date(r['expiry_date']) if r['expiry_date'] else None
        d = days_until(ed) if ed else None
        if d is not None and d <= days_threshold:
            urgent.append({'id': r['id'], 'name': r['name'], 'qty': r['qty'], 'expiry_date': r['expiry_date'], 'days': d})
    return urgent

def send_email(subject, body, to_addrs):
    host = os.environ.get('EMAIL_SMTP_HOST')
    port = int(os.environ.get('EMAIL_SMTP_PORT', 587))
    user = os.environ.get('EMAIL_USERNAME')
    pw = os.environ.get('EMAIL_PASSWORD')
    from_addr = os.environ.get('EMAIL_FROM') or user
    if not host or not user or not pw or not to_addrs:
        raise RuntimeError('Missing email configuration')
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addrs
    msg.set_content(body)
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)

@app.route('/send-reminders')
def send_reminders():
    to = os.environ.get('EMAIL_TO')
    if not to:
        flash('EMAIL_TO not configured. Set environment variable to enable reminders.')
        return redirect(url_for('index'))
    urgent = get_items_expiring_within(3)
    if not urgent:
        flash('No items expiring within 3 days')
        return redirect(url_for('index'))
    body_lines = ['Items expiring soon:']
    for u in urgent:
        body_lines.append(f"- {u['name']} (in {u['days']} days) — expiry {u['expiry_date']}")
    body = '\n'.join(body_lines)
    try:
        send_email('FoodSaver reminders — items expiring soon', body, to)
        flash('Reminder email sent')
    except Exception as e:
        flash('Failed to send email: ' + str(e))
    return redirect(url_for('index'))

# -----------------------
# CLI / Run
# -----------------------

def start_reminder_scheduler(interval_minutes=60):
    \"\"\"Start a background thread that sends reminders every `interval_minutes` minutes.
    Returns a stop_event that can be used to stop the thread if needed.
    \"\"\"
    stop_event = threading.Event()
    def worker():
        while not stop_event.wait(interval_minutes * 60):
            try:
                to = os.environ.get('EMAIL_TO')
                if not to:
                    # nothing configured; skip until environment is set
                    continue
                urgent = get_items_expiring_within(3)
                if urgent:
                    body_lines = ['Items expiring soon:']
                    for u in urgent:
                        body_lines.append(f"- {u['name']} (in {u['days']} days) — expiry {u['expiry_date']}")
                    send_email('FoodSaver automatic reminders — items expiring soon', '\n'.join(body_lines), to)
            except Exception as e:
                # don't crash the thread; just log
                print('Reminder scheduler error:', e)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return stop_event

def run_tests_quick():
    # Basic sanity tests that exercise the code paths without a browser
    print('Running quick tests...')
    # Create a fresh DB in-memory for testing
    test_db = ':memory:'
    global DB_PATH
    old_db = DB_PATH
    DB_PATH = test_db
    init_db(seed=True)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM items')
    nitems = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM recipes')
    nrec = cur.fetchone()[0]
    assert nitems > 0, 'Seed items missing'
    assert nrec > 0, 'Seed recipes missing'
    print('Seed OK: items=', nitems, 'recipes=', nrec)

    # test matching
    items = ['eggs', 'cheddar cheese', 'bread']
    matches = match_recipes(items)
    assert any('Egg' in r['name'] or 'Eggs' in r['name'] for r in matches), 'Recipe matching failed'
    print('Recipe matching OK')
    DB_PATH = old_db
    print('Quick tests passed')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true', help='Initialize DB (no seed)')
    parser.add_argument('--seed', action='store_true', help='Initialize DB and seed sample data')
    parser.add_argument('--test', action='store_true', help='Run quick internal tests')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--db', help='Explicit path for the SQLite DB (overrides FOOD_SAVER_DB env var)')
    parser.add_argument('--auto-reminders', action='store_true', help='Run background reminder scheduler')
    parser.add_argument('--reminder-interval', type=int, default=60, help='Interval in minutes for automatic reminders')
    args = parser.parse_args()

    # allow CLI --db to override DB_PATH
    if args.db:
        DB_PATH = args.db

    if args.test:
        init_db(seed=True)
        run_tests_quick()
    if args.init:
        init_db(seed=False)
        print('DB initialized at', DB_PATH)
    if args.seed:
        init_db(seed=True)
        print('DB initialized and seeded at', DB_PATH)

    # If requested, start the automatic reminder scheduler. Guard against the Flask reloader
    # starting two copies of the thread by only starting the scheduler in the *actual* run process.
    scheduler_stop = None
    if args.auto_reminders:
        run_scheduler = (not app.debug) or (os.environ.get('WERKZEUG_RUN_MAIN') == 'true')
        if run_scheduler:
            print(f'Starting reminder scheduler (every {args.reminder_interval} minutes)')
            scheduler_stop = start_reminder_scheduler(args.reminder_interval)

    if not (args.init or args.seed or args.test):
        init_db(seed=False)
        try:
            app.run(host=args.host, port=args.port, debug=True)
        finally:
            if scheduler_stop:
                scheduler_stop.set()
