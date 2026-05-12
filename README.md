# AnD Task A: User Modeling Agent

This repository contains the stateless User Modeling Agent for the AnD Hackathon. It is designed to generate authentic, culturally-relevant product reviews based on user personas and product details.

## 🚀 Features
- **Stateless Architecture**: No database or session storage.
- **OpenRouter SDK**: Native integration for high-performance agentic reasoning.
- **Multi-Model Failover**: Automatic rotation between GLM-4.5, Nemotron-3, and Gemma-4 to ensure 100% uptime.
- **5-Step Agentic Workflow**:
  1. **Retrieve**: Context gathering from input details.
  2. **Analyze**: Style fingerprinting and taste profile extraction.
  3. **Reason**: Chain of Thought planning.
  4. **Generate**: Persona-aligned review drafting.
  5. **Reflect**: Authenticity critique and refinement.

## 🛠️ Tech Stack
- **FastAPI**: Lightweight API framework.
- **OpenRouter SDK**: Official Python SDK for model access.
- **Pydantic**: Data validation and schemas.

## 🚦 Getting Started

### 1. Environment Setup
Clone the example environment and add your OpenRouter API key:
```bash
cp .env.example .env
```
Then edit `.env`:
```env
OPENROUTER_API_KEY=your_key_here
```

### 2. Run with Docker
```bash
docker build -t and-task-a .
docker run -p 8000:8000 --env-file .env and-task-a
```

### 3. API Usage
Generate a review via POST `/api/v1/reviews/generate`:
```bash
curl -X POST "http://localhost:8000/api/v1/reviews/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "user_persona": {
         "name": "Lagos Haggler",
         "interests": ["street_food"],
         "traits": ["price-conscious"],
         "tone": "casual",
         "nigerian_context": true
       },
       "product": {
         "name": "Jollof Rice",
         "category": "Food",
         "description": "Party Jollof with extra spice"
       }
     }'
```

## ⚖️ Compliance
- **Zero External Datasets**: No third-party data used.
- **OpenRouter Only**: Strictly uses official OpenRouter endpoints.
- **Zero Search**: No FAISS or vector DBs; simple reasoning-over-context only.