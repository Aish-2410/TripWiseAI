"""Build the TripWise AI SAMPLE dataset.

IMPORTANT - provenance
----------------------
Every record produced here is *sample / illustrative* data, authored for the
demonstration from general public knowledge. The external sources named in the
project brief (Kaggle, Wikivoyage, Open Travel Data, Hugging Face) could not be
reached from the build environment, so they were NOT integrated.

* Coordinates are approximate (typically within a few km).
* Entry fees are rounded estimates for Indian residents and may be outdated.
* Accommodation records are FICTIONAL placeholders (names end in "(sample)").
* Transport links are produced by a documented distance model, not from real
  timetables or fares.

Run:  python datasets/build_sample_data.py
Output: datasets/processed/{destinations,attractions,accommodation,transport_links,origins}.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent / "processed"

# --------------------------------------------------------------------------
# Destinations
# tags use the shared interest taxonomy:
#   nature, mountains, beaches, adventure, historical, culture, food,
#   shopping, photography, wellness
# --------------------------------------------------------------------------
DESTINATIONS = [
    dict(id="ooty", name="Ooty", state="Tamil Nadu", region="South", type="hill station", climate="cool",
         lat=11.4102, lon=76.6950, best_seasons=["summer", "winter", "post-monsoon"], min_days=2, max_days=5,
         tags=["nature", "mountains", "photography", "wellness"], accessibility="moderate",
         airport="Coimbatore (CJB)", airport_km=90, railhead="Mettupalayam", railhead_km=45, price_index=1.0,
         wiki="Ooty",
         description="A colonial-era hill station in the Nilgiris known for tea estates, gardens, a heritage mountain railway and cool weather."),
    dict(id="coorg", name="Coorg", state="Karnataka", region="South", type="hill station", climate="cool",
         lat=12.4244, lon=75.7382, best_seasons=["winter", "post-monsoon", "monsoon"], min_days=2, max_days=5,
         tags=["nature", "mountains", "adventure", "food", "photography", "wellness"], accessibility="limited",
         airport="Mangaluru (IXE)", airport_km=135, railhead="Mysuru", railhead_km=120, price_index=1.05,
         wiki="Kodagu_district",
         description="Coffee-plantation country in the Western Ghats with waterfalls, forest walks and a distinctive local cuisine."),
    dict(id="munnar", name="Munnar", state="Kerala", region="South", type="hill station", climate="cool",
         lat=10.0889, lon=77.0595, best_seasons=["winter", "post-monsoon", "monsoon"], min_days=2, max_days=5,
         tags=["nature", "mountains", "photography", "wellness", "adventure"], accessibility="moderate",
         airport="Kochi (COK)", airport_km=110, railhead="Aluva / Ernakulam", railhead_km=105, price_index=1.1,
         wiki="Munnar",
         description="Rolling tea estates, shola forests and high-altitude viewpoints in the Western Ghats of Kerala."),
    dict(id="kodaikanal", name="Kodaikanal", state="Tamil Nadu", region="South", type="hill station", climate="cool",
         lat=10.2381, lon=77.4892, best_seasons=["summer", "post-monsoon", "winter"], min_days=2, max_days=4,
         tags=["nature", "mountains", "photography", "wellness"], accessibility="moderate",
         airport="Madurai (IXM)", airport_km=120, railhead="Kodai Road", railhead_km=80, price_index=0.95,
         wiki="Kodaikanal",
         description="A lake-centred hill station in the Palani Hills with cliffs, pine forests and misty viewpoints."),
    dict(id="mysuru", name="Mysuru", state="Karnataka", region="South", type="heritage city", climate="warm",
         lat=12.2958, lon=76.6394, best_seasons=["winter", "post-monsoon", "monsoon"], min_days=1, max_days=3,
         tags=["historical", "culture", "food", "shopping", "photography"], accessibility="good",
         airport="Mysuru (MYQ) / Bengaluru (BLR)", airport_km=10, railhead="Mysuru Jn", railhead_km=3, price_index=0.9,
         wiki="Mysore",
         description="A royal heritage city built around its illuminated palace, markets, silk and sandalwood crafts."),
    dict(id="hampi", name="Hampi", state="Karnataka", region="South", type="heritage site", climate="hot",
         lat=15.3350, lon=76.4600, best_seasons=["winter", "post-monsoon"], min_days=2, max_days=4,
         tags=["historical", "culture", "photography", "adventure"], accessibility="limited",
         airport="Vidyanagar (VDY)", airport_km=35, railhead="Hosapete", railhead_km=13, price_index=0.85,
         wiki="Hampi",
         description="The ruins of the Vijayanagara capital spread across a boulder-strewn landscape beside the Tungabhadra river."),
    dict(id="goa", name="Goa", state="Goa", region="West", type="beach", climate="warm",
         lat=15.4909, lon=73.8278, best_seasons=["winter", "post-monsoon"], min_days=3, max_days=7,
         tags=["beaches", "food", "culture", "historical", "shopping", "adventure", "wellness"], accessibility="moderate",
         airport="Goa Dabolim (GOI) / Mopa (GOX)", airport_km=30, railhead="Madgaon / Thivim", railhead_km=25, price_index=1.3,
         wiki="Goa",
         description="Coastal state blending Portuguese-era heritage, long beaches, seafood and a relaxed pace."),
    dict(id="pondicherry", name="Pondicherry", state="Puducherry", region="South", type="coastal town", climate="warm",
         lat=11.9416, lon=79.8083, best_seasons=["winter", "post-monsoon"], min_days=2, max_days=4,
         tags=["culture", "food", "beaches", "wellness", "photography", "historical"], accessibility="good",
         airport="Puducherry (PNY) / Chennai (MAA)", airport_km=150, railhead="Villupuram", railhead_km=38, price_index=1.1,
         wiki="Pondicherry",
         description="A former French colony with a walkable colonial quarter, seafront promenade, cafes and spiritual communities."),
    dict(id="jaipur", name="Jaipur", state="Rajasthan", region="North", type="heritage city", climate="hot",
         lat=26.9124, lon=75.7873, best_seasons=["winter", "post-monsoon"], min_days=2, max_days=4,
         tags=["historical", "culture", "shopping", "food", "photography"], accessibility="moderate",
         airport="Jaipur (JAI)", airport_km=12, railhead="Jaipur Jn", railhead_km=3, price_index=1.0,
         wiki="Jaipur",
         description="The 'Pink City': hilltop forts, royal palaces, observatories and bustling bazaars."),
    dict(id="udaipur", name="Udaipur", state="Rajasthan", region="North", type="heritage city", climate="warm",
         lat=24.5854, lon=73.7125, best_seasons=["winter", "post-monsoon", "monsoon"], min_days=2, max_days=4,
         tags=["historical", "culture", "photography", "wellness", "shopping"], accessibility="moderate",
         airport="Udaipur (UDR)", airport_km=22, railhead="Udaipur City", railhead_km=3, price_index=1.15,
         wiki="Udaipur",
         description="A lake-city of palaces and havelis in the Aravalli hills, known for sunset views over Lake Pichola."),
    dict(id="agra", name="Agra", state="Uttar Pradesh", region="North", type="heritage city", climate="hot",
         lat=27.1767, lon=78.0081, best_seasons=["winter", "post-monsoon"], min_days=1, max_days=3,
         tags=["historical", "culture", "photography", "food", "shopping"], accessibility="good",
         airport="Agra (AGR)", airport_km=10, railhead="Agra Cantt", railhead_km=4, price_index=0.9,
         wiki="Agra",
         description="Home to the Taj Mahal and a cluster of Mughal-era monuments along the Yamuna river."),
    dict(id="varanasi", name="Varanasi", state="Uttar Pradesh", region="North", type="spiritual city", climate="hot",
         lat=25.3176, lon=82.9739, best_seasons=["winter", "post-monsoon"], min_days=2, max_days=4,
         tags=["culture", "historical", "photography", "food", "wellness"], accessibility="limited",
         airport="Varanasi (VNS)", airport_km=25, railhead="Varanasi Jn", railhead_km=5, price_index=0.85,
         wiki="Varanasi",
         description="One of the oldest living cities, centred on the ghats of the Ganga with daily rituals and narrow lanes."),
    dict(id="rishikesh", name="Rishikesh", state="Uttarakhand", region="North", type="adventure & spiritual town", climate="mild",
         lat=30.0869, lon=78.2676, best_seasons=["winter", "post-monsoon", "summer"], min_days=2, max_days=5,
         tags=["adventure", "wellness", "culture", "nature", "mountains"], accessibility="limited",
         airport="Dehradun (DED)", airport_km=35, railhead="Rishikesh / Haridwar", railhead_km=25, price_index=0.9,
         wiki="Rishikesh",
         description="Yoga and adventure town on the Ganga in the Himalayan foothills, known for rafting and riverside ashrams."),
    dict(id="manali", name="Manali", state="Himachal Pradesh", region="Himalaya", type="mountain resort", climate="cold",
         lat=32.2396, lon=77.1887, best_seasons=["summer", "winter"], min_days=3, max_days=6,
         tags=["mountains", "adventure", "nature", "photography"], accessibility="limited",
         airport="Kullu-Manali (KUU)", airport_km=50, railhead="Chandigarh / Joginder Nagar", railhead_km=250, price_index=1.1,
         wiki="Manali,_Himachal_Pradesh",
         description="An alpine valley town on the Beas river, gateway to snow-fields, passes and adventure sports."),
    dict(id="shimla", name="Shimla", state="Himachal Pradesh", region="Himalaya", type="hill station", climate="cold",
         lat=31.1048, lon=77.1734, best_seasons=["summer", "winter", "post-monsoon"], min_days=2, max_days=4,
         tags=["mountains", "nature", "historical", "shopping", "photography"], accessibility="moderate",
         airport="Shimla (SLV) / Chandigarh (IXC)", airport_km=22, railhead="Shimla (narrow gauge) / Kalka", railhead_km=0, price_index=1.05,
         wiki="Shimla",
         description="The former summer capital of British India: a ridge-top town of colonial architecture and pine forests."),
    dict(id="darjeeling", name="Darjeeling", state="West Bengal", region="East", type="hill station", climate="cool",
         lat=27.0410, lon=88.2663, best_seasons=["post-monsoon", "summer", "winter"], min_days=2, max_days=5,
         tags=["mountains", "nature", "photography", "food", "wellness"], accessibility="moderate",
         airport="Bagdogra (IXB)", airport_km=90, railhead="New Jalpaiguri", railhead_km=75, price_index=1.0,
         wiki="Darjeeling",
         description="A tea-growing hill town with a heritage toy train and sunrise views of the Kanchenjunga range."),
]

# --------------------------------------------------------------------------
# Attractions: (id, dest, name, tags, lat, lon, duration_min, fee_inr, intensity 1-3,
#               accessible True/False/None, slot, significance 1-3, description)
# --------------------------------------------------------------------------
A = []


def att(did, name, tags, lat, lon, dur, fee, intensity, accessible, slot, sig, desc):
    A.append(dict(id=f"{did}-{len(A):03d}", destination_id=did, name=name, tags=tags, lat=lat, lon=lon,
                  duration_min=dur, fee_inr=fee, intensity=intensity, accessible=accessible,
                  best_slot=slot, significance=sig, description=desc))


# Ooty
att("ooty", "Government Botanical Gardens", ["nature", "photography"], 11.4189, 76.7110, 90, 30, 1, True, "morning", 3, "Terraced gardens with exotic trees and seasonal flower displays.")
att("ooty", "Ooty Lake", ["nature", "relaxation", "photography"], 11.4020, 76.6870, 75, 20, 1, True, "afternoon", 2, "Artificial lake with boating and a lakeside promenade.")
att("ooty", "Doddabetta Peak", ["mountains", "photography", "nature"], 11.4003, 76.7375, 75, 10, 2, None, "morning", 3, "Highest point in the Nilgiris with panoramic viewpoint.")
att("ooty", "Nilgiri Mountain Railway ride", ["culture", "historical", "photography"], 11.4118, 76.7000, 180, 50, 1, None, "morning", 3, "Heritage rack-railway journey between Ooty and Coonoor.")
att("ooty", "Rose Garden", ["nature", "photography"], 11.4107, 76.7073, 60, 30, 1, True, "afternoon", 2, "Large terraced rose garden with many cultivars.")
att("ooty", "Tea Factory and Museum", ["culture", "food", "nature"], 11.4010, 76.7300, 60, 20, 1, True, "afternoon", 2, "Walkthrough of tea processing with tasting.")
att("ooty", "Pykara Lake and Falls", ["nature", "adventure", "photography"], 11.4693, 76.5898, 120, 60, 2, None, "afternoon", 2, "Lake and cascades on the road to Mudumalai, with boating.")
# Coorg
att("coorg", "Abbey Falls", ["nature", "photography"], 12.4540, 75.7310, 75, 15, 2, False, "morning", 3, "Waterfall reached through a coffee-and-spice plantation path.")
att("coorg", "Raja's Seat", ["nature", "photography", "relaxation"], 12.4181, 75.7343, 60, 10, 1, True, "evening", 3, "Garden viewpoint popular for sunset over the valley.")
att("coorg", "Madikeri Fort and Museum", ["historical", "culture"], 12.4250, 75.7380, 75, 20, 1, None, "morning", 2, "Hill fort in the town centre with a small museum.")
att("coorg", "Dubare Elephant Camp", ["nature", "adventure"], 12.3745, 75.9130, 150, 150, 2, False, "morning", 2, "River-side elephant camp reached by a short boat crossing.")
att("coorg", "Coffee plantation walk", ["nature", "food", "wellness"], 12.4000, 75.7500, 120, 300, 1, None, "morning", 3, "Guided walk through a working coffee estate with tasting.")
att("coorg", "Namdroling Monastery (Bylakuppe)", ["culture", "photography"], 12.4350, 76.2900, 120, 0, 1, True, "afternoon", 2, "Large Tibetan Buddhist monastery complex.")
att("coorg", "Talacauvery", ["nature", "culture", "mountains"], 12.3860, 75.4870, 90, 0, 2, None, "afternoon", 2, "Hilltop shrine at the traditional source of the Kaveri river.")
# Munnar
att("munnar", "Eravikulam National Park", ["nature", "mountains", "adventure"], 10.1750, 77.0510, 180, 200, 2, None, "morning", 3, "High-range grassland park known for the Nilgiri tahr. Entry is quota-controlled.")
att("munnar", "Mattupetty Dam", ["nature", "photography", "relaxation"], 10.1060, 77.1230, 75, 100, 1, True, "afternoon", 2, "Reservoir with boating and tea-estate views.")
att("munnar", "Tea Museum", ["culture", "food", "historical"], 10.0850, 77.0630, 60, 125, 1, True, "afternoon", 2, "Museum on the region's tea-planting history with factory demonstration.")
att("munnar", "Top Station viewpoint", ["mountains", "photography"], 10.1180, 77.2290, 90, 0, 2, None, "morning", 3, "Highest road-accessible viewpoint in the area.")
att("munnar", "Attukal Waterfalls", ["nature", "photography"], 10.0760, 77.0170, 60, 0, 1, None, "afternoon", 1, "Roadside waterfall amid tea estates.")
att("munnar", "Echo Point", ["nature", "adventure"], 10.1090, 77.1580, 60, 0, 1, None, "evening", 1, "Lakeside viewpoint with a natural echo.")
# Kodaikanal
att("kodaikanal", "Kodai Lake", ["nature", "relaxation"], 10.2380, 77.4890, 90, 50, 1, True, "afternoon", 3, "Star-shaped lake at the heart of the town, with boating and a cycle path.")
att("kodaikanal", "Coaker's Walk", ["nature", "photography", "mountains"], 10.2330, 77.4950, 60, 15, 1, True, "morning", 3, "Paved cliffside path with valley views.")
att("kodaikanal", "Pillar Rocks", ["nature", "photography"], 10.2070, 77.4710, 60, 10, 2, None, "morning", 2, "Three granite pillars rising about 120 m.")
att("kodaikanal", "Bryant Park", ["nature", "photography"], 10.2390, 77.4910, 60, 30, 1, True, "afternoon", 2, "Botanical park with a flower show season.")
att("kodaikanal", "Guna Caves", ["nature", "adventure"], 10.2160, 77.4620, 60, 10, 2, False, "morning", 1, "Rock cave formations among pine forest.")
att("kodaikanal", "Bear Shola Falls", ["nature"], 10.2380, 77.4750, 60, 0, 2, None, "afternoon", 1, "Seasonal waterfall in forest near the town.")
# Mysuru
att("mysuru", "Mysore Palace", ["historical", "culture", "photography"], 12.3052, 76.6552, 120, 100, 1, True, "morning", 3, "The royal residence of the Wadiyar dynasty, illuminated on selected evenings.")
att("mysuru", "Chamundi Hill", ["culture", "mountains", "photography"], 12.2724, 76.6700, 120, 0, 2, None, "morning", 2, "Hilltop temple above the city with views.")
att("mysuru", "Brindavan Gardens", ["nature", "photography", "relaxation"], 12.4210, 76.5720, 120, 50, 1, True, "evening", 2, "Terraced garden below the Krishnaraja Sagara dam.")
att("mysuru", "Mysore Zoo", ["nature", "wildlife"], 12.3010, 76.6520, 150, 100, 1, True, "afternoon", 2, "One of India's older zoological gardens.")
att("mysuru", "St. Philomena's Church", ["historical", "culture", "photography"], 12.3135, 76.6489, 45, 0, 1, True, "afternoon", 1, "Neo-Gothic cathedral.")
att("mysuru", "Devaraja Market", ["shopping", "food", "culture"], 12.3062, 76.6521, 75, 0, 1, True, "evening", 2, "Historic market for flowers, spices, silk and sandalwood.")
# Hampi
att("hampi", "Virupaksha Temple and Hampi Bazaar", ["historical", "culture", "photography"], 15.3350, 76.4600, 120, 0, 1, True, "morning", 3, "Living temple at the western end of the old bazaar street.")
att("hampi", "Vittala Temple (Stone Chariot)", ["historical", "photography", "culture"], 15.3434, 76.4756, 120, 40, 2, None, "morning", 3, "Temple complex famed for its stone chariot and musical pillars.")
att("hampi", "Royal Enclosure and Lotus Mahal", ["historical", "photography"], 15.3200, 76.4750, 120, 40, 1, True, "afternoon", 3, "Palace platforms, stepped tank and the Indo-Islamic Lotus Mahal.")
att("hampi", "Hemakuta Hill sunset", ["photography", "historical"], 15.3340, 76.4630, 60, 0, 2, None, "evening", 2, "Early temples on a hill overlooking the site.")
att("hampi", "Matanga Hill climb", ["adventure", "photography", "nature"], 15.3330, 76.4680, 90, 0, 3, False, "morning", 2, "Steep climb to a panoramic viewpoint, popular at sunrise.")
att("hampi", "Elephant Stables", ["historical", "photography"], 15.3170, 76.4770, 45, 0, 1, True, "afternoon", 2, "Domed stables for royal elephants.")
# Goa
att("goa", "Baga Beach", ["beaches", "adventure", "food"], 15.5553, 73.7517, 150, 0, 1, True, "afternoon", 2, "Busy beach with water sports and shacks.")
att("goa", "Fort Aguada", ["historical", "photography"], 15.4929, 73.7737, 75, 0, 1, None, "evening", 3, "17th-century Portuguese fort and lighthouse above the sea.")
att("goa", "Basilica of Bom Jesus (Old Goa)", ["historical", "culture"], 15.5009, 73.9116, 75, 0, 1, True, "morning", 3, "UNESCO-listed baroque church in Old Goa.")
att("goa", "Fontainhas Latin Quarter (Panaji)", ["culture", "photography", "food"], 15.4960, 73.8310, 120, 0, 1, True, "morning", 3, "Heritage neighbourhood of colourful Portuguese-era houses.")
att("goa", "Dudhsagar Falls", ["nature", "adventure", "photography"], 15.3144, 74.3143, 300, 400, 2, False, "morning", 2, "Tiered waterfall on the Goa-Karnataka border; access is by jeep and seasonal.")
att("goa", "Palolem Beach (South Goa)", ["beaches", "relaxation"], 15.0100, 74.0230, 180, 0, 1, True, "afternoon", 2, "Crescent beach with a calmer atmosphere.")
att("goa", "Anjuna and Vagator coast", ["beaches", "shopping", "photography"], 15.5736, 73.7413, 150, 0, 1, None, "evening", 1, "Cliff-backed beaches and markets.")
# Pondicherry
att("pondicherry", "Promenade Beach", ["beaches", "relaxation", "photography"], 11.9330, 79.8330, 60, 0, 1, True, "evening", 2, "Seafront promenade for sunrise and evening walks.")
att("pondicherry", "French Quarter (White Town)", ["historical", "culture", "photography", "food"], 11.9350, 79.8300, 150, 0, 1, True, "morning", 3, "Grid of colonial villas, cafes and boutiques.")
att("pondicherry", "Auroville and Matrimandir", ["culture", "wellness"], 12.0069, 79.8106, 150, 0, 1, True, "morning", 3, "Experimental township; Matrimandir viewing requires advance arrangements.")
att("pondicherry", "Sri Aurobindo Ashram", ["culture", "wellness"], 11.9340, 79.8300, 45, 0, 1, True, "morning", 2, "Spiritual community centre in the old town.")
att("pondicherry", "Basilica of the Sacred Heart", ["historical", "culture"], 11.9250, 79.8290, 40, 0, 1, True, "afternoon", 1, "Gothic-style church.")
att("pondicherry", "Paradise Beach (boat trip)", ["beaches", "relaxation"], 11.8800, 79.8180, 180, 250, 1, None, "afternoon", 2, "Boat access to a quiet beach south of the town.")
# Jaipur
att("jaipur", "Amber Fort", ["historical", "photography", "culture"], 26.9855, 75.8513, 150, 100, 2, None, "morning", 3, "Hilltop fort-palace with mirrored halls.")
att("jaipur", "City Palace", ["historical", "culture"], 26.9255, 75.8236, 120, 200, 1, True, "morning", 3, "Royal complex with museums and courtyards.")
att("jaipur", "Hawa Mahal", ["historical", "photography"], 26.9239, 75.8267, 45, 50, 1, None, "morning", 3, "Five-storey facade of lattice windows.")
att("jaipur", "Jantar Mantar", ["historical", "culture"], 26.9247, 75.8246, 60, 50, 1, True, "afternoon", 2, "18th-century astronomical instruments (UNESCO).")
att("jaipur", "Nahargarh Fort sunset", ["historical", "photography"], 26.9376, 75.8155, 90, 50, 2, None, "evening", 2, "Fort above the city with sunset views.")
att("jaipur", "Johari Bazaar", ["shopping", "food", "culture"], 26.9190, 75.8250, 120, 0, 1, True, "evening", 2, "Jewellery and textile bazaar.")
# Udaipur
att("udaipur", "City Palace Udaipur", ["historical", "culture", "photography"], 24.5764, 73.6835, 120, 300, 1, None, "morning", 3, "Palace complex on the shore of Lake Pichola.")
att("udaipur", "Lake Pichola boat ride", ["photography", "relaxation"], 24.5720, 73.6790, 60, 400, 1, True, "evening", 3, "Boat ride past island palaces at sunset.")
att("udaipur", "Saheliyon-ki-Bari", ["nature", "historical"], 24.5990, 73.6890, 60, 10, 1, True, "afternoon", 2, "Courtyard garden with fountains.")
att("udaipur", "Monsoon Palace (Sajjangarh)", ["historical", "photography", "nature"], 24.5950, 73.6350, 90, 100, 1, True, "evening", 2, "Hilltop palace with a wide valley view.")
att("udaipur", "Jagdish Temple", ["culture", "historical"], 24.5792, 73.6830, 40, 0, 1, None, "morning", 2, "Indo-Aryan temple near the City Palace.")
att("udaipur", "Bagore ki Haveli", ["culture", "historical"], 24.5790, 73.6810, 60, 100, 1, None, "afternoon", 2, "Haveli museum and evening cultural show venue.")
# Agra
att("agra", "Taj Mahal", ["historical", "photography", "culture"], 27.1751, 78.0421, 180, 250, 1, True, "morning", 3, "17th-century marble mausoleum (UNESCO). Closed on Fridays.")
att("agra", "Agra Fort", ["historical", "culture"], 27.1795, 78.0211, 120, 100, 1, None, "afternoon", 3, "Red-sandstone Mughal fortress (UNESCO).")
att("agra", "Mehtab Bagh", ["photography", "nature", "relaxation"], 27.1790, 78.0440, 60, 30, 1, True, "evening", 2, "Garden across the river facing the Taj Mahal.")
att("agra", "Itimad-ud-Daulah", ["historical", "photography"], 27.1930, 78.0300, 60, 30, 1, True, "afternoon", 2, "Mughal marble tomb with fine inlay work.")
att("agra", "Fatehpur Sikri", ["historical", "culture"], 27.0940, 77.6610, 180, 50, 1, None, "morning", 3, "Abandoned Mughal capital (UNESCO) about 40 km from Agra.")
att("agra", "Kinari Bazaar and local food", ["shopping", "food"], 27.1800, 78.0100, 90, 0, 1, True, "evening", 1, "Old city bazaar for petha sweets and crafts.")
# Varanasi
att("varanasi", "Dashashwamedh Ghat evening aarti", ["culture", "photography"], 25.3070, 83.0100, 90, 0, 1, None, "evening", 3, "Nightly riverside ritual.")
att("varanasi", "Sunrise boat ride on the Ganga", ["culture", "photography", "relaxation"], 25.3050, 83.0100, 90, 300, 1, None, "morning", 3, "Row-boat along the ghats at dawn.")
att("varanasi", "Kashi Vishwanath Temple", ["culture", "historical"], 25.3109, 83.0107, 75, 0, 1, None, "morning", 3, "Major Shiva temple; queues and security checks are common.")
att("varanasi", "Sarnath", ["historical", "culture"], 25.3813, 83.0226, 150, 25, 1, True, "afternoon", 3, "Buddhist site where the Buddha gave his first sermon.")
att("varanasi", "Assi Ghat", ["culture", "wellness", "photography"], 25.2890, 83.0060, 60, 0, 1, None, "morning", 2, "Southern ghat with morning yoga and music.")
att("varanasi", "Ramnagar Fort", ["historical"], 25.2690, 83.0230, 90, 50, 1, None, "afternoon", 1, "18th-century fort on the east bank.")
# Rishikesh
att("rishikesh", "Ganga river rafting", ["adventure", "nature"], 30.1500, 78.3500, 240, 800, 3, False, "morning", 3, "Guided white-water rafting; seasonal and subject to water levels.")
att("rishikesh", "Laxman Jhula and Ram Jhula", ["culture", "photography"], 30.1260, 78.3290, 75, 0, 1, None, "morning", 2, "Pedestrian suspension bridges over the Ganga.")
att("rishikesh", "Triveni Ghat evening aarti", ["culture", "photography"], 30.1000, 78.2980, 75, 0, 1, True, "evening", 3, "Riverside evening ceremony.")
att("rishikesh", "Beatles Ashram (Chaurasi Kutia)", ["culture", "historical", "photography"], 30.1170, 78.3180, 75, 150, 1, None, "afternoon", 2, "Ruined ashram within Rajaji National Park boundaries.")
att("rishikesh", "Yoga session at an ashram", ["wellness", "culture"], 30.1150, 78.3100, 90, 300, 1, True, "morning", 3, "Drop-in yoga class.")
att("rishikesh", "Waterfall trek (Neer Garh)", ["nature", "adventure"], 30.1310, 78.3260, 120, 20, 2, False, "afternoon", 2, "Short walk to a series of pools and cascades.")
# Manali
att("manali", "Solang Valley", ["adventure", "mountains", "photography"], 32.3160, 77.1560, 240, 500, 2, False, "morning", 3, "Valley with seasonal snow activities and paragliding.")
att("manali", "Hadimba Devi Temple", ["culture", "historical", "photography"], 32.2480, 77.1800, 60, 0, 1, True, "morning", 2, "Wooden temple in a cedar forest.")
att("manali", "Old Manali cafes and bridge walk", ["food", "culture", "relaxation"], 32.2590, 77.1790, 120, 0, 1, None, "afternoon", 2, "Cafe-lined lanes across the Manalsu bridge.")
att("manali", "Vashisht hot springs and temple", ["wellness", "culture"], 32.2640, 77.1900, 90, 0, 1, None, "evening", 2, "Village with hot-spring baths and old temples.")
att("manali", "Jogini Falls trek", ["nature", "adventure"], 32.2790, 77.1820, 150, 0, 2, False, "morning", 2, "Forest trail to a waterfall.")
att("manali", "Rohtang Pass excursion", ["mountains", "adventure", "photography"], 32.3716, 77.2466, 360, 800, 2, False, "morning", 3, "High pass; entry needs a permit and is weather- and season-dependent.")
# Shimla
att("shimla", "The Ridge and Christ Church", ["historical", "photography", "culture"], 31.1042, 77.1734, 75, 0, 1, True, "morning", 3, "Open promenade with a landmark church.")
att("shimla", "Mall Road", ["shopping", "food"], 31.1040, 77.1700, 120, 0, 1, True, "evening", 2, "Pedestrian shopping street with eateries.")
att("shimla", "Jakhoo Temple", ["culture", "mountains", "nature"], 31.1010, 77.1850, 90, 0, 2, None, "morning", 2, "Hilltop temple above the town.")
att("shimla", "Kufri", ["nature", "adventure", "mountains"], 31.0970, 77.2670, 180, 100, 1, None, "afternoon", 2, "Nearby hill resort known for scenic walks and seasonal snow.")
att("shimla", "Viceregal Lodge", ["historical", "culture"], 31.1000, 77.1480, 90, 50, 1, None, "afternoon", 2, "Former British viceroy's residence set in gardens.")
att("shimla", "Kalka-Shimla toy train", ["historical", "culture", "photography"], 31.1030, 77.1650, 240, 100, 1, None, "morning", 2, "Narrow-gauge heritage railway (UNESCO).")
# Darjeeling
att("darjeeling", "Tiger Hill sunrise", ["mountains", "photography", "nature"], 27.0000, 88.2740, 150, 100, 1, True, "morning", 3, "Predawn drive to a viewpoint for sunrise over Kanchenjunga (weather dependent).")
att("darjeeling", "Darjeeling Himalayan Railway (toy train)", ["historical", "culture", "photography"], 27.0410, 88.2640, 120, 1500, 1, None, "morning", 3, "Heritage narrow-gauge joy ride (UNESCO).")
att("darjeeling", "Batasia Loop", ["historical", "photography"], 27.0120, 88.2540, 45, 20, 1, True, "afternoon", 2, "Spiral track with a memorial garden and views.")
att("darjeeling", "Himalayan Mountaineering Institute and Zoo", ["mountains", "nature", "historical"], 27.0170, 88.2540, 150, 100, 2, None, "afternoon", 2, "Mountaineering museum and high-altitude zoo.")
att("darjeeling", "Peace Pagoda", ["culture", "photography"], 27.0180, 88.2670, 60, 0, 1, None, "afternoon", 1, "Hilltop Buddhist stupa.")
att("darjeeling", "Happy Valley Tea Estate", ["nature", "food", "culture"], 27.0535, 88.2690, 75, 50, 1, None, "morning", 2, "Working tea estate with factory tour.")

# --------------------------------------------------------------------------
# Origins (departure cities)
# --------------------------------------------------------------------------
ORIGINS = [
    dict(id="hyderabad", name="Hyderabad", lat=17.3850, lon=78.4867),
    dict(id="bengaluru", name="Bengaluru", lat=12.9716, lon=77.5946),
    dict(id="chennai", name="Chennai", lat=13.0827, lon=80.2707),
    dict(id="mumbai", name="Mumbai", lat=19.0760, lon=72.8777),
    dict(id="delhi", name="New Delhi", lat=28.6139, lon=77.2090),
    dict(id="kolkata", name="Kolkata", lat=22.5726, lon=88.3639),
    dict(id="pune", name="Pune", lat=18.5204, lon=73.8567),
    dict(id="ahmedabad", name="Ahmedabad", lat=23.0225, lon=72.5714),
    dict(id="kochi", name="Kochi", lat=9.9312, lon=76.2673),
    dict(id="coimbatore", name="Coimbatore", lat=11.0168, lon=76.9558),
    dict(id="visakhapatnam", name="Visakhapatnam", lat=17.6868, lon=83.2185),
    dict(id="lucknow", name="Lucknow", lat=26.8467, lon=80.9462),
]

ROAD_FACTOR = 1.30  # road/rail distance ~ 1.3 x straight line


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------
# Transport MODEL (v1): documented, deterministic, NOT real fares/timetables.
# --------------------------------------------------------------------------
MODEL = {
    "bus":    dict(rate=1.9, speed=45, min_fare=150, max_km=1100, comfort=2),
    "train":  dict(rate=1.1, speed=55, min_fare=180, max_km=3000, comfort=3),
    "car":    dict(rate=12.0, speed=50, min_fare=800, max_km=800, comfort=4),   # whole vehicle, up to 4 seats
    "flight": dict(base=2600, rate=2.2, speed=650, overhead_h=3.5, min_km=400, comfort=5),
}


def transport_links():
    rows = []
    for o in ORIGINS:
        for d in DESTINATIONS:
            straight = haversine(o["lat"], o["lon"], d["lat"], d["lon"])
            road = straight * ROAD_FACTOR
            # bus
            if road <= MODEL["bus"]["max_km"]:
                rows.append(dict(origin=o["id"], destination=d["id"], mode="bus", distance_km=round(road),
                                 price_inr=max(MODEL["bus"]["min_fare"], round(road * MODEL["bus"]["rate"], -1)),
                                 duration_h=round(road / MODEL["bus"]["speed"] + 0.5, 1), comfort=2, price_basis="per_person"))
            # train needs a railhead; add railhead->destination transfer km as bus/taxi leg cost
            rail_km = road + d["railhead_km"]
            rows.append(dict(origin=o["id"], destination=d["id"], mode="train", distance_km=round(rail_km),
                             price_inr=max(MODEL["train"]["min_fare"], round(road * MODEL["train"]["rate"] + d["railhead_km"] * 2.5, -1)),
                             duration_h=round(road / MODEL["train"]["speed"] + d["railhead_km"] / 40 + 0.5, 1), comfort=3, price_basis="per_person"))
            # car (whole-vehicle price)
            if road <= MODEL["car"]["max_km"]:
                rows.append(dict(origin=o["id"], destination=d["id"], mode="car", distance_km=round(road),
                                 price_inr=round(road * MODEL["car"]["rate"], -2), duration_h=round(road / MODEL["car"]["speed"] + 0.5, 1),
                                 comfort=4, price_basis="per_vehicle"))
            # flight: needs airport and a meaningful distance
            if straight >= MODEL["flight"]["min_km"]:
                transfer = d["airport_km"]
                rows.append(dict(origin=o["id"], destination=d["id"], mode="flight", distance_km=round(straight + transfer),
                                 price_inr=round(MODEL["flight"]["base"] + straight * MODEL["flight"]["rate"] + transfer * 2.5, -1),
                                 duration_h=round(straight / MODEL["flight"]["speed"] + MODEL["flight"]["overhead_h"] + transfer / 45, 1),
                                 comfort=5, price_basis="per_person"))
    for r in rows:
        r["basis"] = "distance_model_v1 (estimate, not a real fare or timetable)"
    return rows


# --------------------------------------------------------------------------
# Accommodation: FICTIONAL sample records generated per destination and tier.
# --------------------------------------------------------------------------
TIERS = {
    "hostel":    dict(price=450, unit="per_bed", capacity=1, amenities=["wifi", "shared kitchen", "lockers"], comfort=1, accessible=False),
    "budget":    dict(price=1100, unit="per_room", capacity=2, amenities=["wifi", "hot water"], comfort=2, accessible=False),
    "homestay":  dict(price=1600, unit="per_room", capacity=2, amenities=["wifi", "home-cooked meals", "garden"], comfort=3, accessible=None),
    "midrange":  dict(price=2900, unit="per_room", capacity=2, amenities=["wifi", "breakfast", "restaurant", "lift"], comfort=4, accessible=True),
    "premium":   dict(price=6500, unit="per_room", capacity=2, amenities=["wifi", "breakfast", "spa", "restaurant", "lift"], comfort=5, accessible=True),
}


def accommodation():
    rows = []
    for d in DESTINATIONS:
        for i, (tier, t) in enumerate(TIERS.items()):
            off = (i - 2) * 0.004
            rows.append(dict(
                id=f"{d['id']}-{tier}", destination_id=d["id"], name=f"{d['name']} {tier.title()} Stay (sample)",
                tier=tier, price_inr=round(t["price"] * d["price_index"], -1), price_unit=t["unit"], capacity=t["capacity"],
                amenities=t["amenities"], comfort=t["comfort"], accessible=t["accessible"],
                lat=round(d["lat"] + off, 5), lon=round(d["lon"] - off * 0.8, 5),
                is_sample=True, note="Fictional placeholder record; price is an estimate."))
    return rows


FOOD_PER_PERSON_DAY = {"budget": 350, "mid": 700, "premium": 1500}
LOCAL_KM_RATE = 14.0  # INR per km for a shared auto/taxi (vehicle seats up to 4)


def destinations_out():
    out = []
    for d in DESTINATIONS:
        dd = dict(d)
        dd["country"] = "India"
        dd["food_per_person_day"] = {k: round(v * d["price_index"], -1) for k, v in FOOD_PER_PERSON_DAY.items()}
        dd["is_sample"] = True
        out.append(dd)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "destinations": destinations_out(),
        "attractions": A,
        "accommodation": accommodation(),
        "transport_links": transport_links(),
        "origins": ORIGINS,
        "meta": dict(
            dataset="TripWise AI sample dataset v1",
            is_sample=True,
            road_factor=ROAD_FACTOR,
            local_km_rate=LOCAL_KM_RATE,
            transport_model=MODEL,
            disclaimer="Illustrative sample data. Coordinates approximate; fees and prices are estimates; "
                       "accommodation is fictional; transport figures come from a distance model.",
        ),
    }
    for k in ("destinations", "attractions", "accommodation", "transport_links", "origins", "meta"):
        (OUT / f"{k}.json").write_text(json.dumps(payload[k], indent=1, ensure_ascii=False), encoding="utf-8")
    print({k: (len(v) if isinstance(v, list) else "meta") for k, v in payload.items()})


if __name__ == "__main__":
    main()
