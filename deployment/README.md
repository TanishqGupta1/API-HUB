# Deployment — AWS ECS Fargate

API-HUB runs on AWS ECS Fargate. Three services in one cluster behind
a shared ALB:

| Subdomain                   | Service             | Container | Port |
|-----------------------------|---------------------|-----------|------|
| `api.<domain>`              | api-hub-backend     | FastAPI   | 8000 |
| `app.<domain>`              | api-hub-frontend    | Next.js   | 3000 |
| `n8n.<domain>`              | api-hub-n8n         | n8n + OnPrintShop | 5678 |

Inter-service traffic uses Cloud Map private DNS (e.g.
`backend.api-hub.local:8000`). RDS Postgres in private subnets, EFS
for n8n state, all secrets in Secrets Manager.

## One-time prerequisites

1. **Route 53 hosted zone** for the chosen domain (e.g. `staging.example.com`)
2. **ACM certificate** in the deploy region covering `*.<domain>`
3. **VPC** with at least 2 public + 2 private subnets and a NAT gateway
4. **GitHub OIDC role** in IAM trusting `repo:VisualGraphxLLC/API-HUB:ref:refs/heads/main`
   with permissions: ECR push, CloudFormation deploy, ECS register/run-task,
   PassRole on the task roles, Secrets Manager Read.
5. **GitHub repo secret** `AWS_OIDC_ROLE_ARN` set to the role ARN above

Update `deployment/ecs/parameters/staging.json` with the VPC ID, subnet
IDs, hosted zone ID, ACM cert ARN, and domain.

## First deploy

```bash
# Local one-shot, before CI is wired up:
aws cloudformation deploy \
  --template-file deployment/ecs/api-hub.yaml \
  --stack-name api-hub-staging \
  --region us-east-1 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    EnvironmentName=staging \
    DomainName=staging.example.com \
    HostedZoneId=Z123 \
    AcmCertificateArn=arn:aws:acm:us-east-1:...:certificate/... \
    VpcId=vpc-... \
    PublicSubnetIds=subnet-aaa,subnet-bbb \
    PrivateSubnetIds=subnet-ccc,subnet-ddd \
    BackendImageUri=... FrontendImageUri=... N8nImageUri=...
```

After the stack creates, run the Alembic migration as a one-off ECS task:

```bash
aws ecs run-task \
  --cluster api-hub-staging \
  --launch-type FARGATE \
  --task-definition api-hub-migrate
```

## Subsequent deploys

Push to `main` → GitHub Actions:
1. Builds backend, frontend, and n8n images, pushes to ECR with the SHA tag
2. Deploys the CFN stack with new image URIs
3. Runs `alembic upgrade head` as a one-off Fargate task

Rollback: re-run the workflow with the previous SHA, or:
```bash
aws cloudformation deploy \
  --parameter-overrides \
    BackendImageUri=<previous-sha-uri> \
    ... # others unchanged
```

## Cost (staging)

| Service | Configuration | Monthly |
|---------|---------------|--------:|
| ECS Fargate (3 services × 0.5 vCPU / 1 GB) | always-on | ~$50 |
| ALB | always-on | ~$20 |
| RDS db.t4g.small (Multi-AZ off in staging) | 20 GB gp3 | ~$25 |
| EFS | 1 GB | ~$1 |
| Secrets Manager (5 secrets) | — | ~$2 |
| CloudWatch Logs (30-day retention) | low traffic | ~$5 |
| Route 53 hosted zone | — | $0.50 |
| **Total** | | **~$104/mo** |

Production with Multi-AZ RDS adds ~$40/mo.

## DR / backups

- RDS automated backups: 7 days (staging) / 14 days (production)
- RPO ~1 hour (PITR), RTO ~30 min (RDS restore + ECS service replace)
- No cross-region replicas in V1 (per spec D14)
- Pre-deploy snapshots (manual): `aws rds create-db-snapshot --db-instance-identifier api-hub-staging --db-snapshot-identifier api-hub-staging-pre-deploy-<date>`
