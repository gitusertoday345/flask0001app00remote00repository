import os
import datetime
import logging
import jwt
from flask import Flask, request, jsonify
from flask_cors import CORS
from peewee import *
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

# -----------------------------
# CONFIG
# -----------------------------
#SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
SECRET_KEY = os.environ.get("SECRET_KEY", "fjfFGdfDFdfDFUWYPXNMFJjudGgthjoqyfbcbalfyDHXNBYhabvfc")
DATABASE = "counter.db"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
AVATAR_DIR = os.path.join(STATIC_DIR, "avatars")

os.makedirs(AVATAR_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static")
CORS(app)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

db = SqliteDatabase(DATABASE)


# -----------------------------
# STATIC ROUTE (Fix for Render)
# -----------------------------
@app.route("/static/<path:filename>")
def static_files(filename):
    return app.send_static_file(filename)


# -----------------------------
# MODELS
# -----------------------------
class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    email = CharField(unique=True)
    password_hash = CharField()
    profile_pic = CharField(null=True)


class Counter(BaseModel):
    user = ForeignKeyField(User, backref="counter", unique=True)
    count = IntegerField(default=0)


db.connect()
db.create_tables([User, Counter])
logging.info("Database initialized and tables created.")


# -----------------------------
# AUTH HELPERS
# -----------------------------
def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


def get_user_from_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None

    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return User.get_or_none(User.id == payload["user_id"])
    except Exception as e:
        logging.error(f"Token decode error: {e}")
        return None


# -----------------------------
# ROUTES: AUTH
# -----------------------------
@app.post("/signup")
def signup():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    if User.get_or_none(User.email == email):
        return jsonify({"error": "Email already exists"}), 400

    user = User.create(
        email=email,
        password_hash=generate_password_hash(password)
    )
    Counter.create(user=user, count=0)

    return jsonify({"message": "Account created"}), 200


@app.post("/login")
def login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.get_or_none(User.email == email)
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(user.id)
    return jsonify({
        "token": token,
        "email": user.email,
        "profile_pic": user.profile_pic
    }), 200


@app.get("/session")
def session_check():
    user = get_user_from_token()
    if not user:
        return jsonify({"logged_in": False}), 200

    return jsonify({
        "logged_in": True,
        "email": user.email,
        "profile_pic": user.profile_pic
    }), 200


# -----------------------------
# ROUTES: COUNTER
# -----------------------------
@app.get("/counter")
def get_counter():
    user = get_user_from_token()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    counter = Counter.get(Counter.user == user)
    return jsonify({"count": counter.count}), 200


@app.post("/counter")
def increment_counter():
    user = get_user_from_token()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    counter = Counter.get(Counter.user == user)
    counter.count += 1
    counter.save()

    return jsonify({"count": counter.count}), 200


# -----------------------------
# ROUTES: AVATAR UPLOAD
# -----------------------------
@app.post("/upload-avatar")
def upload_avatar():
    user = get_user_from_token()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    try:
        img = Image.open(file.stream).convert("RGB")
        img = img.resize((40, 40))

        filename = f"user_{user.id}.jpg"
        filepath = os.path.join(AVATAR_DIR, filename)
        img.save(filepath, format="JPEG")

        # FULL URL FIX
        base = request.host_url.rstrip("/")
        url_path = f"{base}/static/avatars/{filename}"

        user.profile_pic = url_path
        user.save()

        return jsonify({"url": url_path}), 200

    except Exception as e:
        logging.error(f"Avatar upload error: {e}")
        return jsonify({"error": "Avatar processing failed"}), 500


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

