import datetime
import jwt
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from peewee import *
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------
# CONFIG
# -----------------------------
SECRET_KEY = "super-secret-key-change-this"
DATABASE = "counter.db"

app = Flask(__name__)
CORS(app)  # <-- FIXED: allow frontend access

# Enable logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

db = SqliteDatabase(DATABASE)


# -----------------------------
# MODELS
# -----------------------------
class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    email = CharField(unique=True)
    password_hash = CharField()


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
    logging.debug(f"Creating token for user_id={user_id}")
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    logging.debug(f"Token created: {token}")
    return token


def get_user_from_token():
    auth = request.headers.get("Authorization", "")
    logging.debug(f"Authorization header: {auth}")

    if not auth.startswith("Bearer "):
        logging.warning("Missing or invalid Authorization header.")
        return None

    token = auth.split(" ", 1)[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        logging.debug(f"Decoded JWT payload: {payload}")
        user = User.get_or_none(User.id == payload["user_id"])
        logging.debug(f"User from token: {user}")
        return user
    except Exception as e:
        logging.error(f"Token decode error: {e}")
        return None


# -----------------------------
# ROUTES
# -----------------------------
@app.post("/signup")
def signup():
    logging.info("Signup request received.")
    data = request.json
    logging.debug(f"Signup payload: {data}")

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        logging.warning("Signup missing email or password.")
        return jsonify({"error": "Missing email or password"}), 400

    if User.get_or_none(User.email == email):
        logging.warning(f"Signup failed: email already exists ({email})")
        return jsonify({"error": "Email already exists"}), 400

    user = User.create(
        email=email,
        password_hash=generate_password_hash(password)
    )
    Counter.create(user=user, count=0)

    logging.info(f"New user created: {email}")
    return jsonify({"message": "Account created"}), 200


@app.post("/login")
def login():
    logging.info("Login request received.")
    data = request.json
    logging.debug(f"Login payload: {data}")

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.get_or_none(User.email == email)
    if not user:
        logging.warning(f"Login failed: user not found ({email})")
        return jsonify({"error": "Invalid credentials"}), 401

    if not check_password_hash(user.password_hash, password):
        logging.warning(f"Login failed: wrong password ({email})")
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(user.id)
    logging.info(f"User logged in: {email}")

    return jsonify({"token": token, "email": user.email}), 200


@app.get("/session")
def session_check():
    logging.info("Session check request received.")
    user = get_user_from_token()

    if not user:
        logging.info("Session check: not logged in.")
        return jsonify({"logged_in": False}), 200

    logging.info(f"Session check: logged in as {user.email}")
    return jsonify({"logged_in": True, "email": user.email}), 200


@app.get("/counter")
def get_counter():
    logging.info("Counter GET request received.")
    user = get_user_from_token()

    if not user:
        logging.warning("Unauthorized counter GET.")
        return jsonify({"error": "Unauthorized"}), 401

    counter = Counter.get(Counter.user == user)
    logging.debug(f"Counter value for {user.email}: {counter.count}")

    return jsonify({"count": counter.count}), 200


@app.post("/counter")
def increment_counter():
    logging.info("Counter POST (increment) request received.")
    user = get_user_from_token()

    if not user:
        logging.warning("Unauthorized counter POST.")
        return jsonify({"error": "Unauthorized"}), 401

    counter = Counter.get(Counter.user == user)
    counter.count += 1
    counter.save()

    logging.info(f"Counter incremented for {user.email}: {counter.count}")
    return jsonify({"count": counter.count}), 200


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    logging.info("Starting Flask server on https://flask0001app00remote00repository.onrender.com")
    app.run(debug=True)
