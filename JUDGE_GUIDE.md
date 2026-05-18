# Judge Testing Guide — AnD Task A

## Overview

This guide enables hackathon judges to verify all requirements of Task A:
stateless persona-driven review generation with probabilistic rating and Nigerian cultural markers.

**API Base:** `http://localhost:8000`
**Docs:** `http://localhost:8000/docs`

---

## Quick Start

```bash
git clone <repo-url>
cd AnD-task-a
cp .env.example .env          # add your OPENROUTER_API_KEY
sudo docker compose up -d --build
sleep 10
curl http://127.0.0.1:8000/api/v1/health
```

---

## Health Check

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected:
```json
{"status": "healthy"}
```

---

## Test 1: The Lagos Haggler (Price Shock)

**Validates:** price extraction → shock → low rating → outraged text
inputs can be flexible or structured (e.g. text or json)
```bash
curl -X POST http://localhost:8000/api/v1/reviews/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_persona": {
      "name": "Chinedu Okafor",
      "location": "Lagos",
      "archetype": "The Haggler",
      "interests": ["street_food", "electronics"],
      "traits": ["price_sensitive", "direct"],
      "tone": "casual",
      "style_sample": "Omo! This thing sweet die but why them go charge ₦3500? Abeg...",
      "nigerian_context": true,
      "budget": 5000,
      "price_sensitivity": "high",
      "past_reviews": [
        {"product_name": "Jollof", "rating": 3, "text": "₦3000 too much. Abeg reduce price.", "date": "2026-04-10"}
      ]
    },
    "product": {
      "name": "Oraimo FreePods 3",
      "category": "electronics",
      "description": "Bluetooth 5.3 earbuds with 30hr battery. Price: ₦24,500.",
      "price": 24500
    }
  }'
```

**Expected:**
- `predicted_rating`: 1.0–2.0
- `review_text`: leads with price outrage, uses "abeg" or "omo"
- `used_nigerian_markers`: non-empty
- `reasoning_chain`: 6 steps including `predict_rating` with shock formula
- `sentence_count`: 2–4

---

## Test 2: The Abuja Big Woman (Cold-Start Formal)

**Validates:** archetype cold-start (4.0 default), formal tone, minimal Pidgin markers

```bash
curl -X POST http://localhost:8000/api/v1/reviews/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_persona": {
      "name": "Amaka Eze",
      "location": "Abuja",
      "archetype": "Big Woman",
      "interests": ["fashion", "luxury"],
      "traits": ["quality_conscious", "formal"],
      "tone": "formal",
      "style_sample": "I commend the excellent craftsmanship. This is truly worthy of my standards.",
      "nigerian_context": true,
      "budget": 150000,
      "price_sensitivity": "low",
      "past_reviews": []
    },
    "product": {
      "name": "Ankara Wrap Dress",
      "category": "fashion",
      "description": "Handmade premium Ankara fabric wrap dress. Price: ₦45,000.",
      "price": 45000
    }
  }'
```

**Expected:**
- `predicted_rating`: 3.5–4.5 (cold-start base 4.0, minimal shock)
- `style_snapshot.adaptation_reason`: mentions "formal archetype" / "polished tone"
- `used_nigerian_markers`: empty or 1 marker max
- `review_text`: formal, no slang

---

## Test 3: PH Code-Mixer (Deep Nigerian Context)

**Validates:** style markers extracted from user's own past reviews

```bash
curl -X POST http://localhost:8000/api/v1/reviews/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_persona": {
      "name": "Emeka Nwosu",
      "location": "Port Harcourt",
      "archetype": "Community Connector",
      "interests": ["community", "food", "phones"],
      "traits": ["expressive", "communal"],
      "tone": "casual",
      "style_sample": "My people! Na fire this thing be. Abeg make una come see.",
      "nigerian_context": true,
      "budget": 30000,
      "price_sensitivity": "medium",
      "past_reviews": [
        {"product_name": "Suya", "rating": 5, "text": "Na fire! My people go love this.", "date": "2026-03-15"},
        {"product_name": "Phone case", "rating": 4, "text": "Sharp sharp delivery. No wahala at all.", "date": "2026-04-01"}
      ]
    },
    "product": {
      "name": "Tecno Spark 20",
      "category": "electronics",
      "description": "6.6\" display, 5000mAh battery. Price: ₦89,000.",
      "price": 89000
    }
  }'
```

**Expected:**
- `used_nigerian_markers`: includes markers from past reviews (e.g. "na fire", "no wahala")
- `style_snapshot.adaptation_reason`: mentions "signature markers"
- `review_text`: uses community-oriented language

---

## Test 4: Empty Product (Validation Guard)

**Validates:** 400 error returned for placeholder/empty product data

```bash
curl -X POST http://localhost:8000/api/v1/reviews/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_persona": {
      "name": "Test User",
      "interests": [],
      "traits": [],
      "tone": "neutral",
      "nigerian_context": false,
      "budget": 10000,
      "price_sensitivity": "medium"
    },
    "product": {
      "name": "string",
      "category": "string",
      "description": "string"
    }
  }'
```

**Expected:** HTTP 400 — `"Product requires valid name or description. Received placeholder data."`

---

## Key Compliance Points

| Requirement | Implementation |
|---|---|
| Stateless | No DB, no sessions — all context passed in request |
| OpenRouter Only | `OPENROUTER` proxied via `OPENROUTER_API_KEY` |
| No Datasets | Zero FAISS/vector DBs — reasoning over context only |
| Visible Reasoning | `reasoning_chain` array with 6+ structured steps |
| Probabilistic Rating | `RatingPredictor` uses `random.Random(seed)`, price shock, archetype |
| Nigerian Authenticity | Markers extracted from user's own text, persona-matched defaults |
| Anti-Hallucination | Prompt forbids any specs not in description |
