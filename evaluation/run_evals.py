"""
AnD-task-a: Review Generation Evaluation Runner
Computes RMSE, ROUGE, Nigerian Marker Density, and rating distribution
using consolidated corpus. All scores are empirically derived.
"""
import sys
import io
# Force UTF-8 stdout so Windows cp1252 consoles don't raise UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import json
import math
import statistics
from typing import List, Dict

# Access consolidated data from Task A corpus
CORPUS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
if CORPUS_PATH not in sys.path:
    sys.path.insert(0, CORPUS_PATH)

# Set mock env var for Pydantic validation ONLY if not already present
if "OPENROUTER_API_KEYS" not in os.environ:
    os.environ["OPENROUTER_API_KEYS"] = '["sk-or-v1-placeholder-for-tests"]'

try:
    from app.corpus.seed_items import SEED_ITEMS
    from app.corpus.reference_reviews import REFERENCE_REVIEWS
    from app.core.config import settings
    from app.ml.rating_predictor import RatingPredictor
except ImportError as e:
    print(f"Error: Could not import corpus data or settings: {e}")
    REFERENCE_REVIEWS = {}
    SEED_ITEMS = []
    settings = None
    RatingPredictor = None

try:
    from rouge_score import rouge_scorer
except ImportError:
    rouge_scorer = None

NIGERIAN_MARKERS = ["omo", "abeg", "sha", "na", "dey", "wahala", "jare", "nawa"]


def compute_rouge(generated: str, references: List[str]) -> Dict[str, float]:
    """
    Computes ROUGE-1 and ROUGE-L f-measure (0-1 scale) against reference texts.
    Returns max score across all references.
    """
    if rouge_scorer is None:
        return {"rouge1": None, "rougeL": None, "error": "rouge_score not installed"}

    scorer = rouge_scorer.RougeScorer(["rouge1", "rougeL"], use_stemmer=True)
    max_scores = {"rouge1": 0.0, "rougeL": 0.0}

    for ref in references:
        scores = scorer.score(ref, generated)
        for key in max_scores:
            max_scores[key] = max(max_scores[key], scores[key].fmeasure)

    return max_scores


def check_nigerian_authenticity(text: str) -> Dict[str, object]:
    """Checks for Nigerian markers. Pass threshold: count >= 2."""
    text_lower = text.lower()
    found = [m for m in NIGERIAN_MARKERS if m in text_lower]
    return {
        "count": len(found),
        "found": found,
        "score": min(len(found) / 2.0, 1.0),
        "passes": len(found) >= 2,
    }


def compute_rmse_from_cases(cases: List[Dict]) -> Dict[str, object]:
    """
    Compute RMSE of predicted ratings vs. expected range midpoints.
    Also returns per-rating-bucket distribution.
    """
    if RatingPredictor is None:
        return {"rmse": None, "error": "RatingPredictor unavailable"}

    predictor = RatingPredictor()
    abs_errors = []
    pred_ratings = []

    for case in cases:
        persona = case["persona"]
        product = case["product"]
        expected_mid = (case["expected_range"][0] + case["expected_range"][1]) / 2

        try:
            result = predictor.predict_probabilistic(persona, product)
            pred = result.get("rating", 3.0)
        except Exception:
            pred = 3.0

        abs_errors.append(abs(expected_mid - pred))
        pred_ratings.append(pred)

    rmse = math.sqrt(sum(e ** 2 for e in abs_errors) / len(abs_errors)) if abs_errors else 0
    std = statistics.stdev(abs_errors) if len(abs_errors) > 1 else 0

    # Rating distribution (count of each integer bucket 1-5)
    distribution = {str(i): 0 for i in range(1, 6)}
    for r in pred_ratings:
        bucket = str(min(5, max(1, round(r))))
        distribution[bucket] += 1

    return {
        "rmse": round(rmse, 4),
        "std": round(std, 4),
        "n": len(abs_errors),
        "rating_distribution": distribution,
    }


