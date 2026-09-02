"""Flask backend for the Smart Recipe Analyzer."""
import logging
import os

from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

from llm import InvalidIngredientsError, LLMError, generate_recipes

load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
logger = logging.getLogger(__name__)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def _extract_ingredients(payload):
    """Normalize the request body's `ingredients` field into a clean list of strings.

    Accepts either a JSON array of strings or a single comma-separated string,
    so the frontend has flexibility in how it sends the field.
    """
    raw = payload.get("ingredients")

    if isinstance(raw, list):
        items = [str(item).strip() for item in raw]
    elif isinstance(raw, str):
        items = [item.strip() for item in raw.split(",")]
    else:
        return None

    return [item for item in items if item]


@app.route("/generate", methods=["POST"])
def generate():
    payload = request.get_json(silent=True)

    if payload is None or not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    ingredients = _extract_ingredients(payload)

    if ingredients is None:
        return jsonify(
            {"error": "The 'ingredients' field must be a list of strings or a comma-separated string."}
        ), 400

    if not ingredients:
        return jsonify({"error": "Please provide at least one ingredient."}), 400

    try:
        result = generate_recipes(ingredients)
    except InvalidIngredientsError as e:
        # The user's input itself is the problem, not the LLM/API - a 400,
        # not a 502, and no recipes are generated.
        logger.info("Rejected non-food ingredients: %s", e.invalid_items)
        return jsonify({"error": str(e), "invalid_ingredients": e.invalid_items}), 400
    except LLMError as e:
        # Known, expected failure modes from the LLM layer (bad API key, rate
        # limit, network error, malformed/empty response, etc).
        logger.warning("Recipe generation failed: %s", e)
        return jsonify({"error": str(e)}), 502
    except Exception:
        # Anything unanticipated - never leak internal details to the client.
        logger.exception("Unexpected error while generating recipes")
        return jsonify({"error": "An unexpected error occurred while generating recipes."}), 500

    return jsonify(result), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
