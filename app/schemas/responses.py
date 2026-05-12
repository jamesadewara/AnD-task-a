from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ErrorResponse(BaseModel):
    detail: str = Field(..., example="An error occurred processing your request.")

class StyleSnapshot(BaseModel):
    inferred_tone: str = Field(..., example="casual")
    inferred_archetype: str = Field(..., example="default_nigerian_consumer")
    applied_markers: List[str] = Field(default_factory=list, example=["omo", "abeg"])
    adaptation_reason: str = Field(..., example="No user history; defaulted to neutral with Nigerian context")

class ReasoningStep(BaseModel):
    step: str = Field(..., example="reason")
    action: str = Field(..., example="Analyzed product against user archetype")
    output: str = Field(..., example="Tone: neutral. Nigerian context: true.")

class ReviewResponse(BaseModel):
    review_text: str = Field(..., example="Omo, this item make sense die! I completely love the vibe.")
    predicted_rating: float = Field(..., example=4.5)
    reasoning_chain: List[ReasoningStep] = Field(default_factory=list, description="Structured agent steps")
    confidence: float = Field(..., example=0.92)
    style_snapshot: StyleSnapshot
    image_url: Optional[str] = Field(None, example="https://images.example.com/product-123.jpg")
    used_nigerian_markers: List[str] = Field(default_factory=list, example=["omo", "abeg"])
    sentence_count: int = Field(..., example=5)