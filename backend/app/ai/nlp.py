"""Deterministic NLP pipeline: normalisation -> entity extraction -> intent recognition.

No LLM required. Pattern lexicons are explicit and inspectable. An optional LLM could be
layered on top, but nothing here depends on it.
"""
from __future__ import annotations

import re
from datetime import date

import difflib

from .data_loader import Dataset, DEST_ALIASES, ORIGIN_ALIASES

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a": 1, "couple of": 2}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

INTEREST_LEX = {
    "nature": ["nature", "wildlife", "forest", "greenery", "waterfall", "waterfalls", "scenic"],
    "mountains": ["mountain", "mountains", "hill station", "hill stations", "hills", "himalaya", "himalayan"],
    "beaches": ["beach", "beaches", "sea", "coast", "seaside"],
    "adventure": ["adventure", "trek", "trekking", "hiking", "rafting", "paragliding", "thrill"],
    "historical": ["history", "historical", "monument", "monuments", "fort", "forts", "palace", "palaces", "heritage sites"],
    "culture": ["culture", "cultural", "heritage", "temple", "temples", "spiritual", "traditions"],
    "food": ["food", "cuisine", "foodie", "street food", "local food", "eat"],
    "shopping": ["shopping", "markets", "bazaar", "handicrafts"],
    "photography": ["photography", "photos", "photogenic", "sightseeing", "sunset", "sunrise", "views"],
    "wellness": ["relax", "relaxing", "relaxation", "wellness", "spa", "yoga", "peaceful", "calm", "quiet"],
}
EXCLUDE_LEX = {"trekking": ["trek", "trekking", "hiking", "hike", "climb", "climbing"], "rafting": ["rafting"], "shopping": ["shopping"],
               "boat": ["boating", "boat"], "temple": ["temple", "temples"], "adventure": ["adventure"], "museum": ["museum", "museums"]}
MODE_LEX = {"train": ["train", "rail", "railway"], "bus": ["bus", "buses"], "flight": ["flight", "fly", "plane", "air"], "car": ["car", "taxi", "cab", "drive", "driving"]}
TIER_LEX = {"hostel": ["hostel", "dorm", "backpacker"], "budget": ["budget hotel", "cheap hotel", "cheap stay"], "homestay": ["homestay", "home stay"],
            "midrange": ["mid-range", "midrange", "mid range", "3-star", "three star"], "premium": ["luxury", "premium", "5-star", "five star", "resort"]}
CLIMATE_LEX = {"cold": ["cold", "snow", "snowy", "freezing", "chilly"], "cool": ["cool", "pleasant", "cooler"], "mild": ["mild", "moderate weather"],
               "warm": ["warm"], "hot": ["hot", "sunny hot"]}
SEASON_LEX = {"winter": ["winter"], "summer": ["summer"], "monsoon": ["monsoon", "rainy", "rains"], "post-monsoon": ["post-monsoon", "post monsoon", "autumn", "fall"]}


def _has(text: str, words: list[str]) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text) for w in words)


def _num(tok: str) -> int | None:
    tok = tok.replace(",", "")
    if tok.isdigit():
        return int(tok)
    return NUM_WORDS.get(tok)


def extract_budget(t: str) -> float | None:
    for pat in [r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k|thousand|lakh|lakhs)?", r"([\d,]+(?:\.\d+)?)\s*(k|thousand|lakh|lakhs)\b(?!\s*(?:days?|nights?))",
                r"(?:under|below|within|upto|up to|budget of|budget is|budget around|around|about)\s*([\d,]{4,})\s*()"]:
        m = re.search(pat, t)
        if m:
            v = float(m.group(1).replace(",", ""))
            suf = (m.group(2) or "").strip()
            v *= {"k": 1e3, "thousand": 1e3, "lakh": 1e5, "lakhs": 1e5}.get(suf, 1)
            if v >= 500:
                return v
    m = re.search(r"budget[^\d]{0,15}([\d,]{3,})", t)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def extract_duration(t: str) -> int | None:
    m = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?(?:day|days|night|nights)", t)
    if m:
        n = _num(m.group(1))
        if n:
            return n + (0 if "day" in m.group(0) else 1)
    if "weekend" in t:
        return 2
    if re.search(r"\b(a|one) week\b|\bweek-?long\b", t):
        return 7
    if "long weekend" in t:
        return 3
    return None


