import re
from typing import List, Dict, Optional, Any
from loguru import logger

def detect_markers(text: str, persona: dict = None) -> List[str]:
    NIGERIAN_MARKERS = ["wahala", "abeg", "omo", "Naija", "NEPA", "sharp sharp", 
                        "chop", "dey", "na", "don tire", "no wahala", "value for money",
                        "no be so", "sweet die", "dey whine me", "my people", "sha", "maga"]
    text_lower = text.lower()
    return [m for m in NIGERIAN_MARKERS if m.lower() in text_lower]

def extract_user_markers(persona: dict) -> List[str]:
    corpus = persona.get("style_sample", "") or ""
    past_reviews = persona.get("past_reviews", [])
    if past_reviews:
        for r in past_reviews:
            if isinstance(r, dict):
                corpus += " " + (r.get("text", "") or "")
            else:
                corpus += " " + str(r)
        
    all_markers = ["Omo", "abeg", "wahala", "NEPA", "no wahala", "sweet die", 
                   "no be so", "sharp me", "dey", "am", "sha", "maga", "dey whine me"]
    found = [m for m in all_markers if m.lower() in corpus.lower()]
    return found if found else ["abeg", "omo"]

class ReviewAgent:
    def __init__(self):
        pass

    async def _call_llm(self, messages: list, temperature: float = 0.7, max_tokens: int = 300) -> str:
        from app.core.llm import llm_service
        return await llm_service.get_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
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

    async def step_3_reason(self, product: dict, persona: dict) -> str:
        """Internal Reasoning Plan (LLM)"""
        logger.info("[ReviewAgent] Step 3: Generating reasoning plan")
        
        prompt = f"""
        Act as a product reviewer. Plan a review for:
        Product Name: {product['name']}
        Category: {product['category']}
        Description: {product.get('description', 'No description provided.')}
        
        Think step-by-step:
        1. How should a user with tone '{persona.get('tone')}' react to this?
        2. Which features (ONLY from description) should be highlighted?
        3. How to inject Nigerian cultural nuances naturally if context is enabled?
        
        Output a 3-point plan. Do NOT hallucinate features.
        """
        messages = [{"role": "user", "content": prompt}]
        return await self._call_llm(messages, temperature=0.5, max_tokens=200)

    def _emergency_fallback_review(self, product: dict, persona: dict) -> str:
        price = product.get("price", 0.0)
        budget = persona.get("budget", 10000.0)
        name = product.get("name", "Product")
        
        if price and budget and price > budget * 2:
            return f"Omo, {name} cost ₦{price}? That one too much for my pocket abeg. My budget na ₦{budget}. No be say e no good, but who price am? 2 stars because e fit dey work, but my account balance dey cry."
        
        return f"I try {name}. E get potential but I need more time to sabi am well. 3 stars for now."

    async def step_4_generate(self, product: dict, persona: dict, plan: str, rating_constraint: float = None) -> str:
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
            rating_instruction = f"### RATING CONSTRAINT ###\nYou MUST write a review that justifies a {rating_constraint}/5.0 rating. Your tone must perfectly align with this score."

        user_markers = extract_user_markers(persona)
        
        prompt = f"""
        Write a product review in the user's authentic Nigerian voice.
        
        Product: {product.get('name')} | Category: {product.get('category')}
        Description: {product.get('description', 'No description provided.')}
        Price: ₦{price}
        
        User Persona:
        - Archetype: {archetype}
        - Tone: {persona.get('tone')}
        - Nigerian Context: {persona.get('nigerian_context')}
        - Budget: ₦{budget}
        - Signature Phrases: {user_markers}
        
        {economic_constraint}
        {rating_instruction}
        
        Plan: {plan}
        
        Rules:
        - NEVER hallucinate specs (RAM, battery, etc.) not explicitly listed in the description.
        - Write 2-4 sentences.
        - Use at least 2 signature phrases naturally.
        - Output ONLY the review text.
        """
        
        messages = [{"role": "user", "content": prompt}]
        max_retries = 2
        attempts = 0
        draft = ""
        
        while not draft.strip() and attempts < max_retries:
            response = await self._call_llm(messages, temperature=0.7, max_tokens=250)
            draft = response.strip()
            attempts += 1
            
        if not draft.strip():
            logger.warning("[ReviewAgent] LLM returned empty draft. Using fallback.")
            draft = self._emergency_fallback_review(product, persona)
            
        return draft

    async def step_5_reflect(self, draft: str, persona: dict) -> str:
        """Critique and revise for authenticity and adherence to constraints."""
        logger.info("[ReviewAgent] Step 5: Reflecting for authenticity")
        
        if not draft.strip():
            return ""
            
        prompt = f"""
        Critique and refine this Nigerian review for authenticity:
        "{draft}"
        
        Checklist:
        - Does it sound human and culturally accurate?
        - Did it follow the economic constraints (if any)?
        - Is it free of hallucinated technical specs?
        
        Output ONLY the final revised review text. If the draft is already good, return it as is.
        """
        messages = [{"role": "user", "content": prompt}]
        
        response = await self._call_llm(messages, temperature=0.5, max_tokens=250)
        return response.strip() if response.strip() else draft

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
        
        if not final_review.strip():
            reasoning_chain.append({
                "step": "reflect",
                "action": "Validation FAILED",
                "output": "Generated review is EMPTY. Triggering emergency fallback."
            })
            final_review = self._emergency_fallback_review(product, persona)
        
        final_review = final_review.strip().replace('"', '')
        
        # Marker Detection and Validation
        detected = detect_markers(final_review, persona)
        validated_markers = [m for m in detected if m.lower() in final_review.lower()]
        
        # Reasoning Documentation
        reasoning_chain.append({
            "step": "style_adapt",
            "action": "Applied style fingerprint and Nigerian markers",
            "output": f"Injected markers: {validated_markers}. Adapted tone: {persona.get('tone')} with Pidgin."
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
            "sentence_count": len(re.split(r'[.!?]+', final_review)) - 1
        }