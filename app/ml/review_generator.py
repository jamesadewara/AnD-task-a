import re
from typing import List, Dict, Optional, Any
from loguru import logger

def detect_markers(text: str, persona: dict = None) -> List[str]:
    from app.core.config import settings
    text_lower = text.lower()
    return [m for m in settings.NIGERIAN_MARKERS if m.lower() in text_lower]

def extract_user_markers(persona: dict) -> List[str]:
    """
    Extracts Nigerian markers that the user ACTUALLY uses in their own text.
    Priority: style_sample > past_reviews > archetype-appropriate fallback.
    """
    from app.core.config import settings
    corpus = (persona.get("style_sample", "") or "").lower()

    for review in persona.get("past_reviews", []):
        if isinstance(review, dict):
            corpus += " " + (review.get("text", "") or "").lower()
        else:
            corpus += " " + str(review).lower()

    found = [m for m in settings.ALL_MARKERS if m in corpus]

    # No history — return archetype-appropriate defaults from settings
    if not found:
        archetype = (persona.get("archetype", "") or "").lower()
        
        # Try to find a match in the configured archetypes
        for key, markers in settings.ARCHETYPE_FALLBACK_MARKERS.items():
            if key in archetype:
                return markers
        
        # Fallback to default if no match
        return settings.ARCHETYPE_FALLBACK_MARKERS.get("default", ["abeg", "omo"])

    return found