def extract_travellers(t: str) -> tuple[int | None, dict]:
    flags: dict = {}
    n = None
    m = re.search(r"(\d+|two|three|four|five|six)\s*(?:people|persons|travellers|travelers|adults|of us|pax)", t) or re.search(r"\bfor\s+(\d+|two|three|four|five|six)\b(?!\s*(?:days|nights|k|thousand))", t)
    if m:
        n = _num(m.group(1))
    if re.search(r"\b(solo|alone|by myself|just me)\b", t):
        n, flags["travel_style"] = 1, "solo"
    if re.search(r"\b(couple|partner|wife|husband|girlfriend|boyfriend|honeymoon|spouse)\b", t):
        n, flags["travel_style"] = n or 2, "couple"
    if re.search(r"\bfriends\b", t):
        flags["travel_style"] = "friends"
    if re.search(r"\b(family|kids|children|child|toddler)\b", t):
        flags["travel_style"] = "family"
        if re.search(r"\b(kids|children|child|toddler)\b", t):
            flags["children"] = True
    if re.search(r"\b(parents|mother|father|grandparents|grandmother|grandfather|elderly|senior|old people|mom|dad)\b", t):
        flags["elderly"] = True; flags.setdefault("travel_style", "family")
    return n, flags


def extract_date(t: str, today: date) -> str | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", t) or None
    mon_first = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    try:
        if m:
            d_, mo = int(m.group(1)), MONTHS[m.group(2)]
        elif mon_first:
            mo, d_ = MONTHS[mon_first.group(1)], int(mon_first.group(2))
        else:
            return None
        y = today.year
        cand = date(y, mo, d_)
        if cand < today:
            cand = date(y + 1, mo, d_)
        return cand.isoformat()
    except ValueError:
        return None


# ------------------------------------------------------------------ accommodation / location entities
STAR_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
STAY_TYPES = {"hostel": ["hostel", "hostels", "dorm"], "homestay": ["homestay", "homestays", "home stay", "home stays"], "resort": ["resort", "resorts"],
              "hotel": ["hotel", "hotels"], "guesthouse": ["guest house", "guesthouse", "guest houses", "lodge", "lodges", "inn", "inns"], "villa": ["villa", "villas"]}
AMENITY_LEX = {"wifi": ["wifi", "wi-fi", "wi fi", "internet"], "breakfast": ["breakfast"], "restaurant": ["restaurant", "on-site dining"], "lift": ["lift", "elevator"],
               "spa": ["spa", "massage"], "garden": ["garden"], "lockers": ["lockers"], "shared kitchen": ["shared kitchen"], "home-cooked meals": ["home-cooked", "home cooked", "homecooked"],
               "hot water": ["hot water", "geyser"]}
PRICE_LOW = r"\b(cheap|cheaper|cheapest|affordable|inexpensive|economical|low[- ]cost|low[- ]budget|pocket[- ]friendly|budget[- ](?:hotels?|stays?|accommodation|options|friendly|places?|rooms?|resorts?)|(?:hotels?|stays?|accommodation|rooms?) on a budget)\b"
PRICE_HIGH = r"\b(luxury|luxurious|luxe|premium|upscale|high[- ]end|top[- ]end|posh|best hotels?|expensive hotels?)\b"
PRICE_MID = r"\b(mid[- ]?range|moderately priced|decent|comfortable)\b"
STOP = {"the", "a", "an", "to", "in", "at", "of", "and", "near", "hotel", "hotels", "stay", "stays", "stop", "there", "here", "for", "with", "some", "good", "best", "nice"}


