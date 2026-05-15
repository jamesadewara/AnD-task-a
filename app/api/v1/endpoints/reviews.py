from fastapi import APIRouter, HTTPException
from fastapi.requests import Request
from loguru import logger
import traceback
from app.ml.review_generator import ReviewAgent, detect_markers
from app.ml.rating_predictor import RatingPredictor
from app.schemas.responses import ReviewResponse, ErrorResponse, StyleSnapshot, ReasoningStep
from fastapi.responses import StreamingResponse
from app.core.ratelimit import limiter, get_session_id, get_global_key

router = APIRouter()

import json

@router.post(
    "/generate",
    response_model=ReviewResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Generate personalized review (Stateless)",
    description="Accepts any input format/prompt and returns structured review response."
)
@limiter.limit("20/minute") # Default key_func is get_remote_address
@limiter.limit("100/hour", key_func=get_session_id)
@limiter.limit("500/day", key_func=get_global_key)
async def generate_review(request: Request):
    """Accept any input format and return structured ReviewResponse."""
    try:
        body = await request.json()
    except Exception as e:
        # If JSON parse fails, treat entire body as a message
        body = await request.body()
        body = {"message": body.decode() if isinstance(body, bytes) else str(body)}
    
    logger.info(f"Generating review from input: {str(body)[:100]}...")

    try:
        agent = ReviewAgent()
        result = await agent.generate_stateless_flexible(body)
        
        review_text = result["review_text"]
        reasoning_chain_data = result["reasoning_chain"]
        
        # Convert dicts to ReasoningStep models
        reasoning_chain = [ReasoningStep(**step) for step in reasoning_chain_data]

        predictor = RatingPredictor()
        rating = predictor.predict_flexible(review_text, body)

        # Default confidence
        confidence = 0.85
        
        # Populate Style Snapshot
        markers = detect_markers(review_text, body) if isinstance(body, dict) else []
        archetype_label = body.get("archetype", "default_consumer") if isinstance(body, dict) else "default_consumer"
        adaptation_reason = f"Review generated from input. Applied markers: {markers}" if markers else "Standard review generation."
        
        style_snapshot = StyleSnapshot(
            inferred_tone=body.get("tone", "neutral") if isinstance(body, dict) else "neutral",
            inferred_archetype=archetype_label,
            applied_markers=markers,
            adaptation_reason=adaptation_reason
        )

        return ReviewResponse(
            review_text=review_text,
            predicted_rating=rating,
            reasoning_chain=reasoning_chain,
            confidence=confidence,
            style_snapshot=style_snapshot,
            image_url=body.get("image_url") if isinstance(body, dict) else None,
            used_nigerian_markers=markers,
            sentence_count=result.get("sentence_count", 0)
        )
    except Exception as e:
        logger.error(f"Review generation failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
async def stream_review(request: Request):
    """Stream reasoning steps and final review result."""
    try:
        body = await request.json()
    except:
        body = await request.body()
        body = {"message": body.decode() if isinstance(body, bytes) else str(body)}

    agent = ReviewAgent()
    
    async def event_generator():
        try:
            async for event in agent.generate_streaming_flexible(body):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Stream failed: {e}")
            yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")