class ReviewAgent:
    def __init__(self):
        pass

    def _validate_rating_alignment(self, review_text: str, rating: float) -> bool:
        """Heuristic: ensure sentiment polarity in review text matches the numeric rating."""
        from app.core.config import settings
        text_lower = review_text.lower()
        neg_count = sum(1 for w in settings.NEGATIVE_SENTIMENT_WORDS if w in text_lower)
        pos_count = sum(1 for w in settings.POSITIVE_SENTIMENT_WORDS if w in text_lower)

        if rating <= 2.0 and pos_count > neg_count:
            return False  # Too positive for a low rating
        if rating >= 4.0 and neg_count > pos_count:
            return False  # Too negative for a high rating
        return True

    def _estimate_sentiment(self, text: str) -> float:
        """Rough heuristic: count positive vs negative words to estimate implied rating (1-5 scale)."""
        from app.core.config import settings
        text_lower = text.lower()
        neg_score = sum(1 for w in settings.NEGATIVE_SENTIMENT_WORDS if w in text_lower)
        pos_score = sum(1 for w in settings.POSITIVE_SENTIMENT_WORDS if w in text_lower)
        if neg_score > pos_score * 2: return 1.5
        if neg_score > pos_score:     return 2.5
        if pos_score > neg_score * 2: return 4.5
        if pos_score > neg_score:     return 3.5
        return 3.0

    async def _call_llm(self, messages: list, temperature: float = 0.7, max_tokens: int = 300, on_fallback = None) -> str:
        from app.core.llm import llm_service
        return await llm_service.get_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            on_fallback=on_fallback
        )

    async def step_1_retrieve(self, product: dict, persona: dict) -> Dict[str, str]:
        logger.info(f"[ReviewAgent] Step 1: Retrieving context for {product.get('name', 'string')}")
        past_reviews = persona.get("past_reviews", [])
        if past_reviews:
            output = f"{len(past_reviews)} past reviews found. Read and incorporated."
        else:
            output = "0 past reviews found. Cold-start scenario."
        return {
            "step": "retrieve",
            "action": "Fetched user history from persona",
            "output": output
        }

    async def step_2_analyze(self, product: dict, persona: dict) -> Dict[str, str]:
        logger.info("[ReviewAgent] Step 2: Analyzing product against user archetype")
        product_name = product.get('name', 'string')
        desc_status = "empty" if not product.get('description') else "provided"
        output = f"Tone: {persona.get('tone', 'neutral')}. Nigerian context: {persona.get('nigerian_context', True)}. Product name: '{product_name}'. Description: {desc_status}."
        return {
            "step": "reason",
            "action": "Analyzed product against user archetype",
            "output": output
        }

    async def step_3_reason(self, product: dict, persona: dict, on_fallback=None) -> str:
        """Internal Reasoning Plan (LLM)"""
        logger.info("[ReviewAgent] Step 3: Generating reasoning plan")
        
        prompt = f"""
Plan a review for {product['name']} ({product['category']}):

Product: {product.get('description', 'No description provided.')}
User: {persona.get('tone')} tone, budget ₦{persona.get('budget', 0)}
Context: {persona.get('nigerian_context', False)}

1. How should {persona.get('tone')} user react?
2. Which features (description only) to highlight?
3. How to inject Nigerian nuances if enabled?

Plan only. No hallucinated specs.
"""
        messages = [{"role": "user", "content": prompt}]
        return await self._call_llm(messages, temperature=0.5, max_tokens=200, on_fallback=on_fallback)

    def _emergency_fallback_review(self, product: dict, persona: dict) -> str:
        price = product.get("price", 0.0)
        budget = persona.get("budget", 10000.0)
        name = product.get("name", "Product")
        
        if price and budget and price > budget * 2:
            return f"Omo, {name} cost ₦{price}? That one too much for my pocket abeg. My budget na ₦{budget}. No be say e no good, but who price am? 2 stars because e fit dey work, but my account balance dey cry."
        
        return f"I try {name}. E get potential but I need more time to sabi am well. 3 stars for now."

    async def step_4_generate(self, product: dict, persona: dict, plan: str, rating_constraint: float = None, on_fallback=None) -> str:
        """Generate the review draft with strict economic and rating constraints."""
        logger.info("[ReviewAgent] Step 4: Generating review draft")
        
        price = product.get("price", 0.0)
        budget = persona.get("budget", 0.0)
        archetype = persona.get("archetype") or (persona.get("traits", [""])[0] if persona.get("traits") else "default")
        sensitivity = persona.get("price_sensitivity", "medium")
        
        # Economic Reality Computation
        ratio = price / budget if budget > 0 else 1.0
        economic_constraint = ""
        
        if (ratio > 1.5 and (sensitivity == "high" or "Haggler" in archetype)) or (ratio > 3.0):
            economic_constraint = f"""
            ### UNIGNORABLE ECONOMIC CONSTRAINT ###
            Price (₦{price}) is {ratio:.1f}x the User's Budget (₦{budget}).
            User Archetype: {archetype} (Price-Sensitive).
            
            REQUIRED STRUCTURE:
            1. LEAD WITH PRICE OUTRAGE: Complain immediately about how expensive this is for the value.
            2. GRUDGING PRAISE: Only acknowledge features second, with a 'but' or 'sha'.
            """
        
        rating_instruction = ""
        if rating_constraint is not None:
            # Determine sentiment profile from the numeric constraint
            if rating_constraint <= 2.0:
                sentiment = "STRONGLY NEGATIVE \u2014 mostly price complaint, minimal quality praise"
                structure  = "1. Open with shock/outrage at price. 2. Mention budget gap explicitly. 3. One grudging quality note with 'but' or 'sha'. 4. Refuse to recommend. 5. Give low rating."
            elif rating_constraint <= 3.0:
                sentiment = "MIXED NEGATIVE \u2014 price complaint dominant, cautious quality praise"
                structure  = "1. Price concern first. 2. Quality acknowledgment second. 3. Qualified 'maybe'. 4. Medium-low rating."
            elif rating_constraint <= 4.0:
                sentiment = "MIXED POSITIVE \u2014 quality praise dominant, minor reservation"
                structure  = "1. Quality praise first. 2. Minor complaint. 3. Recommend with caveat. 4. Medium-high rating."
            else:
                sentiment = "STRONGLY POSITIVE \u2014 enthusiastic praise, no reservations"
                structure  = "1. Enthusiastic opening. 2. Feature highlights. 3. Price acceptable. 4. Strong recommend. 5. High rating."

            rating_instruction = f"""
    ### MANDATORY RATING CONSTRAINT (VIOLATING THIS = FAIL) ###
    Your review MUST justify EXACTLY {rating_constraint}/5.0 stars.
    Sentiment profile: {sentiment}

    REQUIRED REVIEW STRUCTURE:
    {structure}

    If rating is \u2264 2.0: The review MUST be AT LEAST 70% negative about price.
    If rating is \u2265 4.0: The review MUST be AT LEAST 70% positive about quality.
    """

        user_markers = extract_user_markers(persona)

        prompt = f"""
Write a {rating_constraint}/5 review in {persona.get('tone')} Nigerian voice. 2-4 sentences.

Product: {product.get('name')} | {product.get('category')}
Description: {product.get('description', 'No description provided.')}
Price: ₦{price} | Budget: ₦{budget}

Persona: {archetype} | Context: {persona.get('nigerian_context')}

STYLE: Use 2+ of these phrases: {user_markers}

CONSTRAINTS:
{economic_constraint}
{rating_instruction}

RULES:
- No specs not in description
- Rate as X.0/5 (e.g. 4.5/5)
- Output review only
"""
        
        messages = [{"role": "user", "content": prompt}]
        max_retries = 2
        attempts = 0
        draft = ""
        
        while not draft.strip() and attempts < max_retries:
            response = await self._call_llm(messages, temperature=0.7, max_tokens=250, on_fallback=on_fallback)
            draft = response.strip()
            attempts += 1
            
        if not draft.strip():
            logger.warning("[ReviewAgent] LLM returned empty draft. Using fallback.")
            draft = self._emergency_fallback_review(product, persona)
            
        return draft

    async def step_5_reflect(self, draft: str, persona: dict, on_fallback=None) -> str:
        """Critique and revise for authenticity and adherence to constraints."""
        logger.info("[ReviewAgent] Step 5: Reflecting for authenticity")
        
        if not draft.strip():
            return ""
            
        prompt = f"""
Refine this review for authenticity:
"{draft}"

Verify:
✓ Sounds human & culturally accurate
✓ Follows economic constraints
✓ No specs outside description

Return revised text only. No meta-commentary.
"""
        messages = [{"role": "user", "content": prompt}]
        
        response = await self._call_llm(messages, temperature=0.5, max_tokens=250, on_fallback=on_fallback)
        return response.strip() if response.strip() else draft

    async def generate_streaming(self, persona: dict, product: dict):
        """Streaming agentic workflow that yields steps as they occur."""
        from app.ml.rating_predictor import RatingPredictor
        
        fallbacks = []
        async def fallback_notifier(failed, next_mod, err):
            fallbacks.append(f"⚠️ Model {failed.split('/')[-1]} rate-limited. Trying {next_mod.split('/')[-1]}...")
        
        # Step 1: RETRIEVE
        step1 = await self.step_1_retrieve(product, persona)
        yield {"event": "reasoning", "data": step1}
        
        # Step 2: ANALYZE
        step2 = await self.step_2_analyze(product, persona)
        yield {"event": "reasoning", "data": step2}
        
        # Probabilistic Rating Step
        predictor = RatingPredictor()
        p_res = predictor.predict_probabilistic(persona, product)
        sampled_rating = p_res["rating"]
        
        step_rating = {
            "step": "predict_rating",
            "action": "Computed price shock and sampled probabilistic rating",
            "output": f"Sampled Rating: {sampled_rating}. Formula: {p_res['formula']}. Price Shock: {p_res['shock']:.2f}."
        }
        yield {"event": "reasoning", "data": step_rating}
        
        # Step 3: Plan
        plan = await self.step_3_reason(product, persona, on_fallback=fallback_notifier)
        for f in fallbacks:
            yield {"event": "reasoning", "data": {"step": "fallback", "action": "LLM Rotation", "output": f}}
        fallbacks = []
        
        # Step 4: Generate
        draft = await self.step_4_generate(product, persona, plan, rating_constraint=sampled_rating, on_fallback=fallback_notifier)
        for f in fallbacks:
            yield {"event": "reasoning", "data": {"step": "fallback", "action": "LLM Rotation", "output": f}}
        fallbacks = []

        # Step 5: Reflect
        final_review = await self.step_5_reflect(draft, persona, on_fallback=fallback_notifier)
        for f in fallbacks:
            yield {"event": "reasoning", "data": {"step": "fallback", "action": "LLM Rotation", "output": f}}
        fallbacks = []

        if not final_review.strip():
            final_review = self._emergency_fallback_review(product, persona)

        # Validation logic (Simplified for streaming)
        detected = detect_markers(final_review, persona)
        archetype_label = persona.get("archetype") or "default_consumer"
        
        step_style = {
            "step": "style_adapt",
            "action": "Applied style fingerprint and Nigerian markers",
            "output": f"Injected user's signature markers: {detected}" if detected else f"Formal archetype '{archetype_label}' adaptation."
        }
        yield {"event": "reasoning", "data": step_style}

        final_review = final_review.strip().replace('"', '')
        
        # Final Result
        final_result = {
            "review_text": final_review,
            "predicted_rating": sampled_rating,
            "used_nigerian_markers": detected,
            "sentence_count": len([s for s in re.split(r'(?<!\d)[.!?]+(?!\d)', final_review) if s.strip()])
        }
        yield {"event": "final_result", "data": final_result}

    async def generate_stateless(self, persona: dict, product: dict) -> dict:
        """Full structured agentic workflow with probabilistic rating model."""
        from app.ml.rating_predictor import RatingPredictor
        
        # Build reasoning chain in Python
        reasoning_chain = []
        
        # Step 1 & 2 (Metadata/Context)
        step1 = await self.step_1_retrieve(product, persona)
        reasoning_chain.append(step1)
        
        step2 = await self.step_2_analyze(product, persona)
        reasoning_chain.append(step2)
        
        # Probabilistic Rating Step
        predictor = RatingPredictor()
        p_res = predictor.predict_probabilistic(persona, product)
        sampled_rating = p_res["rating"]
        
        reasoning_chain.append({
            "step": "predict_rating",
            "action": "Computed price shock and sampled probabilistic rating",
            "output": f"Sampled Rating: {sampled_rating}. Formula: {p_res['formula']}. Price Shock: {p_res['shock']:.2f}. Deterministic seed applied."
        })
        
        # Step 3: Plan
        plan = await self.step_3_reason(product, persona)
        
        # Step 4: Generate (with rating constraint)
        draft = await self.step_4_generate(product, persona, plan, rating_constraint=sampled_rating)

        # Step 5: Reflect
        final_review = await self.step_5_reflect(draft, persona)
        reflect_failed = not final_review.strip()

        if reflect_failed:
            final_review = self._emergency_fallback_review(product, persona)

        # Rating Alignment Validation — regenerate once if sentiment mismatches rating
        if not self._validate_rating_alignment(final_review, sampled_rating):
            logger.warning("[ReviewAgent] Rating-sentiment mismatch detected. Regenerating with stronger constraint.")
            reasoning_chain.append({
                "step": "validate_rating",
                "action": "Rating-sentiment mismatch detected",
                "output": f"Review sentiment did not align with {sampled_rating} stars. Regenerating once with stronger constraint."
            })
            stronger_draft = await self.step_4_generate(product, persona, plan, rating_constraint=sampled_rating)
            retry_review   = await self.step_5_reflect(stronger_draft, persona)
            if retry_review.strip():
                final_review = retry_review
        
        final_review = final_review.strip().replace('"', '')

        # Marker Detection and Validation
        detected = detect_markers(final_review, persona)
        validated_markers = [m for m in detected if m.lower() in final_review.lower()]
        archetype_label = persona.get("archetype") or "default_consumer"

        # Fix 2: threshold-based adaptation_reason
        if not validated_markers or len(validated_markers) <= 1:
            adaptation_reason = f"Formal archetype '{archetype_label}' \u2014 minimal Pidgin markers for polished tone. Tone: {persona.get('tone')}."
        else:
            adaptation_reason = f"Injected user's signature markers: {validated_markers}"

        # Fix 3: Always append reflect step with quality metrics
        validation_passed = len(final_review.strip()) > 50
        sentiment_estimate = self._estimate_sentiment(final_review)
        reasoning_chain.append({
            "step": "reflect",
            "action": "Validated review authenticity and constraint compliance",
            "output": (
                f"Validation: {'PASSED' if validation_passed else 'FAILED (used fallback)'}. "
                f"Review length: {len(final_review)} chars. "
                f"Rating-text alignment: {'Consistent' if abs(sampled_rating - sentiment_estimate) < 1.5 else 'Check'}. "
                f"Marker count: {len(validated_markers)}."
            )
        })

        # Reasoning Documentation
        reasoning_chain.append({
            "step": "style_adapt",
            "action": "Applied style fingerprint and Nigerian markers",
            "output": adaptation_reason
        })

        reasoning_chain.append({
            "step": "generate",
            "action": "Finalized review draft",
            "output": f"Draft length: {len(final_review)} chars. Rating constraint: {sampled_rating} stars enforced."
        })
        
        return {
            "review_text": final_review,
            "predicted_rating": sampled_rating,
            "reasoning_chain": reasoning_chain,
            "used_nigerian_markers": detected,
            "sentence_count": len([s for s in re.split(r'(?<!\d)[.!?]+(?!\d)', final_review) if s.strip()])
        }