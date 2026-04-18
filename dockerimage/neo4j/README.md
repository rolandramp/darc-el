# Neo4j (Docker) - Startup Instructions

This folder contains the custom Neo4j image used by the project. The image now downloads its plugins during build, so the local plugin directory is no longer needed.

## Quick Summary

- Service name: `neo4j-kg` in [docker-compose.yml](../../docker-compose.yml)
- Base image: `neo4j:2026.03-community`
- Credentials: `neo4j` / `pass4neo` (set via `NEO4J_AUTH` in [docker-compose.yml](../../docker-compose.yml))
- Ports:
  - Bolt: `7687`
  - HTTP: `7474`
  - HTTPS: `7475`
- Plugins downloaded at build time:
  - APOC `2026.03.1`
  - neosemantics `5.26.0`
  - spatial `5.26.0`

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose v2 (`docker compose`) or the legacy `docker-compose` command

## Build and Run

Run from the project root:

```bash
docker compose up --build neo4j-kg
```

With the legacy command:

```bash
docker-compose up --build neo4j-kg
```

If you want to build only the Neo4j image first:

```bash
docker compose build neo4j-kg
```

## Logs

```bash
docker compose logs -f neo4j-kg
```

## Stop

```bash
docker compose down
```

## Accessing Neo4j

- Browser: http://localhost:7474
- Bolt: bolt://localhost:7687

## Notes

- The Dockerfile now downloads plugin jars during image build, so there is no host-mounted `plugins` directory anymore.
- Neo4j imports are mounted from [docker-compose.yml](../../docker-compose.yml) into `/var/lib/neo4j/import`.
- If you add or change plugin versions later, keep the README and Dockerfile in sync.

