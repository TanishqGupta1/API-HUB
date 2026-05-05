# API-HUB — Production Deploy Runbook

Step-by-step procedure for the first ECS Fargate deploy. Treat each step as a hand-off: when you finish, the next person should be able to start the next step without context.

For the architecture overview, see `deployment/README.md`. For the CFN template, see `deployment/ecs/api-hub.yaml`.

---

## Phase 0 — Prerequisites (one-time, manual)

These are AWS-account-level resources that exist outside the CFN stack. Do them once, then never again.

### 0.1 — Domain in Route 53

You need a domain you own with DNS pointed at Route 53.

```bash
# Create a hosted zone if you don't have one yet
aws route53 create-hosted-zone --name staging.example.com --caller-reference $(date +%s)

# Note the HostedZoneId from the output. You will paste this into
# deployment/ecs/parameters/staging.json later.
```

If the registrar is not Route 53 (e.g. GoDaddy, Cloudflare), update the registrar's NS records to the four NS values Route 53 returned. Wait for propagation (usually < 1 hour).

**Verify:**
```bash
dig +short NS staging.example.com   # should return the AWS ns-* records
```

### 0.2 — ACM wildcard certificate

The ALB needs a TLS cert covering `api.`, `app.`, `n8n.` subdomains.

```bash
aws acm request-certificate \
  --region us-east-1 \
  --domain-name '*.staging.example.com' \
  --subject-alternative-names 'staging.example.com' \
  --validation-method DNS
```

ACM returns a CertificateArn and a list of validation CNAME records to add to Route 53. Add them:

```bash
# ACM's describe-certificate shows the CNAMEs
aws acm describe-certificate --region us-east-1 --certificate-arn <arn> \
  --query 'Certificate.DomainValidationOptions[].ResourceRecord'
```

Add each `Name` → `Value` CNAME to the Route 53 zone. Wait until the cert status flips to `ISSUED`:

```bash
aws acm describe-certificate --region us-east-1 --certificate-arn <arn> \
  --query 'Certificate.Status'
# Expect: "ISSUED"
```

### 0.3 — VPC

You need a VPC with at least 2 public subnets and 2 private subnets across two AZs, plus a NAT gateway for the private subnets to reach the internet (ECR pulls, OPS API calls).

If your account has a default VPC and matches that shape, skip. Otherwise create one — the AWS console "VPC and more" wizard does this in 3 clicks.

**Capture the IDs you need:**
```bash
VPC_ID=vpc-xxxxxxxxxxxxxxxxx
PUBLIC_SUBNETS=subnet-aaa,subnet-bbb     # for the ALB
PRIVATE_SUBNETS=subnet-ccc,subnet-ddd    # for ECS tasks, RDS, EFS
```

### 0.4 — ECR repositories

CI pushes images here. Create once:

```bash
aws ecr create-repository --repository-name api-hub-backend  --region us-east-1
aws ecr create-repository --repository-name api-hub-frontend --region us-east-1
aws ecr create-repository --repository-name api-hub-n8n      --region us-east-1
```

### 0.5 — GitHub OIDC role for CI

GitHub Actions needs to assume an AWS role to push images and deploy CFN. Create an OIDC identity provider + role:

1. Go to IAM → Identity providers → Add provider → OpenID Connect
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`
2. Create a role trusting that provider, restricted to this repo:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": { "Federated": "arn:aws:iam::<ACCOUNT>:oidc-provider/token.actions.githubusercontent.com" },
       "Action": "sts:AssumeRoleWithWebIdentity",
       "Condition": {
         "StringEquals": {
           "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
           "token.actions.githubusercontent.com:sub": "repo:VisualGraphxLLC/API-HUB:ref:refs/heads/main"
         }
       }
     }]
   }
   ```
3. Attach a policy that allows: ECR push, CloudFormation deploy, IAM PassRole on the task roles, ECS register/run-task, Secrets Manager read on `api-hub/*`. (The narrowest viable policy is in `deployment/iam-policies/github-deploy.json` — add later.)
4. Capture the role ARN.

### 0.6 — GitHub repo secret

In the GitHub repo Settings → Secrets and variables → Actions → New repository secret:
- Name: `AWS_OIDC_ROLE_ARN`
- Value: the role ARN from 0.5

---

## Phase 1 — Configure parameters

### 1.1 — Edit `deployment/ecs/parameters/staging.json`

Replace placeholders with the IDs you captured in Phase 0:

