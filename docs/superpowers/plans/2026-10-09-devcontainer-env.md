# Dev Container Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Dev Container Compose configuration valid without requiring a local `.env` file.

**Architecture:** Keep `.env` as an optional source for provider API keys and define the local PostgreSQL connection URL directly on the `app` service. This preserves developer overrides while ensuring Compose validation has all required local infrastructure settings.

**Tech Stack:** Docker Compose v5, VS Code Dev Containers, PostgreSQL 16

## Global Constraints

- Do not add or expose API keys.
- Preserve optional `.env` loading.
- Use the Compose service hostname `postgres`, not `localhost`, in `DATABASE_URL`.

---

### Task 1: Make the application environment self-contained

**Files:**
- Modify: `docker-compose.yml`
- Test: Compose configuration validation command

**Interfaces:**
- Consumes: PostgreSQL service `postgres` on port `5432` with the existing development credentials.
- Produces: `DATABASE_URL=postgresql+psycopg://langchain_user:langchain_password@postgres:5432/langchain_db` in the `app` container environment.

- [ ] **Step 1: Verify the existing configuration fails**

Run: `docker compose -f docker-compose.yml --profile '*' config`

Expected: exit code 1 with `.env not found`.

- [ ] **Step 2: Make `.env` optional and set the database URL**

Replace the short `env_file` entry with:

```yaml
    env_file:
      - path: .env
        required: false
    environment:
      DATABASE_URL: postgresql+psycopg://langchain_user:langchain_password@postgres:5432/langchain_db
```

- [ ] **Step 3: Verify the corrected configuration**

Run: `docker compose -f docker-compose.yml --profile '*' config`

Expected: exit code 0; rendered `app.environment.DATABASE_URL` references `postgres:5432/langchain_db`.

- [ ] **Step 4: Validate the Dev Container configuration inputs**

Run: `python3 -m json.tool .devcontainer/devcontainer.json >/dev/null`

Expected: exit code 0.

No commit step is included because the workspace is not a Git repository.