def extract_stay_entities(t: str) -> dict:
    e: dict = {}
    m = re.search(r"\b([1-5]|one|two|three|four|five)\s*[- ]?\s*(?:stars?|\*)(?![a-z])", t)
    if m:
        e["stars"] = int(m.group(1)) if m.group(1).isdigit() else STAR_WORDS[m.group(1)]
    for k, ws in STAY_TYPES.items():
        if _has(t, ws):
            e["stay_type"] = k; break
    if re.search(PRICE_LOW, t):
        e["price_pref"] = "low"
    elif re.search(PRICE_HIGH, t) or e.get("stars", 0) >= 4:
        e["price_pref"] = "high"
    elif re.search(PRICE_MID, t) or e.get("stars") == 3:
        e["price_pref"] = "mid"
    am = [k for k, ws in AMENITY_LEX.items() if _has(t, ws)]
    if am:
        e["amenities"] = am
    if re.search(r"\b(near|close to|next to|around|beside|nearby|close by|walking distance (?:of|from|to))\b\s+(?:these|the planned|my planned|the itinerary|my itinerary)\b", t) or "near these attractions" in t or "near my itinerary" in t:
        e["near_plan"] = True
    else:
        m = re.search(r"\b(?:near|close to|next to|around|beside|nearby|close by|walking distance (?:of|from|to))\s+(?:the\s+)?([a-z' ]{3,40}?)(?=\s+(?:for|with|under|below|within|that|which|and|from|in)\b|[,.;!?]|$)", t)
        if m:
            e["near_phrase"] = m.group(1).strip()
    m = re.search(r"\b(?:under|below|within|upto|up to|less than|max(?:imum)?(?: of)?|not more than|at most|cheaper than)\s*(?:₹|rs\.?|inr)?\s*([\d,]+)\s*(k|thousand)?(?!\s*(?:days?|nights?|people|persons|stars?))", t)
    if m and m.group(1).replace(",", "").isdigit():
        v = float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        if v >= 100:
            e["max_price"] = v
    m = re.search(r"\b(\d+|one|two|three|four|five|six|seven)\s*nights?\b", t)
    if m:
        n = _num(m.group(1))
        if n:
            e["nights"] = n
    return e


VOCAB = set("""hotel hotels accommodation accommodations resort resorts hostel hostels homestay homestays itinerary recommend recommendation suggest transport transportation
trekking sightseeing cheaper cheapest expensive destination destinations compare comparison activities attractions budget weather temperature luxury affordable relaxed
honeymoon vacation holiday places things restaurant restaurants airport station flights train bus taxi""".split())


def correct_spelling(text: str, ds: Dataset) -> tuple[str, dict]:
    """Conservative typo repair against a small travel vocabulary plus destination/origin names. Returns the repaired text and {typo: fix}."""
    names = {w for d in ds.destinations.values() for w in re.findall(r"[a-z]+", d["name"].lower())}
    names |= {w for o in ds.origins.values() for w in re.findall(r"[a-z]+", o["name"].lower())}
    vocab = VOCAB | names
    pool = sorted(vocab)
    fixes: dict = {}
    out = []
    for tok in re.findall(r"[A-Za-z]+|[^A-Za-z]+", text):
        low = tok.lower()
        if tok.isalpha() and len(tok) >= 4 and low not in vocab:
            cands = [w for w in pool if len(w) >= 4 and w[0] == low[0] and abs(len(w) - len(low)) <= 2 and not (w.startswith(low) or low.startswith(w))]
            best = max(cands, key=lambda w: difflib.SequenceMatcher(None, low, w).ratio(), default=None)
            if best:
                r = difflib.SequenceMatcher(None, low, best).ratio()
                if r >= 0.85 or (sorted(best) == sorted(low) and r >= 0.7):      # close match, or a transposition such as hotles/hotels
                    fixes[tok] = best; tok = best.capitalize() if tok[0].isupper() else best
        out.append(tok)
    return "".join(out), fixes


def resolve_landmark(ds: Dataset, phrase: str, focus: str | None) -> dict | None:
    """Match a phrase such as 'ooty lake' to a real attraction record (never invents a place)."""
    toks = {w for w in re.findall(r"[a-z]+", phrase.lower()) if w not in STOP}
    if not toks:
        return None
    best, best_s = None, 0.0
    for a in ds.attractions.values():
        nt = {w for w in re.findall(r"[a-z]+", a["name"].lower()) if w not in STOP}
        if not nt:
            continue
        overlap = len(nt & toks)
        sc = overlap / len(nt) * (0.5 + 0.5 * overlap / len(toks))
        if focus and a["destination_id"] == focus:
            sc += 0.15
        if sc > best_s:
            best, best_s = a, sc
    return best if best is not None and best_s >= (0.5 if focus and best["destination_id"] == focus else 0.8) else None


