from fastapi import APIRouter, HTTPException
from loguru import logger
from app.ml.review_generator import ReviewAgent, detect_markers
from app.ml.rating_predictor import RatingPredictor
from app.schemas.responses import ReviewResponse, ErrorResponse, StyleSnapshot, ReasoningStep

router = APIRouter()


@router.post(
    "/generate",
    response_model=ReviewResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Generate personalized review (Stateless)",
    description="Stateless endpoint for hackathon judges. Takes user persona and product details, generates a review in the user's voice with visible reasoning."
)
async def generate_review(request: ReviewGenerateRequest):
    persona = request.user_persona
    product = request.product

    # FIX 1: Validate Product Input (Prevent Hallucination)
    if product.name.lower() in ["string", "", "product name"]:
        # If name is a placeholder, we proceed but the agent will handle it cautiously
        # unless description is also empty, then we reject.
        if not product.description or product.description.lower() == "string":
            raise HTTPException(
                status_code=400,
                detail="Product requires valid name or description. Received placeholder data."
            )

    logger.info(f"Generating review for product: {product.name}")

    agent = ReviewAgent()
    gen_result = await agent.generate_stateless(persona.model_dump(), product.model_dump())
    
    review_text = gen_result["review_text"]
    reasoning_chain_data = gen_result["reasoning_chain"]
    
    # Convert dicts to ReasoningStep models
    reasoning_chain = [ReasoningStep(**step) for step in reasoning_chain_data]

    predictor = RatingPredictor()
    product_desc = f"{product.name} {product.description}"
    rating = predictor.predict(product_desc, review_text, persona.model_dump(), product.model_dump())

    # Confidence logic
    confidence = 0.85
    if not product.description or product.name.lower() == "string":
        confidence = 0.60  # Drop confidence for placeholder/minimal data
    elif persona.style_sample:
        confidence = 0.92

    # Populate Style Snapshot
    markers = detect_markers(review_text)
    style_snapshot = StyleSnapshot(
        inferred_tone=persona.tone or "neutral",
        inferred_archetype=persona.traits[0] if persona.traits else "default_nigerian_consumer",
        applied_markers=markers,
        adaptation_reason="No user history provided; defaulted to neutral with Nigerian context" if not persona.traits else "Adapted to user-provided traits and tone"
    )

    return ReviewResponse(
        review_text=review_text,
        predicted_rating=rating,
        reasoning_chain=reasoning_chain,
        confidence=confidence,
        style_snapshot=style_snapshot,
        image_url=product.image_url,
        used_nigerian_markers=markers,
        sentence_count=gen_result.get("sentence_count", 0)
    )

@router.get("/health")
async def health():
    return {"status": "ok"}
