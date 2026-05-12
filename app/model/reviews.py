from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Review(BaseModel):
    product_name: str
    rating: int
    text: str
    date: str

class UserPersona(BaseModel):
    name: str = "Anonymous User"
    interests: List[str] = []
    traits: List[str] = []
    tone: str = "neutral"
    style_sample: str = ""
    nigerian_context: bool = True
    past_reviews: List[Review] = []
    budget: float = 0.0
    archetype: str = ""
    price_sensitivity: str = ""

class ProductDetails(BaseModel):
    name: str
    category: str
    description: Optional[str] = ""
    image_url: Optional[str] = None
    price: float = 0.0

class ReviewGenerateRequest(BaseModel):
    user_persona: UserPersona
    product: ProductDetails