from flask import Flask

app = Flask(__name__)


@app.get("/")
def home():
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hello from MeomoLab</title>
  </head>
  <body>
    <h1>Hello from <strong>MeomoLab</strong></h1>
    <a href="/about">About</a>
  </body>
</html>"""

@app.route("/about")
def about():
    return "<p>Your 150 words here.</p>"
