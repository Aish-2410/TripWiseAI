# Algorithms and complexity
Notation: D destinations, A attractions per destination, d days, B beam width (default 40), V/E graph nodes/edges.

## Recommendation (`recommendation.py`)
1. **Hard constraints** filter (O(D)): excluded destinations, no transport option, min days, travel-time share of the trip, budget floor, attraction exclusions, mandatory accessibility. Excluded items are returned with reasons; if nothing survives, relaxation advice is returned.
2. **Weighted score** over six components (interests, budget, climate, season, travel time, duration). Unspecified components are dropped and weights renormalised; missing destination data scores 0.25 and is flagged. Rule adjustments are added with diminishing returns. Deterministic; seeded jitter only if `randomize`. Cost O(D·A).

## Knowledge base and rules
Triple store with provenance and confidence; pattern queries are linear scans over indexed subjects. Rules (R1…R10, R3b, R7, R6) are IF/THEN objects with readable text, evaluated per candidate; ranking rules adjust scores, itinerary rules change planning, budget rules trigger the Guardian.

## Search (`search.py`)
- **BFS**: O(V+E); minimises hops only.
- **A\***: O(E log V) worst case; haversine heuristic is admissible and consistent (checked by `check_heuristic`; results matched Dijkstra in tests) on the modelled graph (edges ≤450 km plus connectivity edges, road factor 1.3).
- **Beam search itinerary** (`itinerary.py`): state = partial day assignment, actions = add an eligible attraction (respecting daily minute limits 330/450/570 and 3/4/5 activity caps by pace, 0.75× time on arrival/departure days, elderly cap), h = optimistic sum of best remaining values. Complexity O(d·B·A·log B). Not guaranteed optimal.

## Budget Guardian (`budget.py`)
Group costing (per-person fares × travellers, per-vehicle × ceil(T/4), per-bed hostel, rooms = ceil(T/capacity), food, fees × T, local km × ₹14, 8% contingency). Optimiser generates moves (cheaper stay, transport, food tier, swap paid→free, drop paid, regroup), ranks by saving, flags moves that violate stated preferences, applies greedily with an activity floor (≤8 steps). Greedy: reports when budget cannot be met.

## Re-planning (`replanning.py`)
Patch preferences → lock activities still valid → beam-fill → optimise if over budget → diff summary; version history in the client enables undo.

## ML (`ml/stravl_pipeline.py`)
Binary classification of yes/no swipes, user-level 80/20 split, profiles from training users only. Held-out ROC-AUC: popularity baseline 0.7036, cosine similarity 0.5798, logistic regression (deployed, JSON coefficients) 0.7235, HistGradientBoosting 0.7301. Gains are modest; the output is informational only.
