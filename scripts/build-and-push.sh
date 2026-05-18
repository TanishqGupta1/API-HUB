#!/bin/bash
# Build and push frontend + backend Docker images to ECR for ECS deployment.
# Run this from the repo root before updating the ECS service.
#
# Usage:
#   AWS_REGION=us-east-1 \
#   AWS_ACCOUNT_ID=123456789012 \
#   NEXT_PUBLIC_API_URL=https://api.dev-apihub.visualgraphx.com \
#   NEXT_PUBLIC_N8N_URL=https://n8n.dev-apihub.visualgraphx.com \
#   ./scripts/build-and-push.sh

set -e

# ── Required env vars ────────────────────────────────────────────────────────
: "${AWS_REGION:?Set AWS_REGION}"
: "${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
: "${NEXT_PUBLIC_API_URL:?Set NEXT_PUBLIC_API_URL (e.g. https://api.dev-apihub.visualgraphx.com)}"
: "${NEXT_PUBLIC_N8N_URL:?Set NEXT_PUBLIC_N8N_URL}"

ECR_BASE="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
SHA=$(git rev-parse --short HEAD)

echo "▶ Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_BASE"

echo ""
echo "▶ Building frontend (sha=$SHA)..."
docker build \
  --build-arg NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
  --build-arg NEXT_PUBLIC_N8N_URL="$NEXT_PUBLIC_N8N_URL" \
  -t "$ECR_BASE/api-hub-frontend:$SHA" \
  -t "$ECR_BASE/api-hub-frontend:latest" \
  ./frontend

echo "▶ Pushing frontend..."
docker push "$ECR_BASE/api-hub-frontend:$SHA"
docker push "$ECR_BASE/api-hub-frontend:latest"

echo ""
echo "▶ Building backend (sha=$SHA)..."
docker build \
  -t "$ECR_BASE/api-hub-backend:$SHA" \
  -t "$ECR_BASE/api-hub-backend:latest" \
  ./backend

echo "▶ Pushing backend..."
docker push "$ECR_BASE/api-hub-backend:$SHA"
docker push "$ECR_BASE/api-hub-backend:latest"

echo ""
echo "✅ Done. Images pushed:"
echo "   $ECR_BASE/api-hub-frontend:$SHA"
echo "   $ECR_BASE/api-hub-backend:$SHA"
echo ""
echo "Next: go to ECS → your service → Update → set image tag to: $SHA"
