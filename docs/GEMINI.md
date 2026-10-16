# Gemini integration (natural-language understanding only)

Gemini reads a message and returns a small, schema-validated interpretation. **It never searches, ranks, prices or plans.** Destinations, stays, transport, budgets, recommendations and itineraries still come from the dataset and the existing algorithms (`chat_services.py`, `planner.py`, `recommendation.py`, `budget.py`), so the knowledge-base and reasoning/explanation features still work and can be demonstrated.

## How it connects (`backend/app/ai/llm.py` -> `chat._respond`)
1. The rule-based parser (`nlp.py`, `intents.py`) runs first, as before.
2. If its intent confidence is below 0.85 (and it is not a greeting, undo, apply-option or an answer to a pending question), one Gemini call interprets the message together with a tiny context (current destination/itinerary, origin, budget, days, travellers). Confident messages never call Gemini.
3. The output is validated by a Pydantic schema, then **grounded and checked**: places must appear in the user's message and are resolved against the destination/origin lists; numbers must be in range and present in the message; currency must be INR; interests/climate/stay types must be in the known vocabularies. Anything else is dropped.
4. Validated values fill only the gaps (`setdefault`): explicit rule-based values are never overwritten, so an explicit destination is never silently replaced. Gemini's intent is used only when the rules are unsure, and only if it makes sense for the state (e.g. "modify" needs an itinerary).
5. The existing handlers do the rest. A place Gemini names that is not in the dataset produces the honest "not in my dataset" reply. The "What I understood" panel shows `Interpreted by: Gemini, checked against the dataset` or `Rule-based parser (Gemini unavailable)`.

## Configure (server-side only)
Copy `.env.example` to `backend/.env` (git-ignored) and set:

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | none | from https://aistudio.google.com/apikey. Missing/placeholder = Gemini off |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | any model your account can use; it was listed with a free tier in Google's docs when this was written, so check your account |
| `GEMINI_TIMEOUT_S` | `15` | per-request timeout in seconds; minimum 10 (the API rejects shorter deadlines), lower values are raised |
| `GEMINI_MAX_RETRIES` | `1` | retries for timeouts / 5xx only (capped at 1) |
| `GEMINI_ENABLED` | `true` | `false` forces the rule-based parser |

Run as usual (`uvicorn app.main:app`); the startup log says whether Gemini is enabled, never the key. `GET /api/meta` reports `chat.llm_enabled`, and the chat page shows the engine label.

## Fallback behaviour
No key, timeout, quota (429), auth (401/403), unknown model (404), 5xx, malformed JSON or schema violation -> the call returns nothing, the rule-based chatbot answers, and the reason is logged server-side (key redacted). 5xx/timeouts retry at most once (only if the first attempt failed within half the timeout, so users never wait for two full deadlines); 429/auth/model errors pause Gemini for 1-10 minutes so chat stays fast. Users never see provider errors or stack traces.

## Security notes
The key is read from the environment at call time, never sent to the browser, never in API responses or logs, and `.env` is git-ignored. The user's message is sent inside `<user_message>` tags with a system instruction that treats it as data; the model has no tools, and its output can only fill the schema. The message and a few trip fields are sent to Google's API (privacy note for deployment).

## Verify manually
`cd backend && PYTHONPATH=. python scripts/gemini_smoke.py` (uses a little quota; prints the model's interpretation and the validated entities, never the key). Automated tests mock the provider and use no quota: `tests/test_gemini_understanding.py`.
