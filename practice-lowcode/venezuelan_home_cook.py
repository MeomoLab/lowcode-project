import os
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template_string, request, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "recipes-photos"
DATABASE = BASE_DIR / "recipes.sqlite3"
MAX_PHOTO_BYTES = 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError("Set the SECRET_KEY environment variable before starting the app.")
app.config["SECRET_KEY"] = secret_key
# Leave room for multipart form fields. The photo itself is still limited to 1 MB
# in the route below, where a field-specific message can be shown.
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
UPLOAD_DIR.mkdir(exist_ok=True)

PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Venezuelan Home Cooks</title>
  <style>
    :root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#29251f;background:#faf7f1;line-height:1.5}
    *{box-sizing:border-box}body{margin:0}header{background:#722f24;color:#fff;padding:2rem max(1rem,calc((100% - 900px)/2))}
    h1{margin:0;font-size:clamp(1.8rem,5vw,2.6rem)}header p{margin:.35rem 0 0;color:#f7e6dc}
    main{max-width:900px;margin:2rem auto;padding:0 1rem}.panel,.recipe{background:#fff;border:1px solid #e7dfd5;border-radius:14px;padding:1.25rem;margin-bottom:1.25rem;box-shadow:0 3px 12px #3925170a}
    h2{margin:.1rem 0 1rem;color:#722f24}.field{margin:1rem 0}label{display:block;font-weight:650;margin-bottom:.3rem}
    input,textarea,button{font:inherit}input[type=text],textarea{width:100%;padding:.7rem;border:1px solid #aaa095;border-radius:8px;background:#fff}
    textarea{min-height:110px;resize:vertical}.hint{color:#655e56;font-size:.92rem}.ingredient-row{display:grid;grid-template-columns:1fr 1fr auto;gap:.5rem;margin:.55rem 0}
    button{min-height:46px;border:0;border-radius:8px;background:#722f24;color:#fff;padding:.65rem 1rem;font-weight:700;cursor:pointer}button.secondary{background:#eee5dc;color:#302822}
    .ingredient-row input{min-width:0;padding:.55rem;border:1px solid #aaa095;border-radius:8px}.ingredient-row button{min-height:42px;padding:.45rem .7rem}
    .error{background:#fff0ed;color:#84251c;padding:.7rem;border-radius:8px;margin:.5rem 0}.success{background:#edf5ea;color:#254c24;padding:.7rem;border-radius:8px;margin:.5rem 0}
    .recipe h3{margin:.1rem 0;color:#722f24;font-size:1.35rem}.recipe-meta{color:#655e56}.recipe img{display:block;max-width:100%;max-height:520px;object-fit:contain;margin:1rem 0;border-radius:9px}
    ol,ul{padding-left:1.4rem}.empty{color:#655e56}@media(max-width:560px){.ingredient-row{grid-template-columns:1fr 1fr}.ingredient-row button{grid-column:1/-1}}
  </style>
</head>
<body>
<header><h1>Venezuelan Home Cooks</h1><p>Share the family recipes that keep our tables connected.</p></header>
<main>
  {% with messages = get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="{{ category }}" role="status">{{ message }}</div>{% endfor %}{% endwith %}
  {% for error in errors %}<div class="error" role="alert">{{ error }}</div>{% endfor %}
  <section class="panel" aria-labelledby="share-heading">
    <h2 id="share-heading">Share a family recipe</h2>
    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
      <div class="field"><label for="title">Title</label><input id="title" name="title" type="text" maxlength="100" required value="{{ values.title }}"></div>
      <div class="field"><label>Ingredients and quantities</label><p class="hint">Add up to 50 ingredients. Include a quantity or measurement for every ingredient.</p>
        <div id="ingredients">{% for ingredient,quantity in ingredients %}<div class="ingredient-row"><input name="ingredient" type="text" maxlength="200" placeholder="Ingredient" aria-label="Ingredient" value="{{ ingredient }}"><input name="quantity" type="text" maxlength="100" placeholder="Quantity / measurement" aria-label="Quantity or measurement" value="{{ quantity }}"><button class="secondary remove" type="button" aria-label="Remove ingredient">Remove</button></div>{% endfor %}</div>
        <button class="secondary" id="add-ingredient" type="button">Add ingredient</button>
      </div>
      <div class="field"><label for="steps">Cooking steps</label><textarea id="steps" name="steps" maxlength="2000" required>{{ values.steps }}</textarea><p class="hint">Up to 2,000 characters.</p></div>
      <div class="field"><label for="author">Author name (optional)</label><input id="author" name="author" type="text" maxlength="50" value="{{ values.author }}"></div>
      <div class="field"><label for="photo">Photo (optional, JPG or PNG, maximum 1 MB)</label><input id="photo" name="photo" type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png"><p class="hint" id="photo-status" aria-live="polite">No photo selected.</p><button class="secondary" id="remove-photo" type="button" disabled>Remove selected photo</button><p class="error" id="photo-error" role="alert" hidden></p></div>
      <button type="submit">Share recipe</button>
    </form>
  </section>
  <section aria-labelledby="recipes-heading"><h2 id="recipes-heading">Shared family recipes</h2>
    {% for recipe in recipes %}<article class="recipe"><h3>{{ recipe.title }}</h3><p class="recipe-meta">Shared by {{ recipe.author or 'A home cook' }}</p>
      {% if recipe.photo %}<img src="{{ url_for('photo', filename=recipe.photo) }}" alt="Photo for {{ recipe.title }}">{% endif %}
      <h4>Ingredients</h4><ul>{% for item in recipe.ingredients %}<li>{{ item.quantity }} {{ item.name }}</li>{% endfor %}</ul>
      <h4>Cooking steps</h4><p style="white-space:pre-wrap">{{ recipe.steps }}</p>
    </article>{% else %}<p class="empty">No recipes have been shared yet. Add the first one above.</p>{% endfor %}
  </section>
</main>
<script>
const ingredients = document.getElementById('ingredients');
const photoInput = document.getElementById('photo');
const photoStatus = document.getElementById('photo-status');
const photoError = document.getElementById('photo-error');
const removePhotoButton = document.getElementById('remove-photo');
photoInput.addEventListener('change', () => {
  const file = photoInput.files[0];
  photoError.hidden = true;
  photoError.textContent = '';
  photoStatus.textContent = file ? `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)` : 'No photo selected.';
  removePhotoButton.disabled = !file;
});
removePhotoButton.addEventListener('click', () => {
  photoInput.value = '';
  photoStatus.textContent = 'Photo removed. No photo will be shared.';
  photoError.hidden = true;
  removePhotoButton.disabled = true;
});
document.querySelector('form').addEventListener('submit', event => {
  const file = photoInput.files[0];
  if (file && file.size > 1024 * 1024) {
    event.preventDefault();
    photoError.textContent = 'Photo is too large. The photo field accepts JPG or PNG files up to 1 MB. Remove it or choose a smaller image.';
    photoError.hidden = false;
    photoInput.focus();
  }
});
document.getElementById('add-ingredient').addEventListener('click', () => {
  if (ingredients.children.length >= 50) return;
  const row = document.createElement('div'); row.className = 'ingredient-row';
  row.innerHTML = '<input name="ingredient" type="text" maxlength="200" placeholder="Ingredient" aria-label="Ingredient"><input name="quantity" type="text" maxlength="100" placeholder="Quantity / measurement" aria-label="Quantity or measurement"><button class="secondary remove" type="button" aria-label="Remove ingredient">Remove</button>';
  ingredients.appendChild(row);
});
ingredients.addEventListener('click', event => { if (event.target.matches('.remove') && ingredients.children.length > 1) event.target.parentElement.remove(); });
</script>
</body></html>'''


def connect_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    with connect_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL DEFAULT '',
            steps TEXT NOT NULL,
            photo TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            quantity TEXT NOT NULL
        )""")


def valid_image_signature(data, extension):
    if extension in {"jpg", "jpeg"}:
        return data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9")
    if extension == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR"
    return False


def load_recipes():
    with connect_db() as db:
        rows = db.execute("SELECT id, title, author, steps, photo FROM recipes ORDER BY id DESC").fetchall()
        recipes = []
        for row in rows:
            recipe = dict(row)
            recipe["ingredients"] = [dict(item) for item in db.execute(
                "SELECT name, quantity FROM ingredients WHERE recipe_id = ? ORDER BY id", (row["id"],)
            ).fetchall()]
            recipes.append(recipe)
        return recipes


@app.route("/", methods=["GET", "POST"])
def index():
    errors = []
    if "csrf_token" not in request.cookies:
        csrf_token = secrets.token_urlsafe(32)
    else:
        csrf_token = request.cookies.get("csrf_token", "")
    values = {"title": "", "steps": "", "author": ""}
    ingredients = [("", "")]

    if request.method == "POST":
        submitted_token = request.form.get("csrf_token", "")
        if not csrf_token or not secrets.compare_digest(submitted_token, csrf_token):
            abort(400, description="Invalid CSRF token. Reload the page and try again.")
        values = {key: request.form.get(key, "").strip() for key in ("title", "steps", "author")}
        names = request.form.getlist("ingredient")
        quantities = request.form.getlist("quantity")
        ingredients = list(zip(names[:50], quantities[:50])) or [("", "")]
        if len(names) > 50 or len(quantities) > 50:
            errors.append("A recipe can contain no more than 50 ingredients.")
        if not values["title"] or len(values["title"]) > 100:
            errors.append("Enter a title of no more than 100 characters.")
        if len(values["author"]) > 50:
            errors.append("Author name must be no more than 50 characters.")
        if not values["steps"]:
            errors.append("add cooking steps")
        if len(values["steps"]) > 2000:
            errors.append("Cooking steps must be no more than 2,000 characters.")
        if not names or not any(name.strip() for name in names):
            errors.append("Add at least one ingredient and its quantity.")
        if len(names) != len(quantities):
            errors.append("add a quantity for the ingredient")
        for index, name in enumerate(names):
            quantity = quantities[index] if index < len(quantities) else ""
            if name.strip() and not quantity.strip():
                errors.append("add a quantity for the ingredient")
                break
            if quantity.strip() and not name.strip():
                errors.append("Enter an ingredient for each quantity.")
                break

        photo_file = request.files.get("photo")
        photo_bytes = None
        extension = ""
        if photo_file and photo_file.filename:
            safe_original_name = secure_filename(photo_file.filename)
            extension = Path(safe_original_name).suffix.lower().lstrip(".")
            if extension not in ALLOWED_EXTENSIONS:
                errors.append("Photo must be a JPG or PNG file.")
            else:
                photo_bytes = photo_file.stream.read(MAX_PHOTO_BYTES + 1)
                if len(photo_bytes) > MAX_PHOTO_BYTES:
                    errors.append("Photo must be no larger than 1 MB.")
                elif not valid_image_signature(photo_bytes, extension):
                    errors.append("The photo content does not match a supported JPG or PNG image.")

        normalized = [(name.strip(), quantity.strip()) for name, quantity in zip(names[:50], quantities[:50]) if name.strip()]
        if not errors:
            stored_name = None
            if photo_bytes is not None:
                stored_name = secrets.token_hex(24) + (".jpg" if extension == "jpeg" else "." + extension)
                photo_path = UPLOAD_DIR / stored_name
                with photo_path.open("xb") as image_file:
                    image_file.write(photo_bytes)
            try:
                with connect_db() as db:
                    cursor = db.execute(
                        "INSERT INTO recipes (title, author, steps, photo) VALUES (?, ?, ?, ?)",
                        (values["title"], values["author"], values["steps"], stored_name),
                    )
                    recipe_id = cursor.lastrowid
                    db.executemany(
                        "INSERT INTO ingredients (recipe_id, name, quantity) VALUES (?, ?, ?)",
                        [(recipe_id, name, quantity) for name, quantity in normalized],
                    )
            except Exception:
                if stored_name:
                    (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
                raise
            flash("Your recipe has been shared with everyone who can access this app.", "success")
            response = redirect(url_for("index"), code=303)
            response.set_cookie("csrf_token", csrf_token, httponly=True, samesite="Lax", secure=request.is_secure)
            return response

    response = app.make_response(render_template_string(PAGE, recipes=load_recipes(), errors=errors,
                                                        values=values, ingredients=ingredients, csrf_token=csrf_token))
    response.set_cookie("csrf_token", csrf_token, httponly=True, samesite="Lax", secure=request.is_secure)
    return response


@app.errorhandler(413)
def request_too_large(_error):
    return render_template_string(r'''<!doctype html>
    <html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Upload too large</title><style>body{font:1rem/1.5 system-ui,sans-serif;max-width:38rem;margin:10vh auto;padding:1.25rem;color:#29251f;background:#faf7f1}main{background:white;border:1px solid #e7dfd5;border-radius:14px;padding:1.5rem}h1{color:#722f24}.error{background:#fff0ed;color:#84251c;padding:1rem;border-radius:8px}a{display:inline-block;margin-top:.75rem;background:#722f24;color:white;padding:.7rem 1rem;border-radius:8px;text-decoration:none}</style></head>
    <body><main><h1>Recipe was not submitted</h1><p class="error"><strong>The request is too large.</strong> The photo field is the most likely cause. Photos must be JPG or PNG and no larger than 1 MB.</p><p>Go back, remove the selected photo or choose a smaller one, then submit again.</p><a href="/">Return to the recipe form</a></main></body></html>'''), 413


@app.get("/photos/<path:filename>")
def photo(filename):
    # Only generated opaque names with supported image suffixes are served.
    if not filename.endswith((".jpg", ".jpeg", ".png")) or Path(filename).name != filename:
        abort(404)
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename, max_age=3600, conditional=True)


initialize_db()

if __name__ == "__main__":
    # Flask's development server is local-only by default; debug mode stays off.
    app.run(debug=False)
