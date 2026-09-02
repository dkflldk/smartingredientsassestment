"""LLM integration: turns a list of ingredients into structured recipe data."""
import json
import os
from typing import List

from pydantic import BaseModel, Field, ValidationError
import groq

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


class Nutrition(BaseModel):
    calories: int
    protein_g: float
    carbs_g: float


class Recipe(BaseModel):
    name: str
    ingredients: List[str]
    instructions: List[str]
    cooking_time_minutes: int
    nutrition: Nutrition


class RecipeResponse(BaseModel):
    valid: bool = True
    invalid_ingredients: List[str] = Field(default_factory=list)
    recipes: List[Recipe] = Field(default_factory=list)


class LLMError(Exception):
    """Raised when the LLM call fails or returns an unusable response."""


class InvalidIngredientsError(Exception):
    """Raised when the input contains items that aren't food ingredients."""

    def __init__(self, invalid_items: List[str]):
        self.invalid_items = invalid_items
        items = ", ".join(invalid_items) if invalid_items else "one or more items"
        super().__init__(
            f"These don't look like food ingredients: {items}. Please enter only food ingredients."
        )


_client = None


def get_client() -> groq.Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise LLMError("GROQ_API_KEY is not configured.")
        _client = groq.Groq(api_key=api_key)
    return _client


SYSTEM_PROMPT = (
    "You are a culinary assistant. The user will give you a comma-separated list "
    "of items they claim to have on hand.\n\n"
    "Step 1 - Validate: check whether EVERY item is a real, edible food "
    "ingredient (a protein, vegetable, fruit, grain, dairy product, spice, "
    "condiment, pantry staple, etc). Reject anything that clearly is not food - "
    "objects, brands, electronics, animals not eaten, body parts, places, "
    "abstract words, gibberish, or nonsense. Be reasonably permissive with "
    "unusual-but-real foods and minor spelling mistakes; only reject items that "
    "are clearly not something you would cook or eat.\n\n"
    "If ANY item fails validation: set \"valid\" to false, list every failing "
    "item verbatim in \"invalid_ingredients\", and leave \"recipes\" as an empty "
    "array. Do not generate any recipes in this case.\n\n"
    "If ALL items pass validation: set \"valid\" to true, leave "
    "\"invalid_ingredients\" as an empty array, and propose 2 to 3 distinct "
    "recipes that primarily use those ingredients (common pantry staples such "
    "as salt, pepper, oil, and water may be assumed available even if not "
    "listed). For each recipe, provide clear step-by-step instructions and a "
    "realistic per-serving nutrition estimate.\n\n"
    "Respond with ONLY a JSON object (no prose, no markdown code fences) matching "
    "exactly this shape:\n"
    "{\n"
    '  "valid": boolean,\n'
    '  "invalid_ingredients": ["string", ...],\n'
    '  "recipes": [\n'
    "    {\n"
    '      "name": "string",\n'
    '      "ingredients": ["string", ...],\n'
    '      "instructions": ["string", ...],\n'
    '      "cooking_time_minutes": integer,\n'
    '      "nutrition": {\n'
    '        "calories": integer,\n'
    '        "protein_g": number,\n'
    '        "carbs_g": number\n'
    "      }\n"
    "    }\n"
    "  ]\n"
    "}\n"
    'When "valid" is true, "recipes" must contain 2 to 3 items.'
)


def generate_recipes(ingredients: List[str]) -> dict:
    """Ask the LLM for 2-3 recipes built around the given ingredients."""
    client = get_client()
    ingredients_text = ", ".join(ingredients)

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            max_completion_tokens=4000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Ingredients available: {ingredients_text}"},
            ],
        )
    except groq.RateLimitError as e:
        raise LLMError("The recipe service is rate-limited right now. Please try again shortly.") from e
    except groq.AuthenticationError as e:
        raise LLMError("The recipe service is misconfigured (invalid API key).") from e
    except groq.APIStatusError as e:
        raise LLMError(f"The recipe service returned an error: {e.message}") from e
    except groq.APIConnectionError as e:
        raise LLMError("Could not reach the recipe service. Check your network connection.") from e

    choice = completion.choices[0] if completion.choices else None
    content = choice.message.content if choice and choice.message else None

    if not content:
        raise LLMError("The recipe service did not return any content.")

    try:
        data = json.loads(content)
        parsed = RecipeResponse(**data)
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        raise LLMError("The recipe service returned data that didn't match the expected schema.") from e

    if not parsed.valid:
        raise InvalidIngredientsError(parsed.invalid_ingredients)

    if not parsed.recipes:
        raise LLMError("The recipe service did not return any recipes. Please try again.")

    return {"recipes": [recipe.model_dump() for recipe in parsed.recipes]}
