# 🚀 TradeSignal India — Automated CI/CD & EC2 Deployment Guide

This project is configured with an **automated GitHub Actions CI/CD pipeline** that builds Docker images, tags them with the **Git Commit SHA**, pushes them to GitHub Container Registry (GHCR), and updates your live AWS EC2 containers with **zero downtime**.

---

## 📌 Architecture Overview

```
Your Local PC (git push)
          │
          ▼
   GitHub Repository
          │
          ▼ (Triggers GitHub Actions)
 ┌─────────────────────────────────────────┐
 │ 1. Build Backend Docker Image           │
 │ 2. Build Frontend Docker Image          │
 │ 3. Tag with Commit SHA (e.g. :9f3b12a)  │
 │ 4. Push to GHCR (ghcr.io)               │
 └──────────────────┬──────────────────────┘
                    │
                    ▼ (SSH to EC2)
              AWS EC2 Server
  ┌─────────────────────────────────────┐
  │ • Pulls new tagged images           │
  │ • Recreates Backend & Frontend      │
  │ • Keeps PostgreSQL & Redis Intact   │
  │ • Prunes old dangling images        │
  └─────────────────────────────────────┘
```

---

## 🔑 One-Time GitHub Setup (3 Secrets)

1. Go to your GitHub repository:
   👉 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

2. Add the following secrets:

| Secret Name | Example Value | Description |
|---|---|---|
| `EC2_HOST` | `13.232.xxx.xxx` | Your AWS EC2 Public IPv4 address |
| `EC2_USER` | `ec2-user` or `ubuntu` | Default SSH user for your EC2 instance |
| `EC2_SSH_KEY` | `-----BEGIN RSA PRIVATE KEY-----...` | Entire contents of your `.pem` key file |
| `DEPLOY_TOKEN` | `ghp_xxxxxxxxxxxx` *(Optional)* | GitHub Personal Access Token with `read:packages` permission |

---

## 🚀 Daily Workflow: How to Deploy

Whenever you make changes to backend strategies, algorithms, or frontend UI:

```bash
# 1. Stage and commit your changes
git add .
git commit -m "feat: improved option chain confluence score"

# 2. Push to GitHub
git push origin main
```

**That's it!**  
GitHub Actions will automatically build the images, push them to the registry, SSH into your EC2, and update your running app within ~90 seconds.

---

## ⏪ Instant 10-Second Rollback (In case of issues)

Because every build is uniquely tagged with its Git Commit SHA, you can roll back instantly on EC2 without rebuilding:

```bash
# SSH into your EC2 server
ssh -i your-key.pem ec2-user@<EC2_IP>

# Run the rollback utility with the target commit SHA
cd ~/trade-signal-india_v2_upgrade
./scripts/rollback.sh <PREVIOUS_COMMIT_SHA>
```

Your live app will roll back in under **3 seconds**!

---

## 💾 Database Persistence Guarantee

Your production `docker-compose.prod.yml` uses named volumes (`postgres_data` and `redis_data`).  
During CI/CD deployments:
- Only `backend` and `frontend` containers are recreated (`--no-deps`).
- PostgreSQL trade logs, tables, and Redis state are **never touched or wiped**.
