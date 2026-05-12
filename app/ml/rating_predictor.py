import random
import math
import re
from loguru import logger

def extract_price(description: str) -> float:
    """
    Parses price from description text. 
    Handles patterns like ₦24,500, N24,500, Price: 24,500 with commas.
    """
    if not description:
        return 0.0
    # Pattern: currency symbol or "Price:" followed by optional currency and numbers/commas
    pattern = r"(?:Price:?|₦|N)\s*(?:₦|N)?\s*([\d,]+(?:\.\d+)?)"
    match = re.search(pattern, description, re.IGNORECASE)
    if not match:
        return 0.0
    
    price_str = match.group(1).replace(",", "")
    try:
        return float(price_str)
    except ValueError:
        return 0.0

def archetype_base_rating(archetype: str) -> float:
    """
    Returns default rating based on persona archetype for cold-start scenarios.
    Haggler=2.5, Big Woman=4.0, default=3.0.
    """
    archetype = archetype.lower()
    if "haggler" in archetype:
        return 2.5
    if "big woman" in archetype:
        return 4.0
    return 3.0

class RatingPredictor:
    def __init__(self):
        pass

    def predict_probabilistic(self, persona: dict, product: dict) -> dict:
        """
        Builds a rating distribution from user history, computes price shock,
        and samples a deterministic rating.
        """
        # 1. Local Random Instance for Reproducibility (fixes global seed corruption)
        seed_str = f"{persona.get('name', 'user')}_{product.get('name', 'product')}"
        rng = random.Random(seed_str)

        # 2. Base Distribution from History
        past_reviews = persona.get("past_reviews", [])
        # Extract archetype once for reuse
        archetype = (persona.get("archetype") or (persona.get("traits", [""])[0] if persona.get("traits") else "default")).lower()
        
        if past_reviews:
            # Extract ratings safely from Review objects (dicts in persona)
            ratings = []
            for r in past_reviews:
                if isinstance(r, dict):
                    ratings.append(r.get("rating", 4.0))
                else:
                    # Handle pydantic object if passed directly
                    ratings.append(getattr(r, "rating", 4.0))
            
            mean = sum(ratings) / len(ratings)
            # Calculate standard deviation
            variance = sum((x - mean) ** 2 for x in ratings) / len(ratings)
            std = math.sqrt(variance) if variance > 0 else 0.5
        else:
            # 3. Cold-start mean based on archetype (Haggler=2.5, Big Woman=4.0, default=3.0)
            mean = archetype_base_rating(archetype)
            std = 0.6

        # 4. Price Shock Computation
        description = product.get("description", "")
        price = extract_price(description)
        price_found = price > 0
        
        if not price_found:
            # Log a warning and default ratio to 1.0 (no shock) rather than crashing log2
            logger.warning(f"[RatingPredictor] Price not found or zero in description for product '{product.get('name', 'unknown')}'.")
        
        budget = persona.get("budget", 1.0) # Avoid div by zero
        sensitivity = persona.get("price_sensitivity", "medium").lower()

        ratio = price / budget if (budget > 0 and price > 0) else 1.0
        # log2 shock: 2x price = 1 point drop, 4x price = 2 point drop
        shock_base = math.log2(ratio) if ratio > 1.0 else 0.0
        
        amplifier = 1.0
        if "haggler" in archetype:
            amplifier += 1.5
        if sensitivity == "high":
            amplifier += 1.0
        
        total_shock = shock_base * amplifier
        formula = f"shock = log2({price}/{budget}) * {amplifier:.1f}"
        
        adjusted_mean = mean - total_shock
        # Ensure it stays within 1-5 bounds
        adjusted_mean = max(1.0, min(5.0, adjusted_mean))
        
        # 5. Sampling from Adjusted Distribution (using local rng.gauss)
        sampled = rng.gauss(adjusted_mean, std)
        final_rating = round(sampled * 2) / 2
        final_rating = max(1.0, min(5.0, final_rating))
        
        logger.debug(f"[RatingPredictor] Archetype: {archetype}, Mean: {mean:.1f}, Shock: {total_shock:.1f}, Final: {final_rating}")
        
        return {
            "rating": float(final_rating),
            "formula": formula,
            "shock": float(total_shock),
            "base_mean": float(mean),
            "adjusted_mean": float(adjusted_mean),
            "price_found": price_found,
            "ratio": float(ratio)
        }

    def predict(self, product_description: str, review_text: str, persona: dict = None, product: dict = None) -> float:
        # Legacy fallback method - redirect to probabilistic for consistency
        persona = persona or {}
        product = product or {}
        
        # Ensure description is in product for probabilistic to parse price
        if "description" not in product or not product["description"]:
            product["description"] = product_description
        
        res = self.predict_probabilistic(persona, product)
        return res["rating"]
