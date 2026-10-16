"""Intent recognition, kept separate from response generation.

classify() looks at the (spell-corrected) message, the extracted entities and the conversation state, and returns
(intent, confidence). Confidence below CLARIFY_BELOW means "ask a short clarifying question" rather than guess.
Rules are explicit regular expressions, ordered from most to least specific; nothing is learned or hidden.
"""
from __future__ import annotations

import re

CLARIFY_BELOW = 0.5

INTENT_LABELS = {
    "greet": "Greeting", "help": "What I can do", "reset": "Start a new trip", "undo": "Undo last change", "explain": "Explain a recommendation",
    "compare": "Compare destinations", "stay": "Find accommodation", "stay_cheaper": "Find cheaper accommodation", "transport": "Transport options",
    "route": "Route and travel time", "weather": "Weather and best season", "activities": "Things to do", "cheaper": "Lower the cost",
    "modify": "Change the itinerary", "cost": "Budget breakdown", "plan": "Build an itinerary", "details": "About a destination",
    "recommend": "Recommend destinations", "apply": "Apply an option", "general": "General travel question", "unknown_place": "Place not in my dataset", "ask_where": "Plan a trip", "clarify": "Need a little more detail",
}

STAY = re.compile(r"\b(hotels?|inns?|resorts?|accommodations?|accommodation|lodging|lodges?|homestays?|hostels?|guest ?houses?|villas?|b&b|stays?)\b|"
                  r"\bwhere (?:should|can|do|could|would) (?:i|we) stay\b|\bplaces? to stay\b|\bsomewhere to stay\b|\bto stay (?:in|at|near)\b|\b[1-5][- ]?stars?\b|\b(?:three|four|five)[- ]stars?\b")
STAY_NOUN_ONLY = re.compile(r"\b(hotels?|inns?|resorts?|accommodations?|lodging|homestays?|hostels?|guest ?houses?|villas?|places? to stay|where (?:should|can|do) (?:i|we) stay|[1-5][- ]?stars?|(?:three|four|five)[- ]stars?)\b")
PLAN_VERB = re.compile(r"\b(plan|planning|itinerary|itineraries|build|create|schedule|organi[sz]e|put together|design|draft|prepare|generate)\b")
CHANGE_CUE = re.compile(r"\b(instead|changed? my mind|make it|switch(?:ing)? to|change (?:it |the destination |destination )?to|how about|what about|go (?:with|for)|same (?:trip|budget|plan)|rather|actually|let'?s (?:do|go)|try)\b")
STAY_PREF_KEYS = ("price_pref", "stars", "stay_type", "amenities", "max_price", "accommodation", "near_phrase")
TRIP_WORD = re.compile(r"\b(trip|holiday|vacation|getaway|tour|break|weekend)\b")
TRANSPORT = re.compile(r"\bhow (?:can|do|should|could|would) (?:i|we) (?:get|go|travel|reach)\b|\bhow to (?:get|reach|go|travel)\b|\b(?:get|getting|reach|reaching|travel|travelling|traveling) (?:to|from)\b|"
                       r"\btransport(?:ation)?\b|\btravel options?\b|\bways? to (?:get|reach|travel|go)\b|\b(?:bus|train|flight|flights|cab|taxi)(?:es|s)?\b(?!.*\b(?:plan|itinerary)\b)|\bconnect(?:ions?|ivity)\b|\bfares?\b")
ROUTE = re.compile(r"\bhow (?:far|long)\b|\bdistance\b|\btravel time\b|\bhow many hours\b|\bjourney time\b|\broute\b|\bshortest (?:way|path|route)\b|\bfastest (?:way|route)\b")
WEATHER = re.compile(r"\bweather\b|\bforecast\b|\btemperatures?\b|\bclimate\b|\bhow (?:hot|cold|warm|cool)\b|\bbest (?:time|season|month|months)\b|\bwhen (?:should|can|is|to|do) (?:i|we|the)?\s*(?:best )?(?:visit|go|travel)\b|"
                     r"\bwhat season\b|\b(?:rain|raining|snow|snowing)\b|\bseason\b(?=.*\?)")
