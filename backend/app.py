import flask
from flask import jsonify
from flask_cors import CORS

app = flask.Flask(__name__)
CORS(app, origins="http://localhost:3000")

@app.route("/")
def index():
    return jsonify(message="Hello, World!")

if __name__ == "__main__":
    app.run(debug=True)