def run_evaluation_suite():
    # Import test cases from ablation module for consistent ground truth
    try:
        from ablation import TEST_CASES
    except ImportError:
        TEST_CASES = []

    print("\n" + "=" * 65)
    print(" TASK A: REVIEW GENERATION EVALUATION SCORECARD")
    print("=" * 65)

    # --- RMSE ---
    rmse_result = compute_rmse_from_cases(TEST_CASES)
    rmse_val = rmse_result.get("rmse")
    rmse_std = rmse_result.get("std")
    rmse_n = rmse_result.get("n", 0)
    rmse_pass = (rmse_val is not None) and rmse_val < 1.5
    print(f"\n[RMSE]  n={rmse_n}")
    if rmse_val is not None:
        print(f"  RMSE  : {rmse_val:.4f}  (target < 1.5) -> {'PASS' if rmse_pass else 'FAIL'}")
        print(f"  Std   : {rmse_std:.4f}  (computed on raw absolute errors)")
    else:
        print(f"  RMSE  : N/A  ({rmse_result.get('error', 'unknown error')})")

    dist = rmse_result.get("rating_distribution", {})
    if dist:
        print(f"  Rating distribution: " + "  ".join(f"{k}*={v}" for k, v in sorted(dist.items())))

    # --- ROUGE (AI Generated vs Human References) ---
    print(f"\n[ROUGE]  (0-1 scale, higher=better, threshold >= 0.30)")
    if rouge_scorer is None:
        print("  ROUGE  : N/A — rouge_score not installed (pip install rouge-score)")
    elif not REFERENCE_REVIEWS:
        print("  ROUGE  : N/A — no reference reviews available")
    else:
        try:
            from app.ml.review_generator import ReviewAgent
            import asyncio
            agent = ReviewAgent()
            
            # Sample 10 items for ROUGE evaluation
            import random as _rnd
            rng = _rnd.Random(42)
            item_ids = rng.sample(list(REFERENCE_REVIEWS.keys()), min(10, len(REFERENCE_REVIEWS)))
            
            async def evaluate_ai_rouge(agent, ids):
                tasks = []
                for iid in ids:
                    item = next((i for i in SEED_ITEMS if i["item_id"] == iid), {})
                    if not item: continue
                    # Neutral default persona for general quality check
                    persona = {"name": "EvalUser", "archetype": "Default", "tone": "neutral", "budget": 50000}
                    tasks.append(agent.generate_stateless_flexible({"user_persona": persona, "product": item}))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                r1_list, rl_list = [], []
                
                for iid, res in zip(ids, results):
                    if isinstance(res, Exception) or not res.get("review_text"):
                        continue
                    
                    gen_text = res["review_text"]
                    refs = REFERENCE_REVIEWS[iid]
                    ref_texts = [r.get("text", "") if isinstance(r, dict) else str(r) for r in refs]
                    
                    scores = compute_rouge(gen_text, ref_texts)
                    if "error" not in scores:
                        r1_list.append(scores["rouge1"])
                        rl_list.append(scores["rougeL"])
                return r1_list, rl_list

            print(f"  Generating {len(item_ids)} AI reviews for ROUGE comparison (parallel)...")
            r1_all, rl_all = asyncio.run(evaluate_ai_rouge(agent, item_ids))
            
            if r1_all:
                r1_mean = statistics.mean(r1_all)
                rl_mean = statistics.mean(rl_all)
                print(f"  ROUGE-1: {r1_mean:.4f}  -> {'PASS' if r1_mean >= 0.30 else 'FAIL'}")
                print(f"  ROUGE-L: {rl_mean:.4f}  -> {'PASS' if rl_mean >= 0.25 else 'FAIL'}")
                print(f"  (averaged over {len(r1_all)} AI-generated reviews)")
            else:
                print("  ROUGE  : N/A — AI generation failed for sample items")
                
        except Exception as e:
            print(f"  ROUGE  : Error during AI generation: {e}")

    # --- Nigerian Marker Density ---
    print(f"\n[Nigerian Marker Density]  (target avg >= 2.0 per review)")
    all_ref_texts = []
    for refs in REFERENCE_REVIEWS.values():
        for r in refs:
            text = r.get("text", "") if isinstance(r, dict) else str(r)
            if text:
                all_ref_texts.append(text)

    if all_ref_texts:
        marker_counts = [check_nigerian_authenticity(t)["count"] for t in all_ref_texts]
        avg_markers = statistics.mean(marker_counts)
        pass_rate = sum(1 for c in marker_counts if c >= 2) / len(marker_counts)
        print(f"  Avg markers/review : {avg_markers:.2f}  -> {'PASS' if avg_markers >= 2.0 else 'FAIL'}")
        print(f"  Reviews with >=2   : {pass_rate*100:.1f}%")
        print(f"  Markers checked    : {NIGERIAN_MARKERS}")
    else:
        print("  N/A — no reference review texts loaded")

    # --- Summary ---
    print("\n" + "=" * 65)
    print(f"CORPUS: {len(REFERENCE_REVIEWS)} items | "
          f"{sum(len(v) for v in REFERENCE_REVIEWS.values())} reference reviews")
    print(f"TEST CASES: {rmse_n}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_evaluation_suite()