ACTIVITIES = re.compile(r"\bthings to (?:do|see)\b|\bactivit(?:y|ies)\b|\battractions?\b|\bplaces? to (?:visit|see|explore)\b|\bwhat to (?:do|see)\b|\bwhat can (?:i|we) (?:do|see)\b|\bsightseeing\b|\bsights\b|"
                        r"\bsee (?:in|there|around)\b|\bvisit (?:in|there)\b|\bspots?\b|\bto do (?:there|here|in)\b|\bexplore\b|\bworth (?:seeing|visiting)\b|\bmust[- ](?:see|visit)\b|\bpopular\b")
CHEAPER = re.compile(r"\b(cheaper|cheap|reduce (?:the |my )?(?:total )?cost|reduce (?:the )?(?:price|budget)|save money|too expensive|too pricey|too costly|lower (?:the |my )?(?:total )?(?:cost|price)|cut costs?|make it affordable|less expensive|more affordable|pricey|costly|over budget|bring (?:the )?cost down)\b")
TRIP_REF = re.compile(r"\b(trip|plan|itinerary|schedule|whole|entire|everything|overall|total|journey|holiday)\b")
STAY_REF = re.compile(r"\b(those|them|these|they|that|it|ones?|hotels?|options?|places?|stays?|accommodations?)\b")
MODIFY_VERBS = re.compile(r"\b(add|more|include|replace|change|remove|skip|only|instead|swap|switch|upgrade|downgrade|drop|cancel|shorten|extend|slower|faster|relaxed|less)\b")
HELP = re.compile(r"\bwhat can you do\b|\bhow does this work\b|\bwho are you\b|^(?:can you |could you )?help(?: me)?[?.! ]*$|^help\b[?.! ]*$|\bwhat do you do\b|\bwhat are you\b|\bhow can you help\b")
GENERAL_Q = re.compile(r"^(?:what|why|how|is|are|can|could|do|does|should|which|who|where|when|tell me|any)\b")
TRAVEL_WORDS = re.compile(r"\b(travel|trip|visit|tourist|tourism|holiday|vacation|safe|safety|visa|pack|packing|luggage|insurance|currency|language|food|cuisine|culture|festival|shopping|nightlife)\b")


