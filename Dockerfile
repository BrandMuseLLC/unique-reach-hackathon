FROM node:22-slim AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY brandmuse ./brandmuse
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AUTH_MODE=iap
ENV CAMPAIGN_STORE=firestore
ENV PORT=8080
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY demo/engine.py demo/ai.py demo/ai_explain.py demo/ai_labels.py demo/assistant.py demo/clusters.py demo/daniel_provider.py demo/discovery.py demo/llm.py demo/upriver.py ./demo/
COPY collect/__init__.py collect/aggregate.py collect/validation.py collect/youtube.py ./collect/
ENV MUSE_DATASET=synthetic
ENV MUSE_LLM_COVERAGE_CONFIRMED=false
COPY --from=frontend /app/dist ./dist
CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
