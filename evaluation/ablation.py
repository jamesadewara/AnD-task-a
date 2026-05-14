#!/usr/bin/env python3
"""
AnD Task A Ablation Study
==========================
Evaluates review generation quality with/without key components.

Ablations:
  - Full System (baseline)
  - w/o Price Shock
  - w/o Style Fingerprint (past_reviews)
  - w/o Nigerian Context Markers

Metrics:
  - RMSE vs expected rating ranges
  - Rating accuracy (within expected range)
  - Nigerian marker presence

Usage:
  python ablation.py --output_dir ./results
"""

import argparse
import json
import os
import sys
import asyncio
import math
import statistics
import time
from typing import List, Dict

# Add parent paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ml.rating_predictor import RatingPredictor

# --- TEST CASES (50) ---
TEST_CASES = [
    # Haggler (10)
    {"case_id": "a_001", "persona": {"name": "Musa", "archetype": "Haggler", "budget": 5000, "interests": ["street_food"], "traits": ["price_sensitive"], "tone": "sharp", "price_sensitivity": "high", "location": "Kano", "past_reviews": [{"rating": 4, "text": "Good value for 4000"}]}, "product": {"name": "Glover Court Suya", "description": "Price: ₦4,000", "price_naira": 4000, "category": "street_food", "tags": ["spicy"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_002", "persona": {"name": "Chidi", "archetype": "Haggler", "budget": 3000, "interests": ["street_food"], "traits": ["price_sensitive"], "tone": "polite", "price_sensitivity": "high", "location": "Lagos", "past_reviews": []}, "product": {"name": "iPhone 15 Pro", "description": "Price: ₦1,450,000", "price_naira": 1450000, "category": "electronics", "tags": ["premium"]}, "expected_range": (1.0, 1.5)},
    {"case_id": "a_003", "persona": {"name": "Fatima", "archetype": "Haggler", "budget": 8000, "interests": ["fashion"], "traits": ["value_seeker"], "tone": "direct", "price_sensitivity": "high", "location": "Abuja", "past_reviews": []}, "product": {"name": "Leather Slippers", "description": "Price: ₦12,500", "price_naira": 12500, "category": "fashion", "tags": ["traditional"]}, "expected_range": (2.0, 3.0)},
    {"case_id": "a_004", "persona": {"name": "Bayo", "archetype": "Haggler", "budget": 4500, "interests": ["street_food"], "traits": ["frugal"], "tone": "humorous", "price_sensitivity": "high", "location": "Ibadan", "past_reviews": []}, "product": {"name": "Akara and Pap", "description": "Price: ₦800", "price_naira": 800, "category": "street_food", "tags": ["breakfast"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_005", "persona": {"name": "Efe", "archetype": "Haggler", "budget": 6000, "interests": ["electronics"], "traits": ["tech_savvy"], "tone": "skeptical", "price_sensitivity": "high", "location": "Warri", "past_reviews": []}, "product": {"name": "Oraimo FreePods 3", "description": "Price: ₦24,500", "price_naira": 24500, "category": "electronics", "tags": ["audio"]}, "expected_range": (1.5, 2.5)},
    {"case_id": "a_006", "persona": {"name": "Zainab", "archetype": "Haggler", "budget": 7000, "interests": ["street_food"], "traits": ["traditional"], "tone": "respectful", "price_sensitivity": "high", "location": "Kaduna", "past_reviews": []}, "product": {"name": "Kilishi", "description": "Price: ₦3,500", "price_naira": 3500, "category": "street_food", "tags": ["northern"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_007", "persona": {"name": "Tunde", "archetype": "Haggler", "budget": 4000, "interests": ["nollywood"], "traits": ["entertainment_lover"], "tone": "casual", "price_sensitivity": "high", "location": "Lagos", "past_reviews": []}, "product": {"name": "King of Boys", "description": "Price: ₦1,200", "price_naira": 1200, "category": "nollywood", "tags": ["movie night"]}, "expected_range": (4.5, 5.0)},
    {"case_id": "a_008", "persona": {"name": "Ngozi", "archetype": "Haggler", "budget": 5500, "interests": ["wellness"], "traits": ["naturalist"], "tone": "thoughtful", "price_sensitivity": "high", "location": "Enugu", "past_reviews": []}, "product": {"name": "Organic Shea Butter", "description": "Price: ₦8,500", "price_naira": 8500, "category": "wellness", "tags": ["skin"]}, "expected_range": (2.5, 3.5)},
    {"case_id": "a_009", "persona": {"name": "Ibrahim", "archetype": "Haggler", "budget": 3500, "interests": ["electronics"], "traits": ["budget_conscious"], "tone": "serious", "price_sensitivity": "high", "location": "Kano", "past_reviews": []}, "product": {"name": "Binatone Fan", "description": "Price: ₦35,000", "price_naira": 35000, "category": "electronics", "tags": ["home"]}, "expected_range": (1.0, 2.0)},
    {"case_id": "a_010", "persona": {"name": "Yinka", "archetype": "Haggler", "budget": 8000, "interests": ["dining"], "traits": ["foodie"], "tone": "cheerful", "price_sensitivity": "high", "location": "Lagos", "past_reviews": []}, "product": {"name": "Yellow Chilli Okra", "description": "Price: ₦15,500", "price_naira": 15500, "category": "dining", "tags": ["gourmet"]}, "expected_range": (2.0, 3.0)},

    # Big Woman (10)
    {"case_id": "a_011", "persona": {"name": "Chief Mrs. Adenuga", "archetype": "Big Woman", "budget": 150000, "interests": ["fashion"], "traits": ["prestige", "quality_focused"], "tone": "commanding", "price_sensitivity": "low", "location": "Lagos", "past_reviews": [{"rating": 5, "text": "Exquisite quality"}]}, "product": {"name": "Designer Aso Oke", "description": "Price: ₦120,000", "price_naira": 120000, "category": "fashion", "tags": ["bespoke"]}, "expected_range": (4.5, 5.0)},
    {"case_id": "a_012", "persona": {"name": "Dr. Ifeoma", "archetype": "Big Woman", "budget": 200000, "interests": ["wellness"], "traits": ["exclusive"], "tone": "refined", "price_sensitivity": "low", "location": "Abuja", "past_reviews": []}, "product": {"name": "Spa Day at Wheatbaker", "description": "Price: ₦120,000", "price_naira": 120000, "category": "wellness", "tags": ["luxury"]}, "expected_range": (4.5, 5.0)},
    {"case_id": "a_013", "persona": {"name": "Hajiya Aisha", "archetype": "Big Woman", "budget": 100000, "interests": ["dining"], "traits": ["sophisticated"], "tone": "elegant", "price_sensitivity": "low", "location": "Abuja", "past_reviews": []}, "product": {"name": "Dinner at RSVP Lagos", "description": "Price: ₦85,000", "price_naira": 85000, "category": "dining", "tags": ["fine dining"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_014", "persona": {"name": "Madam Kofo", "archetype": "Big Woman", "budget": 75000, "interests": ["fashion"], "traits": ["traditional"], "tone": "vivacious", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Ankara Wrap Dress", "description": "Price: ₦55,000", "price_naira": 55000, "category": "fashion", "tags": ["silk"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_015", "persona": {"name": "Justice Mary", "archetype": "Big Woman", "budget": 180000, "interests": ["electronics"], "traits": ["high_performance"], "tone": "formal", "price_sensitivity": "low", "location": "Enugu", "past_reviews": []}, "product": {"name": "iPhone 15 Pro", "description": "Price: ₦1,450,000", "price_naira": 1450000, "category": "electronics", "tags": ["premium"]}, "expected_range": (2.0, 3.5)},
    {"case_id": "a_016", "persona": {"name": "Princess Ronke", "archetype": "Big Woman", "budget": 120000, "interests": ["community_events"], "traits": ["socialite"], "tone": "expressive", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Art X Lagos Ticket", "description": "Price: ₦25,000", "price_naira": 25000, "category": "community_events", "tags": ["networking"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_017", "persona": {"name": "Mama G", "archetype": "Big Woman", "budget": 50000, "interests": ["street_food"], "traits": ["authentic"], "tone": "loud", "price_sensitivity": "medium", "location": "Onitsha", "past_reviews": []}, "product": {"name": "PH Native Soup", "description": "Price: ₦4,500", "price_naira": 4500, "category": "street_food", "tags": ["seafood"]}, "expected_range": (4.5, 5.0)},
    {"case_id": "a_018", "persona": {"name": "Executive Sade", "archetype": "Big Woman", "budget": 160000, "interests": ["dining"], "traits": ["business_oriented"], "tone": "curt", "price_sensitivity": "low", "location": "Lagos", "past_reviews": []}, "product": {"name": "Buffet at Eko Hotel", "description": "Price: ₦45,000", "price_naira": 45000, "category": "dining", "tags": ["luxury"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_019", "persona": {"name": "Deaconess Ruth", "archetype": "Big Woman", "budget": 90000, "interests": ["electronics"], "traits": ["reliable"], "tone": "gentle", "price_sensitivity": "medium", "location": "Port Harcourt", "past_reviews": []}, "product": {"name": "Hisense Smart TV", "description": "Price: ₦210,000", "price_naira": 210000, "category": "electronics", "tags": ["smart"]}, "expected_range": (2.5, 3.5)},
    {"case_id": "a_020", "persona": {"name": "Chief Nkechi", "archetype": "Big Woman", "budget": 200000, "interests": ["fashion"], "traits": ["exclusive"], "tone": "proud", "price_sensitivity": "low", "location": "Lagos", "past_reviews": []}, "product": {"name": "Gold Plated Jewelry", "description": "Price: ₦75,000", "price_naira": 75000, "category": "fashion", "tags": ["exclusive"]}, "expected_range": (4.5, 5.0)},

    # Community Validator (10)
    {"case_id": "a_021", "persona": {"name": "Segun", "archetype": "Community Validator", "budget": 20000, "interests": ["electronics"], "traits": ["social_proof", "peer_influenced"], "tone": "curious", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": [{"rating": 4, "text": "Everyone uses this"}]}, "product": {"name": "Oraimo FreePods 3", "description": "Price: ₦24,500", "price_naira": 24500, "category": "electronics", "tags": ["trending"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_022", "persona": {"name": "Amarachi", "archetype": "Community Validator", "budget": 15000, "interests": ["street_food"], "traits": ["authentic"], "tone": "enthusiastic", "price_sensitivity": "medium", "location": "PH", "past_reviews": []}, "product": {"name": "Boli and Fish", "description": "Price: ₦2,000", "price_naira": 2000, "category": "street_food", "tags": ["classic"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_023", "persona": {"name": "Uche", "archetype": "Community Validator", "budget": 25000, "interests": ["community_events"], "traits": ["active"], "tone": "social", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Gidi Culture Fest", "description": "Price: ₦35,000", "price_naira": 35000, "category": "community_events", "tags": ["trending"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_024", "persona": {"name": "Suleiman", "archetype": "Community Validator", "budget": 10000, "interests": ["nollywood"], "traits": ["cultural"], "tone": "opinionated", "price_sensitivity": "medium", "location": "Kano", "past_reviews": []}, "product": {"name": "Anikulapo", "description": "Price: ₦1,500", "price_naira": 1500, "category": "nollywood", "tags": ["folklore"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_025", "persona": {"name": "Bolaji", "archetype": "Community Validator", "budget": 30000, "interests": ["fashion"], "traits": ["trendy"], "tone": "vibrant", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Adire Silk Shirt", "description": "Price: ₦35,000", "price_naira": 35000, "category": "fashion", "tags": ["prestige"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_026", "persona": {"name": "Funmi", "archetype": "Community Validator", "budget": 12000, "interests": ["wellness"], "traits": ["health_conscious"], "tone": "thoughtful", "price_sensitivity": "medium", "location": "Abuja", "past_reviews": []}, "product": {"name": "Yoga Session", "description": "Price: ₦15,000", "price_naira": 15000, "category": "wellness", "tags": ["fitness"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_027", "persona": {"name": "Osas", "archetype": "Community Validator", "budget": 22000, "interests": ["electronics"], "traits": ["utilitarian"], "tone": "blunt", "price_sensitivity": "medium", "location": "Benin", "past_reviews": []}, "product": {"name": "MTN 5G Router", "description": "Price: ₦55,000", "price_naira": 55000, "category": "electronics", "tags": ["essential"]}, "expected_range": (2.0, 3.0)},
    {"case_id": "a_028", "persona": {"name": "Blessing", "archetype": "Community Validator", "budget": 18000, "interests": ["dining"], "traits": ["explorer"], "tone": "excited", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Terra Kulture Brunch", "description": "Price: ₦22,000", "price_naira": 22000, "category": "dining", "tags": ["culture"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_029", "persona": {"name": "Idris", "archetype": "Community Validator", "budget": 28000, "interests": ["community_events"], "traits": ["networker"], "tone": "professional", "price_sensitivity": "medium", "location": "Abuja", "past_reviews": []}, "product": {"name": "Abuja Food Fest", "description": "Price: ₦20,000", "price_naira": 20000, "category": "community_events", "tags": ["networking"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_030", "persona": {"name": "Lola", "archetype": "Community Validator", "budget": 11000, "interests": ["fashion"], "traits": ["traditional"], "tone": "warm", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Leather Slippers", "description": "Price: ₦12,500", "price_naira": 12500, "category": "fashion", "tags": ["craft"]}, "expected_range": (3.5, 4.5)},

    # Try-Am-First (10)
    {"case_id": "a_031", "persona": {"name": "Kazeem", "archetype": "Try-Am-First", "budget": 8000, "interests": ["electronics"], "traits": ["tester", "early_adopter"], "tone": "adventurous", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": [{"rating": 3, "text": "Trying it out"}]}, "product": {"name": "Power Bank", "description": "Price: ₦18,000", "price_naira": 18000, "category": "electronics", "tags": ["essential"]}, "expected_range": (2.5, 3.5)},
    {"case_id": "a_032", "persona": {"name": "Patience", "archetype": "Try-Am-First", "budget": 5000, "interests": ["street_food"], "traits": ["cautious"], "tone": "hesitant", "price_sensitivity": "high", "location": "Enugu", "past_reviews": []}, "product": {"name": "Party Jollof", "description": "Price: ₦2,500", "price_naira": 2500, "category": "street_food", "tags": ["quick"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_033", "persona": {"name": "Obinna", "archetype": "Try-Am-First", "budget": 12000, "interests": ["nollywood"], "traits": ["film_buff"], "tone": "analytic", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "The Wedding Party", "description": "Price: ₦1,000", "price_naira": 1000, "category": "nollywood", "tags": ["comedy"]}, "expected_range": (4.5, 5.0)},
    {"case_id": "a_034", "persona": {"name": "Simi", "archetype": "Try-Am-First", "budget": 15000, "interests": ["fashion"], "traits": ["style_seeker"], "tone": "trendy", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Premium Ankara", "description": "Price: ₦55,000", "price_naira": 55000, "category": "fashion", "tags": ["luxury"]}, "expected_range": (2.0, 3.0)},
    {"case_id": "a_035", "persona": {"name": "Femi", "archetype": "Try-Am-First", "budget": 7000, "interests": ["electronics"], "traits": ["utilitarian"], "tone": "practical", "price_sensitivity": "high", "location": "Ibadan", "past_reviews": []}, "product": {"name": "Oraimo FreePods", "description": "Price: ₦24,500", "price_naira": 24500, "category": "electronics", "tags": ["value"]}, "expected_range": (1.5, 2.5)},
    {"case_id": "a_036", "persona": {"name": "Amaka", "archetype": "Try-Am-First", "budget": 10000, "interests": ["wellness"], "traits": ["skincare"], "tone": "inquisitive", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Organic Shea Butter", "description": "Price: ₦8,500", "price_naira": 8500, "category": "wellness", "tags": ["organic"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_037", "persona": {"name": "Tolu", "archetype": "Try-Am-First", "budget": 13000, "interests": ["community_events"], "traits": ["social"], "tone": "friendly", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Beach Party", "description": "Price: ₦12,000", "price_naira": 12000, "category": "community_events", "tags": ["party"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_038", "persona": {"name": "Kunle", "archetype": "Try-Am-First", "budget": 6000, "interests": ["street_food"], "traits": ["snacker"], "tone": "happy", "price_sensitivity": "high", "location": "Lagos", "past_reviews": []}, "product": {"name": "Kilishi", "description": "Price: ₦3,500", "price_naira": 3500, "category": "street_food", "tags": ["snack"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_039", "persona": {"name": "Abiola", "archetype": "Try-Am-First", "budget": 9000, "interests": ["electronics"], "traits": ["tech_curious"], "tone": "open", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "MTN Router", "description": "Price: ₦55,000", "price_naira": 55000, "category": "electronics", "tags": ["internet"]}, "expected_range": (1.5, 2.5)},
    {"case_id": "a_040", "persona": {"name": "Gift", "archetype": "Try-Am-First", "budget": 14000, "interests": ["fashion"], "traits": ["fashionable"], "tone": "bright", "price_sensitivity": "medium", "location": "Abuja", "past_reviews": []}, "product": {"name": "Gold Jewelry", "description": "Price: ₦75,000", "price_naira": 75000, "category": "fashion", "tags": ["fashion"]}, "expected_range": (2.0, 3.0)},

    # Cold-start (10)
    {"case_id": "a_041", "persona": {"name": "User41", "archetype": "Haggler", "budget": 4000, "interests": ["street_food"], "traits": [], "tone": "neutral", "price_sensitivity": "high", "location": "Lagos", "past_reviews": []}, "product": {"name": "Suya", "description": "Price: ₦4,000", "price_naira": 4000, "category": "street_food", "tags": ["grilled"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_042", "persona": {"name": "User42", "archetype": "Big Woman", "budget": 180000, "interests": ["fashion"], "traits": [], "tone": "neutral", "price_sensitivity": "low", "location": "Abuja", "past_reviews": []}, "product": {"name": "Aso Oke", "description": "Price: ₦120,000", "price_naira": 120000, "category": "fashion", "tags": ["traditional"]}, "expected_range": (4.5, 5.0)},
    {"case_id": "a_043", "persona": {"name": "User43", "archetype": "Community Validator", "budget": 20000, "interests": ["electronics"], "traits": [], "tone": "neutral", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "FreePods", "description": "Price: ₦24,500", "price_naira": 24500, "category": "electronics", "tags": ["audio"]}, "expected_range": (3.0, 4.0)},
    {"case_id": "a_044", "persona": {"name": "User44", "archetype": "Try-Am-First", "budget": 10000, "interests": ["nollywood"], "traits": [], "tone": "neutral", "price_sensitivity": "medium", "location": "PH", "past_reviews": []}, "product": {"name": "King of Boys", "description": "Price: ₦1,200", "price_naira": 1200, "category": "nollywood", "tags": ["thriller"]}, "expected_range": (4.0, 5.0)},
    {"case_id": "a_045", "persona": {"name": "User45", "archetype": "Haggler", "budget": 5000, "interests": ["electronics"], "traits": [], "tone": "neutral", "price_sensitivity": "high", "location": "Lagos", "past_reviews": []}, "product": {"name": "iPhone", "description": "Price: ₦1,450,000", "price_naira": 1450000, "category": "electronics", "tags": ["premium"]}, "expected_range": (1.0, 1.5)},
    {"case_id": "a_046", "persona": {"name": "User46", "archetype": "Big Woman", "budget": 150000, "interests": ["dining"], "traits": [], "tone": "neutral", "price_sensitivity": "low", "location": "Lagos", "past_reviews": []}, "product": {"name": "Dinner RSVP", "description": "Price: ₦85,000", "price_naira": 85000, "category": "dining", "tags": ["luxury"]}, "expected_range": (4.5, 5.0)},
    {"case_id": "a_047", "persona": {"name": "User47", "archetype": "Community Validator", "budget": 15000, "interests": ["fashion"], "traits": [], "tone": "neutral", "price_sensitivity": "medium", "location": "Ibadan", "past_reviews": []}, "product": {"name": "Adire Shirt", "description": "Price: ₦35,000", "price_naira": 35000, "category": "fashion", "tags": ["culture"]}, "expected_range": (2.5, 3.5)},
    {"case_id": "a_048", "persona": {"name": "User48", "archetype": "Try-Am-First", "budget": 8000, "interests": ["street_food"], "traits": [], "tone": "neutral", "price_sensitivity": "medium", "location": "Lagos", "past_reviews": []}, "product": {"name": "Kilishi", "description": "Price: ₦3,500", "price_naira": 3500, "category": "street_food", "tags": ["northern"]}, "expected_range": (3.5, 4.5)},
    {"case_id": "a_049", "persona": {"name": "User49", "archetype": "Haggler", "budget": 3000, "interests": ["electronics"], "traits": [], "tone": "neutral", "price_sensitivity": "high", "location": "Kano", "past_reviews": []}, "product": {"name": "Power Bank", "description": "Price: ₦18,000", "price_naira": 18000, "category": "electronics", "tags": ["essential"]}, "expected_range": (1.0, 2.0)},
    {"case_id": "a_050", "persona": {"name": "User50", "archetype": "Big Woman", "budget": 200000, "interests": ["community_events"], "traits": [], "tone": "neutral", "price_sensitivity": "low", "location": "Abuja", "past_reviews": []}, "product": {"name": "Gidi Fest", "description": "Price: ₦35,000", "price_naira": 35000, "category": "community_events", "tags": ["trending"]}, "expected_range": (4.0, 5.0)},
]


def apply_ablation(study_name: str, persona: dict, product: dict) -> tuple:
    """Apply ablation modifications to persona/product."""
    p = persona.copy()
    prod = product.copy()

    if study_name == "w/o Price Shock":
        # Force price = budget to negate shock
        prod["price_naira"] = p["budget"]
        prod["description"] = f"Price: ₦{p['budget']}"
    elif study_name == "w/o Style Fingerprint":
        p["style_sample"] = ""
        p["past_reviews"] = []
    elif study_name == "w/o Nigerian Context":
        p["nigerian_context"] = False

    return p, prod


NIGERIAN_MARKERS = ["omo", "abeg", "sha", "na", "dey", "wahala", "jare", "nawa"]
# Max cases to run LLM review generation for marker counting.
# Full LLM chain per case (~4 API calls); 10 cases ≈ 40 calls, ~60-90 seconds.
MARKER_SAMPLE_SIZE = 10


def run_ablation(study_name: str, cases: List[dict]) -> dict:
    """Run one ablation study on all cases."""
    predictor = RatingPredictor()
    abs_errors = []
    in_range_count = 0
    
    # Identify cases for marker counting (Full System only)
    marker_case_results = {}
    if study_name == "Full System":
        try:
            from app.ml.review_generator import ReviewAgent
            review_agent = ReviewAgent()
            
            import random as _rnd
            rng = _rnd.Random(42)
            marker_samples = rng.sample(cases, min(MARKER_SAMPLE_SIZE, len(cases)))
            
            print(f"  Running {study_name} (including {len(marker_samples)} parallel LLM marker checks)...")
            
            async def batch_generate(agent, sample_cases):
                tasks = []
                for c in sample_cases:
                    p, pr = apply_ablation(study_name, c["persona"], c["product"])
                    payload = {"user_persona": p, "product": pr}
                    tasks.append(agent.generate_stateless_flexible(payload))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                mapped = {}
                for c, res in zip(sample_cases, results):
                    if isinstance(res, Exception):
                        mapped[c["case_id"]] = 0
                    else:
                        text = res.get("review_text", "").lower()
                        count = sum(1 for m in NIGERIAN_MARKERS if m in text)
                        mapped[c["case_id"]] = count
                return mapped

            marker_case_results = asyncio.run(batch_generate(review_agent, marker_samples))
        except Exception as e:
            print(f"    WARN: Could not batch marker generation: {e}")
    else:
        print(f"  Running {study_name}...")

    for case in cases:
        persona, product = apply_ablation(study_name, case["persona"], case["product"])

        try:
            result = predictor.predict_probabilistic(persona, product)
            pred_rating = result.get("rating", 3.0)
        except Exception as e:
            print(f"    WARN: {case['case_id']} predict failed: {e}")
            pred_rating = 3.0

        # RMSE: collect raw absolute errors (all cases)
        expected_mid = (case["expected_range"][0] + case["expected_range"][1]) / 2
        abs_errors.append(abs(expected_mid - pred_rating))

        # Accuracy: pred_rating falls within expected_range tuple
        lo, hi = case["expected_range"][0], case["expected_range"][1]
        if lo <= pred_rating <= hi:
            in_range_count += 1

    # RMSE computed from raw absolute errors
    rmse = math.sqrt(sum(e ** 2 for e in abs_errors) / len(abs_errors)) if abs_errors else 0
    # Std dev on raw absolute errors — always < max abs error
    std = statistics.stdev(abs_errors) if len(abs_errors) > 1 else 0
    accuracy = in_range_count / len(cases) if cases else 0
    
    marker_counts = list(marker_case_results.values())
    avg_markers = statistics.mean(marker_counts) if marker_counts else 0

    return {
        "rmse": round(rmse, 3),
        "std": round(std, 3),
        "accuracy": round(accuracy, 3),
        "avg_nigerian_markers": round(avg_markers, 2),
        "marker_sample_n": len(marker_counts),
        "samples": len(cases),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="./results")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    studies = ["Full System", "w/o Price Shock", "w/o Style Fingerprint", "w/o Nigerian Context"]
    results = {}

    print("\n" + "="*50)
    print("TASK A ABLATION STUDY (50 cases)")
    print("="*50)

    for study in studies:
        results[study] = run_ablation(study, TEST_CASES)

    # Save
    output_path = os.path.join(args.output_dir, "ablation_task_a.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # Print table
    print("\n" + "-"*60)
    print(f"{'Study':<30} | {'RMSE':>6} | {'Std':>5} | {'Acc':>5} | {'Markers':>7}")
    print("-"*60)
    for study, vals in results.items():
        print(f"{study:<30} | {vals['rmse']:>6.2f} | {vals['std']:>5.2f} | {vals['accuracy']:>5.2f} | {vals['avg_nigerian_markers']:>7.2f}")
    print("-"*60)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()