def extract_entities(text: str, ds: Dataset, today: date) -> dict:
    t = text.lower().strip()
    e: dict = {}
    b = extract_budget(t)
    fx = re.search(r"\b(dollars?|usd|euros?|eur|pounds?|gbp|yen|aed|dirhams?)\b|[$€£]", t)
    if fx and b:                                  # amounts in other currencies are never read as rupees
        e["ignored_budget"] = f"budget in {fx.group(0).upper()} (only INR is supported)"
    elif b:
        e["budget"] = b
    d = extract_duration(t)
    if d:
        e["duration_days"] = d
    n, flags = extract_travellers(t)
    if n:
        e["travellers"] = n
    e.update(flags)
    for c, ws in CLIMATE_LEX.items():
        if _has(t, ws):
            e["climate"] = c; break
    for s, ws in SEASON_LEX.items():
        if _has(t, ws):
            e["season"] = s; break
    # exclusions first, so "replace trekking with sightseeing" removes trekking and ADDS sightseeing (not adventure)
    ex, excl_spans = [], []
    trig = r"(?:replace|remove|skip|avoid|no|without|don'?t want|dont want|drop|instead of|cancel|not into|get rid of)"
    for m in re.finditer(rf"\b{trig}\s+(?:the |any |all |more )?(.+?)(?=\s+(?:with|by|and|but|so|because|since|for)\b|[,.;!?]|$)", t):
        chunk = m.group(1)
        hit = False
        for k, ws in EXCLUDE_LEX.items():
            if _has(chunk, ws) and k not in ex:
                ex.append(k); hit = True
        if hit:
            excl_spans.append(m.span(1))
    if ex:
        e["exclude_activities"] = ex
    t_int = t
    for st_, en_ in sorted(excl_spans, reverse=True):
        t_int = t_int[:st_] + " " * (en_ - st_) + t_int[en_:]
    ints = [k for k, ws in INTEREST_LEX.items() if _has(t_int, ws)]
    if ints:
        e["interests"] = ints
    modes = [k for k, ws in MODE_LEX.items() if _has(t, ws)]
    if modes:
        e["transport"] = modes
    for tier, ws in TIER_LEX.items():
        if _has(t, ws):
            e["accommodation"] = tier; break
    if re.search(r"\b(relaxed|relaxing|slow|easy|leisurely|not rushed|not exhausting|avoid exhausting|less tiring|laid[- ]back)\b", t):
        e["pace"] = "relaxed"
    elif re.search(r"\b(packed|busy|action[- ]packed|see everything|fast[- ]paced|more activities)\b", t):
        e["pace"] = "packed"
    if re.search(r"\b(wheelchair|mobility|accessible|step[- ]free|disabled)\b", t):
        e["accessibility_required"] = True
    if re.search(r"avoid exhausting|not exhausting|less tiring|nothing strenuous|no strenuous", t):
        e["elderly"] = e.get("elderly", False) or bool(re.search(r"parents|grand|elderly|senior", t))
    iso = extract_date(t, today)
    if iso:
        e["start_date"] = iso
    # origin: "from X", "starting from X", "i'm in X", "leaving X"
    for m in re.finditer(r"(?:from|starting from|starting in|i'?m in|i am in|leaving|departing from|based in)\s+([a-z ]{3,20})", t):
        cand = m.group(1).strip()
        words = cand.split()
        for k in range(min(2, len(words)), 0, -1):
            o = ds.resolve_origin(" ".join(words[:k]))
            if o:
                e["origin"] = o; break
        if "origin" in e:
            break
    if "origin" not in e:                       # "Bengaluru to Mysuru": a known starting city directly followed by "to"
        for name, (kind, oid) in _names_for(ds).items():
            if kind == "origin" and re.search(rf"(?<![a-z]){re.escape(name)}\s+to\s+[a-z]", t):
                e["origin"] = oid; break
    # destinations mentioned (ordered by position)
    found = []
    aliases = DEST_ALIASES
    for d_ in ds.destinations.values():
        for name in {d_["name"].lower(), d_["id"]} | {a for a, v in aliases.items() if v == d_["id"]}:
            for m in re.finditer(rf"(?<![a-z]){re.escape(name)}(?![a-z])", t):
                found.append((m.start(), d_["id"]))
    seen, ordered = set(), []
    for _, did in sorted(found):
        if did not in seen:
            seen.add(did); ordered.append(did)
    if ordered:
        e["destinations"] = ordered
    e.update(extract_stay_entities(t))
    return e


