# Smart Recipe Analyzer

Enter a comma-separated list of ingredients and get 2-3 AI-generated recipes,
each with ingredients, step-by-step instructions, cooking time, and a
per-serving nutrition estimate (calories, protein, carbs).

## Project structure

```
axium.test/
├── backend/
│   ├── app.py            # Flask app: serves the frontend + POST /generate endpoint
│   ├── llm.py             # Groq API call + structured-output schema (Pydantic)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html         # Textarea + results container
│   ├── style.css
│   └── script.js          # Client-side validation + fetch call + rendering
└── README.md
```

## Architecture

- **Frontend** is plain HTML/CSS/JS (no build step, no framework). It validates
  that the ingredients field isn't empty before sending a request, POSTs a
  JSON array of ingredients to `/generate`, and renders the returned recipes
  as cards.
- **Backend** is a single Flask app that does two jobs: serves the static
  frontend files, and exposes `POST /generate`, which accepts `{"ingredients":
  [...]}` (a JSON array, or a comma-separated string for flexibility),
  re-validates the list isn't empty server-side, and calls the LLM. On
  success it returns `{"recipes": [...]}`; on failure (bad/missing API key,
  rate limit, network error, malformed LLM output, or any unexpected
  exception) it returns a JSON `{"error": "..."}` body with an appropriate
  4xx/5xx status instead of leaking a stack trace.
- **LLM integration** (`backend/llm.py`) calls the Groq API
  (`client.chat.completions.create`, official `groq` Python SDK) with
  `response_format={"type": "json_object"}` and a system prompt that spells
  out the exact required JSON shape. The returned JSON string is parsed with
  `json.loads` and then validated against a Pydantic schema (`RecipeResponse`
  → `Recipe` → `Nutrition`) — if parsing or validation fails, an `LLMError` is
  raised rather than passing bad data to the frontend. Only on success is the
  validated object serialized back to the frontend.
- Model used is `llama-3.3-70b-versatile` (set via `MODEL` in
  `backend/llm.py`, overridable with the `GROQ_MODEL` env var without a code
  change).

## Setup

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env   # then edit .env and add your GROQ_API_KEY
python app.py
```

Visit `http://localhost:5000`.

## Notes

- No database, auth, or persistence — recipes are generated fresh on each request.
- No additional features beyond what was requested (no saving/favoriting,
  no image generation, no multi-page routing).
