# Deployment — AWS App Runner

This folder contains the CloudFormation template to deploy API-HUB to AWS App Runner.

Two services are deployed:
- **api-hub-backend** — FastAPI on port 8000
- **api-hub-frontend** — Next.js standalone on port 3000

---

## Prerequisites

1. AWS CLI configured (`aws configure`)
2. An ECR repository for each image
3. An RDS PostgreSQL 16 instance (or compatible managed Postgres)
4. Docker installed locally to build and push images

---

## Step 1 — Build and push Docker images

```bash
AWS_ACCOUNT=123456789012
AWS_REGION=us-east-1

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Create ECR repos (one-time)
aws ecr create-repository --repository-name api-hub-backend --region $AWS_REGION
aws ecr create-repository --repository-name api-hub-frontend --region $AWS_REGION

# Build + push backend
docker build -t api-hub-backend ./backend
docker tag api-hub-backend:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-backend:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-backend:latest

# Build + push frontend
docker build --target runner -t api-hub-frontend ./frontend
docker tag api-hub-frontend:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-frontend:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-frontend:latest
```

---

## Step 2 — Deploy the CloudFormation stack

```bash
aws cloudformation deploy \
  --template-file deployment/aws-app-runner.yaml \
  --stack-name api-hub \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    PostgresUrl="postgresql+asyncpg://user:pass@your-rds-host:5432/vg_hub" \
    SecretKey="your-fernet-key" \
    IngestSharedSecret="your-ingest-secret" \
    AllowedOrigins="https://your-frontend-domain.com" \
    NextPublicApiUrl="https://your-backend-domain.com" \
    NextPublicN8nUrl="https://your-n8n-domain.com" \
    BackendImageUri="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-backend:latest" \
    FrontendImageUri="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-frontend:latest"
```

---

## Step 3 — Get service URLs

```bash
aws cloudformation describe-stacks \
  --stack-name api-hub \
  --query "Stacks[0].Outputs"
```

This prints the App Runner URLs for both backend and frontend.

---

## Environment variables reference

| Variable | Service | Required | Description |
|----------|---------|----------|-------------|
| `POSTGRES_URL` | backend | Yes | Full asyncpg connection string |
| `SECRET_KEY` | backend | Yes | Fernet key for encrypted DB columns |
| `INGEST_SHARED_SECRET` | backend | Yes | Auth header for n8n → FastAPI ingest |
| `ALLOWED_ORIGINS` | backend | Yes | Comma-separated CORS origins |
| `N8N_BASE_URL` | backend | Yes | URL of n8n instance |
| `NEXT_PUBLIC_API_URL` | frontend | Yes | Backend URL visible to the browser |
| `NEXT_PUBLIC_N8N_URL` | frontend | No | n8n URL for workflow trigger buttons |

---

## Updating after code changes

```bash
# Rebuild + push the changed image, then redeploy
docker build -t api-hub-backend ./backend
docker tag api-hub-backend:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-backend:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/api-hub-backend:latest

# Trigger App Runner to pull the new image
aws apprunner start-deployment \
  --service-arn $(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='api-hub-backend'].ServiceArn" \
    --output text)
```