```json
[
  {"ParameterKey": "EnvironmentName",    "ParameterValue": "staging"},
  {"ParameterKey": "DomainName",         "ParameterValue": "staging.example.com"},
  {"ParameterKey": "HostedZoneId",       "ParameterValue": "Z123456789ABCDEFGHIJK"},
  {"ParameterKey": "AcmCertificateArn",  "ParameterValue": "arn:aws:acm:us-east-1:..."},
  {"ParameterKey": "VpcId",              "ParameterValue": "vpc-..."},
  {"ParameterKey": "PublicSubnetIds",    "ParameterValue": "subnet-aaa,subnet-bbb"},
  {"ParameterKey": "PrivateSubnetIds",   "ParameterValue": "subnet-ccc,subnet-ddd"},
  {"ParameterKey": "BackendImageUri",    "ParameterValue": "PLACEHOLDER_REPLACED_BY_CI"},
  {"ParameterKey": "FrontendImageUri",   "ParameterValue": "PLACEHOLDER_REPLACED_BY_CI"},
  {"ParameterKey": "N8nImageUri",        "ParameterValue": "PLACEHOLDER_REPLACED_BY_CI"}
]
```

Commit + push to `main`.

### 1.2 — Validate the CFN template locally

Before letting CI run, check the template parses:

```bash
aws cloudformation validate-template \
  --region us-east-1 \
  --template-body file://deployment/ecs/api-hub.yaml
```

Expected: a JSON object with `Description`, `Parameters`, `Capabilities`. No `ValidationError`.

---

## Phase 2 — First deploy

### 2.1 — Trigger CI

Push any commit to `main`. The `Deploy to ECS (staging)` workflow runs. Watch in GitHub Actions tab.

The workflow:
1. Builds + pushes 3 images to ECR (~5 min)
2. Runs `aws cloudformation deploy` (~15-20 min on first run because RDS provisions)
3. Runs `alembic upgrade head` as a one-off Fargate task

If any step fails, the workflow stops. CFN auto-rolls-back the stack on failure.

### 2.2 — Verify the stack

```bash
aws cloudformation describe-stacks --stack-name api-hub-staging \
  --query 'Stacks[0].{Status:StackStatus, Outputs:Outputs}'
# StackStatus should be CREATE_COMPLETE or UPDATE_COMPLETE
```

### 2.3 — Verify DNS resolves

The CFN template creates Route 53 ALIAS records pointing at the ALB. Wait ~1 minute then:

```bash
dig +short api.staging.example.com
dig +short app.staging.example.com
dig +short n8n.staging.example.com
# All three should return the same dualstack.api-hub-... ELB hostname
```

### 2.4 — Verify health endpoints

```bash
curl -fsS https://api.staging.example.com/health
# Expect: {"status":"ok","service":"api-hub"}

curl -fsSI https://app.staging.example.com
# Expect: HTTP/2 200

curl -fsSI https://n8n.staging.example.com/healthz
# Expect: HTTP/2 200
```

If any returns a different status, check ECS service events:
```bash
aws ecs describe-services --cluster api-hub-staging \
  --services api-hub-backend-staging api-hub-frontend-staging api-hub-n8n-staging \
  --query 'services[].{name:serviceName, running:runningCount, desired:desiredCount, events:events[0:3]}'
```

### 2.5 — Create the first admin

The backend's `/api/auth/setup` endpoint is open while there are 0 users. Create the first admin BEFORE anyone else can:

```bash
curl -fsS -X POST https://api.staging.example.com/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourcompany.com","password":"<long-strong-password>"}'
```

Expected: `201 Created` with the user JSON. Subsequent calls return `409 Conflict`.

Save the password in your team password manager (1Password / Bitwarden) — there is no password recovery flow in V1.

### 2.6 — Verify login works in browser

1. Open `https://app.staging.example.com/login` in a fresh browser tab (Incognito recommended)
2. Submit the email + password from 2.5
3. Land on the dashboard
4. DevTools → Application → Cookies → `https://app.staging.example.com` shows `auth_token` with `HttpOnly`, `Secure`, `SameSite=Lax`
5. DevTools → Application → Local Storage → empty (no token there)

### 2.7 — Set up n8n

The custom n8n image already has the OnPrintShop community node baked in. Workflows + credentials must be imported manually for the first deploy.

1. Visit `https://n8n.staging.example.com`. Basic-auth credentials: `admin` / value of `api-hub/staging/N8N_BASIC_AUTH_PASSWORD` in Secrets Manager.
2. Workflows → Import from File → upload each JSON in `n8n-workflows/`.
3. For each imported workflow:
   - Open it
   - Activate it (top-right toggle) if it's a cron / webhook trigger
4. Settings → API → generate an API key. Save it.
5. (Optional) Update the backend's `N8N_API_KEY` secret in Secrets Manager and force a new task definition revision so the backend picks it up.

### 2.8 — Smoke test the push pipeline

```bash
# Create a test customer (replace TOKEN with the auth_token cookie value)
curl -fsS -X POST https://api.staging.example.com/api/customers \
  -H "Cookie: auth_token=<TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Customer","ops_base_url":"https://test.ops.com",...}'

# Trigger a push (assuming a product exists)
curl -fsS -X POST https://api.staging.example.com/api/push/<customer_id>/<product_id> \
  -H "Cookie: auth_token=<TOKEN>"
# Expect: {"status":"pending", "push_log_id":"..."}

# Verify n8n received the webhook (check workflow execution log in n8n UI)
```

---

