# Dev Container Environment Design

## Objective

Allow VS Code Dev Containers to validate and start the Compose project when a
developer has not created a local `.env` file.

## Design

The `app` service will keep loading `.env` when it exists, so developers can
provide optional OpenAI and Google API keys without committing them. The file
will no longer be required during Compose validation. The local PostgreSQL
connection URL will be declared directly in the service environment because
its host and credentials already match the non-secret development database
configuration in the same Compose file.

## Verification

Run `docker compose -f docker-compose.yml --profile '*' config` without an
`.env` file. It must exit successfully and render `DATABASE_URL` for the `app`
service.
