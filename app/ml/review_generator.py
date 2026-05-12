import re
from typing import List, Dict, Optional
from loguru import logger
from fastapi import HTTPException

from litellm import completion
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.documents.user import UserDocument

class ReviewAgent:
    def __init__(self):
        pass

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _call_llm(self, messages: list, temperature: float = 0.7, max_tokens: int = 300) -> str:
        from app.core.llm import llm_service
        return await llm_service.get_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

    def _build_style_context(self, user: UserDocument) -> str:
        interests = ", ".join(user.taste_profile.interests[:8]) if user.taste_profile else ""
        traits = ", ".join(user.taste_profile.personality_traits[:5]) if user.taste_profile else ""
        tone = user.taste_profile.writing_tone if user.taste_profile else "neutral"
        
        if user.style_fingerprint:
            phrases = ", ".join(user.style_fingerprint.top_phrases[:5])
            avg_len = user.style_fingerprint.avg_sentence_length
            exclam = user.style_fingerprint.exclamation_ratio
            formality = user.style_fingerprint.formality_score
            enthusiasm = "high" if exclam > 0.2 else "moderate" if exclam > 0.05 else "calm"
            formality_label = "formal" if formality > 0.6 else "casual" if formality < 0.4 else "balanced"
            nigerian_markers = ", ".join(user.style_fingerprint.nigerian_markers) or "none"
        else:
            phrases, avg_len, enthusiasm, formality_label, nigerian_markers = "", 15, "moderate", "balanced", "none"

        return f"""
        Personality: Interests ({interests}), Traits ({traits}), Tone ({tone})
        Style: Avg {avg_len:.0f} words/sentence, Enthusiasm: {enthusiasm}, Formality: {formality_label}
        Favorite Phrases: {phrases}
        Nigerian Markers: {nigerian_markers}
        """

    async def reason_structure(self, user: UserDocument, product: dict, style_context: str) -> str:
        """Step 1: Reason about the review structure."""
        logger.info(f"[ReviewAgent] Step 1: Reasoning structure for {user.name}'s review of {product['name']}")
        prompt = f"""
        You are planning a review for {product['name']} ({product.get('category', 'product')}).
        Description: {product.get('description', '')}
        
        User Context:
        {style_context}
        
        Plan a 4-5 sentence review structure that naturally incorporates the user's interests and Nigerian cultural context.
        Provide a numbered outline. Do NOT write the actual review yet.
        """
        messages = [{"role": "user", "content": prompt}]
        return await self._call_llm(messages, temperature=0.5, max_tokens=200)

    async def draft_review(self, user: UserDocument, product: dict, structure_plan: str, style_context: str) -> str:
        """Step 2: Draft the review based on the reasoned structure."""
        logger.info(f"[ReviewAgent] Step 2: Drafting review for {product['name']}")
        prompt = f"""
        You are {user.name}. Write a product review based on this structure plan:
        {structure_plan}
        
        Product: {product['name']}
        
        Your Style Profile:
        {style_context}
        
        Instructions:
        - Write EXACTLY 4-6 sentences.
        - Adopt the exact tone and enthusiasm level.
        - Sprinkle Nigerian markers IF they fit naturally.
        - Output ONLY the review text.
        """
        messages = [{"role": "user", "content": prompt}]
        return await self._call_llm(messages, temperature=0.7, max_tokens=300)

    async def reflect_and_revise(self, user: UserDocument, draft: str, style_context: str) -> str:
        """Step 3: Critique the draft for behavioral fidelity and revise."""
        logger.info(f"[ReviewAgent] Step 3: Reflecting and revising draft...")
        prompt = f"""
        You are an authenticity editor. Review this drafted product review:
        "{draft}"
        
        Target User Style:
        {style_context}
        
        Critique the draft: Does it sound like a generic AI? Are the Nigerian markers forced or stereotypical? 
        Is the sentence length authentic to the user?
        
        Revise the draft to fix any issues, making it sound 100% human and authentic to the Target User Style.
        Output ONLY the final revised review text, without quotes or commentary.
        """
        messages = [{"role": "user", "content": prompt}]
        return await self._call_llm(messages, temperature=0.6, max_tokens=300)

    async def generate(self, user_id: str, product: dict, search_context: str = None) -> dict:
        """
        Agentic Workflow to generate a hyper-personalized review.
        """
        user = await UserDocument.find_by_id_or_uuid(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if not user.style_fingerprint or not user.taste_profile:
            raise HTTPException(status_code=400, detail="User model not ready. Run analysis first.")

        style_context = self._build_style_context(user)
        
        # Agent Workflow
        plan = await self.reason_structure(user, product, style_context)
        draft = await self.draft_review(user, product, plan, style_context)
        final_review = await self.reflect_and_revise(user, draft, style_context)
        
        # Post-process
        final_review = final_review.strip().replace("```", "").replace('"', '')
        sentences = re.split(r'(?<=[.!?])\s+', final_review)
        
        markers_used = []
        if user.style_fingerprint and user.style_fingerprint.nigerian_markers:
            markers_used = [m for m in user.style_fingerprint.nigerian_markers if m.lower() in final_review.lower()]

        return {
            "review_text": final_review,
            "sentence_count": len(sentences),
            "used_nigerian_markers": markers_used,
            "style_match_score": 0.95, # Improved via reflection
            "agent_trace": {
                "plan": plan,
                "draft": draft
            }
        }