## Phase 3 — Subsequent deploys

After Phase 2, every push to `main` auto-deploys. No manual steps. CI:
1. Builds new images with the SHA tag
2. Updates the CFN stack with the new image URIs (only ECS service task definitions change; RDS / EFS / ALB do not redeploy)
3. ECS rolling-deploys: new tasks come up, ALB health-checks them, old tasks drain (~5 min)
4. Alembic migration runs after the service update completes

ECS rolling deploy on backend / frontend = zero downtime. n8n is single-task on EFS = brief 503s during deploy (~30 sec). Plan deploys outside business hours if push-pipeline workflows are time-critical.

### Rollback

To revert to a previous SHA:

```bash
# Find the SHA you want
aws ecr describe-images --repository-name api-hub-backend \
  --query 'sort_by(imageDetails,&imagePushedAt)[*].{tag:imageTags[0], pushed:imagePushedAt}' \
  --output table

# Force CFN deploy with that SHA
aws cloudformation deploy \
  --stack-name api-hub-staging \
  --template-file deployment/ecs/api-hub.yaml \
  --parameter-overrides $(jq -r 'map("\(.ParameterKey)=\(.ParameterValue)") | .[]' deployment/ecs/parameters/staging.json | tr '\n' ' ') \
    BackendImageUri=<account>.dkr.ecr.us-east-1.amazonaws.com/api-hub-backend:<old-sha> \
    FrontendImageUri=<account>.dkr.ecr.us-east-1.amazonaws.com/api-hub-frontend:<old-sha> \
    N8nImageUri=<account>.dkr.ecr.us-east-1.amazonaws.com/api-hub-n8n:<old-sha> \
  --capabilities CAPABILITY_IAM
```

Note: rolling back the backend can leave the database one schema version ahead. Alembic migrations should be backwards-compatible. If a migration is destructive, rolling back requires a manual `alembic downgrade -1` first.

### Pre-deploy snapshot (risky changes only)

```bash
aws rds create-db-snapshot \
  --db-instance-identifier api-hub-staging \
  --db-snapshot-identifier api-hub-staging-pre-deploy-$(date +%Y%m%d-%H%M)
```

---

## Phase 4 — Production cutover (later)

When ready to graduate from staging to production:

1. Repeat Phase 0 with `production.example.com`
2. Update `deployment/ecs/parameters/production.json`
3. Add a second GitHub Actions workflow (or extend `deploy.yml`) that triggers on a production tag (e.g. `release/*`) and uses `STACK_NAME=api-hub-production`
4. Production differs from staging by stack template conditions (`!If [IsProduction, ...]`):
   - RDS Multi-AZ enabled
   - 14-day backups (vs 7-day staging)
   - Deletion protection on RDS
5. First-time setup: copy the staging admin user via API, or run `/api/auth/setup` on production explicitly

---

## Common failures + fixes

### "Stack failed: ROLLBACK_COMPLETE"

CFN couldn't create something. Check the events:
```bash
aws cloudformation describe-stack-events --stack-name api-hub-staging \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' --max-items 5
```
Common causes: VPC subnets in wrong AZs, ACM cert in wrong region, IAM role naming conflict (delete the orphan role and re-deploy).

### Backend tasks keep restarting

Check CloudWatch logs:
```bash
aws logs tail /ecs/api-hub-backend-staging --since 10m
```
Most common cause: missing or invalid env var → `_require_prod_env()` raises → container exits → ECS replaces it.

### Frontend gets CORS errors

Verify `ALLOWED_ORIGINS` task definition env exactly matches `https://app.staging.example.com` (no trailing slash, no `http://`).

### Login works but `/api/customers` returns 401

The `auth_token` cookie isn't crossing subdomains. Verify:
- Browser DevTools shows the cookie domain as `.staging.example.com` (with leading dot) OR same-origin requests via reverse-proxy
- For V1, both subdomains must share the same registrable domain; the cookie is set host-only by default. If you need cross-subdomain, update `_set_auth_cookie()` in `backend/modules/auth/routes.py` to set `domain=.staging.example.com`.

### n8n editor returns 401

Basic auth credentials. Reset:
```bash
aws secretsmanager update-secret \
  --secret-id api-hub/staging/N8N_BASIC_AUTH_PASSWORD \
  --secret-string '<new-password>'
# Then force n8n service redeploy
aws ecs update-service --cluster api-hub-staging --service api-hub-n8n-staging --force-new-deployment
```

---

## Open questions for ops / Christian

- **Domain ownership** — who registers + manages Route 53?
- **Production AWS account** — same as staging or separate?
- **n8n basic-auth user list** — single shared admin, or per-engineer?
- **Existing n8n credentials** — who exports the OPS OAuth credentials from current local n8n and imports into the ECS-hosted n8n during first cutover?
- **Tier priority confirmation** — `Net > Sale > MSRP > Case` (PR #81 follow-up TODO in `resolvers_apparel.py`)

Resolve these before Phase 0 starts.