def classify(text: str, ent: dict, state: dict) -> tuple[str, float]:
    t = text.lower().strip()
    has_plan = bool(state.get("plan"))
    shown = state.get("shown")
    n_dest = len(ent.get("destinations", []))
    focus = state.get("focus")

    if re.fullmatch(r"(hi|hello|hey|namaste|hiya|good (morning|afternoon|evening))[!. ]*", t):
        return "greet", 0.99
    if re.search(r"\b(start over|new trip|reset|clear everything|begin again|start again|start fresh)\b", t):
        return "reset", 0.97
    if re.search(r"\b(undo|go back|revert|previous version|previous plan|restore the previous)\b", t):
        return "undo", 0.95
    if HELP.search(t):
        return "help", 0.95
    if re.search(r"\bwhy\b.*\b(recommend|suggest|pick|choose|chose|rank)|\bhow did you (pick|choose|rank)|\bwhy (not|is)\b", t) or re.search(r"^why\b", t):
        return "explain", 0.9
    if re.search(r"\bcompare\b", t) and n_dest < 2:
        if re.search(r"\b(transport|travel options?|ways? to (?:travel|get|reach|go)|buses|bus|train|trains|flights?|fares?)\b", t):
            return "transport", 0.9
        if STAY.search(t):
            return "stay", 0.9
    if re.search(r"\bcompare\b|\bvs\.?\b|\bversus\b|\bdifference between\b|\bwhich is better\b|\bbetter,? .* or\b", t) and (n_dest >= 2 or (n_dest == 1 and focus) or "compare" in t):
        return "compare", 0.92

    # follow-ups that refer to what was just displayed ("those are too expensive"); a fresh search that names a place/landmark/type is NOT a follow-up
    fresh = bool(ent.get("near_phrase") or ent.get("destinations") or ent.get("stars") or ent.get("stay_type") or ent.get("amenities") or ent.get("near_plan"))
    if shown == "stays" and CHEAPER.search(t) and not TRIP_REF.search(t) and not fresh:
        return "stay_cheaper", 0.9
    # accommodation follow-up: "show luxury options instead", "what about hostels", "in Munnar instead" (keeps the stay context, changes what was asked)
    stay_pref = any(k in ent for k in STAY_PREF_KEYS)
    other_topic = WEATHER.search(t) or TRANSPORT.search(t) or ACTIVITIES.search(t) or ROUTE.search(t) or PLAN_VERB.search(t) or re.search(r"\b(trip|itinerary|same|changed my mind)\b", t)
    trip_edit = has_plan and re.search(r"changed? my mind|\bmake it\b|same (?:trip|budget|plan)|switch(?:ing)? to|change (?:it |the destination |destination )?to", t)
    if shown == "stays" and (stay_pref or n_dest == 1) and not other_topic and not trip_edit and not STAY.search(t):
        return "stay", 0.88
    # editing an existing itinerary beats a fresh search ("switch to a hostel", "replace trekking with sightseeing")
    if has_plan and re.search(r"\b(switch|change|upgrade|downgrade|swap|use|go for|move to)\b.*\b(hostel|homestay|hotel|budget|midrange|mid-range|premium|luxury|train|bus|flight|car)\b", t) and not STAY_NOUN_ONLY.search(t.replace("hotel", "")):
        return "modify", 0.9

    # accommodation search
    if STAY.search(t) and not (PLAN_VERB.search(t) and not re.search(r"\b(find|show|suggest|recommend|list|give me|where should|search|look)\b", t)):
        return "stay", 0.95

    if WEATHER.search(t) and not PLAN_VERB.search(t):
        return "weather", 0.9
    if ROUTE.search(t) and (n_dest or ent.get("origin") or focus):
        return "route", 0.88
    if TRANSPORT.search(t) and not PLAN_VERB.search(t) and (n_dest or ent.get("origin") or focus or state.get("prefs", {}).get("origin")):
        return "transport", 0.9
    if ACTIVITIES.search(t) and not PLAN_VERB.search(t) and "exclude_activities" not in ent:
        return "activities", 0.9

    # changing the destination of the current trip ("actually make it X", "what about X instead"): re-plan with the other constraints kept
    if n_dest == 1 and (has_plan or state.get("prefs", {}).get("destination")) and CHANGE_CUE.search(t) and not re.search(r"\b(weather|hotel|hotels|stay|attractions?|things to do)\b", t):
        return "plan", 0.86
    if CHEAPER.search(t):
        return "cheaper", 0.9
    if not has_plan and "exclude_activities" in ent and focus:
        return "modify", 0.8
    if has_plan and ("budget" in ent or "duration_days" in ent or "exclude_activities" in ent or "pace" in ent or "accommodation" in ent or "transport" in ent or MODIFY_VERBS.search(t)):
        return "modify", 0.85
    if re.search(r"\b(how much|total cost|cost summary|what will it cost|breakdown|budget breakdown|cost breakdown)\b", t):
        return "cost", 0.9
    if PLAN_VERB.search(t) or re.search(r"\b(go with|choose|select|let'?s do|i'?ll take|book)\b", t):
        if n_dest or focus or state.get("last_ranked") or "duration_days" in ent or TRIP_WORD.search(t):
            return "plan", 0.88
    if PLAN_VERB.search(t) and not (STAY.search(t) or TRANSPORT.search(t)):
        return "plan", 0.7
    if n_dest and TRIP_WORD.search(t) and not re.search(r"\bwhere\b|\brecommend\b|\bsuggest\b", t):
        return "plan", 0.75
    if re.search(r"\b(tell me about|what is|what'?s in|about|describe|overview)\b", t) and n_dest:
        return "details", 0.85
    if GENERAL_Q.search(t) and re.search(r"\b(visa|passport|safe|safety|pack|packing|luggage|insurance|currency|vaccin\w*|tipping|sim card|plug|permit)\b", t):
        return "general", 0.7
    if any(k in ent for k in ("budget", "duration_days", "climate", "interests", "season", "travellers", "travel_style", "origin", "transport", "accommodation", "pace")) \
            or re.search(r"\b(recommend|suggest|where|somewhere|destination|destinations|trip|holiday|vacation|getaway|travel)\b", t):
        return "recommend", 0.8
    if n_dest:
        return "details", 0.7
    if GENERAL_Q.search(t) and TRAVEL_WORDS.search(t):
        return "general", 0.6
    return "clarify", 0.2