# ---------------------------------------------------------------------- intents
def detect_intent(text: str, ent: dict, state: dict) -> str:
    """Backwards-compatible wrapper: the real classifier lives in intents.py (kept separate from response generation)."""
    from .intents import classify
    return classify(text, ent, state)[0]


_NOT_PLACES = {"india", "south", "north", "east", "west", "central", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
               "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "rs", "inr", "tripwise", "ai", "i", "the", "a"}


def find_unknown_place(message: str, ds: Dataset) -> str | None:
    """A capitalised place after to/in/visit that matches nothing in the dataset (e.g. 'Japan'). Used to say so instead of silently ignoring it."""
    known = set(_NOT_PLACES)
    for d in ds.destinations.values():
        known |= set(re.findall(r"[a-z]+", d["name"].lower())) | {d["id"]}
    for o in ds.origins.values():
        known |= set(re.findall(r"[a-z]+", o["name"].lower())) | {o["id"]}
    for a in ds.attractions.values():
        known |= set(re.findall(r"[a-z]+", a["name"].lower()))
    for m in re.finditer(r"\b(?:to|in|visit|visiting|around|near|at|for|from)\s+((?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?)", message):
        toks = [w.lower() for w in m.group(1).split()]
        if any(w in known for w in toks):
            continue
        if m.group(0).lower().startswith("from "):
            continue
        return m.group(1)
    return None


# ------------------------------------------------------------- places and property names (one general pipeline for any name)
STAY_NOUNS = {w for ws in STAY_TYPES.values() for w in ws} | {"stay", "stays", "accommodation", "accommodations", "lodging", "inn", "suite", "suites", "b&b"}
_GENERIC = set("""a an the and or but of in on at to for from with without near around by about into over under below within upto up more most less least some any all every me my we our you your i it its this that
these those there here them they please kindly can could would should will want need looking look find show give list get suggest recommend search tell what which where when how is are am was be been do does like
good best great nice top cheap cheaper cheapest affordable budget luxury premium expensive options option places place ones one two three four five six seven eight nine ten night nights day days people persons guests
guest person adults adult couple family solo alone friends rooms room bed beds per rs inr rupees rupee k thousand lakh instead also too very really just only available availability booking book price prices rate rates
cost costs tonight tomorrow weekend week month trip star stars rated rating ratings review reviews wifi breakfast spa pool parking garden restaurant lift elevator kitchen lockers hot water geyser internet free clean
comfortable decent mid range midrange luxurious upscale posh lets let ok okay hmm hey hi hello thanks thank yes no yeah sure now again else other another different similar same next first last new old closest nearest
nearby close far walk walking distance km kms hostel dorm homestay home villa lodge guest house guesthouse sample""".split())
_LOC_PREP = {"in", "at", "near", "around", "to", "of", "from", "outside", "towards", "toward"}
_ORIGIN_CUE = r"(?:from|starting from|starting in|leaving|departing from|based in|i'?m in|i am in|living in|currently in)$"
_DEST_CUE = r"(?:to|for|in|at|visit|visiting|into|towards|toward)$"
_NEAR_CUE = r"(?:near|around|close to|next to|outside|nearby|close by)$"


def _names_for(ds: Dataset) -> dict[str, tuple[str, str]]:
    """Every place name/alias in the knowledge base -> (kind, id)."""
    out: dict[str, tuple[str, str]] = {}
    for o in ds.origins.values():
        out[o["name"].lower()] = ("origin", o["id"]); out[o["id"]] = ("origin", o["id"])
    for a, v in ORIGIN_ALIASES.items():
        if v in ds.origins:
            out[a] = ("origin", v)
    for d in ds.destinations.values():
        out[d["name"].lower()] = ("destination", d["id"]); out[d["id"]] = ("destination", d["id"])
    for a, v in DEST_ALIASES.items():
        if v in ds.destinations:
            out[a] = ("destination", v)
    return out


def parse_stay_query(text: str, ds: Dataset, ent: dict) -> dict:
    """Split an accommodation request into a property-name phrase and a location phrase that is not a known place.
    Known places, stay/price/amenity vocabulary, numbers and common words are removed; what is left is classified by its neighbours
    (next to a stay noun -> property name; after in/at/near -> location). Nothing is looked up here and nothing is assumed to exist."""
    t = text.lower()
    toks = [(m.group(0), m.start()) for m in re.finditer(r"[a-z0-9][a-z0-9'&-]*", t)]
    known = set()
    for name in _names_for(ds):
        known |= set(name.split())
    if ent.get("near_phrase"):
        known |= set(ent["near_phrase"].split())
    words = [w for w, _ in toks]
    marked = [(w in _GENERIC or w in STAY_NOUNS or w in known or any(c.isdigit() for c in w) or w in {x for ws in AMENITY_LEX.values() for x in ws}) for w in words]
    runs, i = [], 0
    while i < len(words):
        if marked[i]:
            i += 1; continue
        j = i
        while j < len(words) and not marked[j]:
            j += 1
        runs.append((i, j)); i = j
    name = loc = None
    for a, b in runs:
        if b - a > 4:
            continue
        prev = words[a - 1] if a else ""
        nxt = words[b] if b < len(words) else ""
        phrase = " ".join(words[a:b])
        if prev in STAY_NOUNS or nxt in STAY_NOUNS:
            name = name or phrase
        elif prev in _LOC_PREP:
            loc = loc or phrase
    return dict(name=name, location=loc)


def _name_tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", re.sub(r"\(.*?\)", " ", s.lower()))


def match_stay_name(ds: Dataset, phrase: str | None) -> list[dict]:
    """Records whose name contains every word of the phrase (small typos tolerated). Returns [] when nothing in the dataset matches."""
    q = _name_tokens(phrase or "")
    if not q:
        return []
    hits = []
    for r in ds.accommodation.values():
        rt = _name_tokens(r["name"])
        sc = []
        for w in q:
            best = max((1.0 if w == x else difflib.SequenceMatcher(None, w, x).ratio() for x in rt), default=0)
            sc.append(best if (best == 1.0 or (len(w) >= 5 and best >= 0.82)) else 0)
        if all(sc):
            hits.append((sum(sc) / len(sc), r))
    return [r for _, r in sorted(hits, key=lambda x: -x[0])]


def find_unsupported_place(message: str, ds: Dataset, intent: str, ent: dict, parts: dict | None = None, bare_ok: bool = False) -> dict | None:
    """A place the user asked about that the dataset cannot serve: a city that exists only as a starting point (no attractions/stays),
    or a place the dataset does not know at all. Never resolves to a different place."""
    t = message.lower()
    descriptive = intent in ("stay", "stay_cheaper", "activities", "weather", "details")
    found = []
    dest_names = {n for n, (k, _) in _names_for(ds).items() if k == "destination"}
    for name, (kind, oid) in _names_for(ds).items():
        if kind != "origin" or name in dest_names:
            continue
        for m in re.finditer(rf"(?<![a-z]){re.escape(name)}(?![a-z])", t):
            before = t[:m.start()].rstrip(" ,")
            if re.search(_ORIGIN_CUE, before):
                role = "origin"
            elif re.search(_NEAR_CUE, before):
                role = "near"
            elif re.search(_DEST_CUE, before):
                role = "dest"
            else:
                role = "bare"
            if role == "dest" or (role == "bare" and (descriptive or bare_ok)):
                found.append((m.start(), dict(name=ds.origins[oid]["name"], kind="origin_only", id=oid, lat=ds.origins[oid]["lat"], lon=ds.origins[oid]["lon"])))
    if found:
        return sorted(found, key=lambda x: x[0])[0][1]
    unk = find_unknown_place(message, ds)
    if unk:
        return dict(name=unk, kind="unknown")
    if intent in ("stay", "stay_cheaper") and parts and parts.get("location"):
        return dict(name=parts["location"].title(), kind="unknown")
    return None
