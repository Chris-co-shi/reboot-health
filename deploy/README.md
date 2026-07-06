<div align="center">

# Deployment

### Local private deployment for reboot-health

<p>
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker%20Compose-Local%20Stack-2496ED?logo=docker&logoColor=white">
  <img alt="Scope" src="https://img.shields.io/badge/Scope-Private%20Deployment-6C5CE7">
</p>

</div>

## Components

The deployment stack coordinates:

- Java Health Domain Kernel.
- Python Health Agent Harness.
- Frozen Vue Debug Tool.
- External or local PostgreSQL 17, depending on environment configuration.

Flutter runs as the user client and is not hosted by this Compose stack.

## Validate configuration

From the repository root:

```bash
docker compose -f deploy/docker-compose.yml config
```

## Start

```bash
docker compose -f deploy/docker-compose.yml up -d
```

## Inspect

```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f
```

## Stop

```bash
docker compose -f deploy/docker-compose.yml down
```

## Configuration rules

- Real credentials and private network addresses must be provided through local environment configuration.
- Do not commit production secrets or encryption material.
- Do not expose services publicly by default.
- M2.5-A does not require Redis, a message queue, a vector database or a workflow platform.
- Deployment changes must not silently alter application business behavior.

Detailed constraints are defined in [`AGENTS.md`](AGENTS.md) and [`../docs/architecture.md`](../docs/architecture.md).
