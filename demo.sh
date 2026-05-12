#!/bin/bash
# demo.sh — Full smoke test for AnD Task A
# Usage: bash demo.sh

set -e

echo "=========================================="
echo " AnD Task A — Demo & Smoke Test"
echo "=========================================="

# 1. Start services
echo ""
echo "[1/4] Starting docker-compose..."
docker-compose up --build -d

# 2. Wait for startup
echo "[2/4] Waiting 10s for service to be ready..."
sleep 10

# 3. Health check
echo "[3/4] Health check..."
HEALTH=$(curl -s http://localhost:8000/health)
echo "Health: $HEALTH"

if echo "$HEALTH" | grep -q "healthy"; then
  echo "  ✓ Service is healthy"
else
  echo "  ✗ Health check FAILED"
  docker-compose logs task-a
  exit 1
fi

# 4. Sample Haggler curl
echo ""
echo "[4/4] Running Haggler test payload..."
curl -s -X POST http://localhost:8000/api/v1/reviews/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_persona": {
      "name": "Chinedu Okafor",
      "location": "Lagos",
      "archetype": "The Haggler",
      "interests": ["electronics"],
      "traits": ["price_sensitive"],
      "tone": "casual",
      "style_sample": "Omo! Why dem go charge that much? Abeg no be so.",
      "nigerian_context": true,
      "budget": 5000,
      "price_sensitivity": "high",
      "past_reviews": [
        {"product_name": "Jollof", "rating": 3, "text": "Too expensive abeg.", "date": "2026-04-10"}
      ]
    },
    "product": {
      "name": "Oraimo FreePods 3",
      "category": "electronics",
      "description": "Bluetooth 5.3 earbuds with 30hr battery. Price: N24,500.",
      "price": 24500
    }
  }' | python -m json.tool

echo ""
echo "=========================================="
echo " Demo complete. Check output above."
echo " Full judge test guide: JUDGE_GUIDE.md"
echo "=========================================="
