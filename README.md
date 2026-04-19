# DARC-EL: LLM-Based Data Extraction for Assessing Reporting Completeness in Electrocatalysis Literature

DARC-EL Data-driven Assessment of Reporting Completeness in Electrocatalysis Literature

## Project Description

Reliable evaluation of electrocatalysts requires consistent reporting of key properties such as activity, overpotential, and long-term stability, yet these metrics are frequently incomplete or inconsistently documented in the literature. This project's goal is to develop a GenAI-powered automated pipeline to systematically analyze a large body of electrocatalysis literature, extract key properties, and quantify how often essential information is missing. A benchmark on prompt-engineered and retrieval-augmented LLM approaches using a ground-truth dataset will be done, then the best-performing method will be applied to a broad corpus of papers. The system identifies underreporting trends and variations across journals and publication years, providing data-driven insights into the evolution of reporting practices in electrocatalysis.

The API now also accepts document uploads for ingestion into Neo4j. Uploaded files are parsed by type, extracted into a transport object, chunked for later retrieval, and stored as separate graph nodes.

Backend implementation details, API endpoint behavior, and upload internals are documented in `darc-el-backend/README.md`.
UI runtime, Django configuration, and frontend integration details are documented in `darc-el-ui/README.md`.

## Author

- Roland Ramp
- ORCID: [0009-0003-5145-2197](https://orcid.org/0009-0003-5145-2197)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Prerequisites

- Docker installed and running
- Docker Compose v2 (`docker compose`) or the legacy `docker-compose` command
- A valid Zotero API key and library ID
- Neo4j runs as part of the compose stack at `bolt://neo4j-kg:7687`

## Project Structure

- `darc-el-backend/` contains the FastAPI backend, its `pyproject.toml`, and backend Dockerfile
- `darc-el-ui/` contains the Django web UI, its `pyproject.toml`, and UI Dockerfile
- `docker-compose.yml` builds and runs backend + UI together with Neo4j and LLM providers
- `.env` stores runtime environment variables
- `.env.example` provides a safe template without secrets

## Service Documentation

- Backend service documentation: [`darc-el-backend/README.md`](darc-el-backend/README.md)
- UI service documentation: [`darc-el-ui/README.md`](darc-el-ui/README.md)

## System Architecture

DARC-EL runs as a compose-managed multi-service stack. The backend orchestrates bibliography downloads, document ingestion, and LLM provider routing through a shared registry configured in `config/llm_models.yaml`, while the Django UI consumes backend APIs.

The diagram below shows the deployment topology and service boundaries.

```mermaid
flowchart TD
	User[User Browser or Client]

	subgraph Stack[Docker Compose Stack]
		UI[darc-el-ui\nDjango UI]
		API[darc-el-backend\nFastAPI Backend]
		KG[neo4j-kg\nNeo4j Graph]
		OLL[ollama-backend\nOllama]
		LLAMA[llama-cpp-backend\nGPU profile optional]
	end

	ZOT[Zotero API]
	OR[OpenRouter Cloud]

	User --> UI
	User --> API
	UI --> API
	API --> KG
	API --> OLL
	API --> LLAMA
	API --> OR
	ZOT --> API
```

The runtime flow below summarizes how backend services process requests, route LLM calls, and persist graph data.

```mermaid
flowchart TD
	Request[Client or UI Request] --> API[FastAPI Backend]

	API --> ING[Document Ingestion Service]
	API --> DLS[Download Service]
	API --> STATUS[Status and Health Handlers]

	ING --> REG[Shared LLM Client Registry]
	DLS --> REG

	REG --> OLLP[Ollama Provider]
	REG --> LLP[llama.cpp Provider]
	REG --> ORP[OpenRouter Provider]

	ING --> NEO[(Neo4j Graph)]
	DLS --> NEO

	STATUS --> CFG[Non-secret Runtime Configuration]
```

Backend API endpoint details and upload internals are maintained in `darc-el-backend/README.md`.
UI runtime and integration behavior are maintained in `darc-el-ui/README.md`.

## 1. Configure Environment Variables

Copy `.env.example` to `.env` and set your own values:

ZOTERO_LIBRARY_ID=your_library_id
ZOTERO_API_KEY=your_api_key
ZOTERO_LIBRARY_TYPE=group

Optional:

ZOTERO_OUTPUT_FILE=zotero_group_items.json

LLM model registration is now read from `config/llm_models.yaml`. Keep model names and provider-model mappings in that YAML file.
You can also register an optional OpenRouter model in the same YAML using `provider: openrouter` and `api_key: ${OPENROUTER_API_KEY}`.

## 2. Build with Docker Compose

From the project root, build the services:

```bash
docker compose build
```

For service-specific build commands, see the backend and UI README files.

## 3. Run the Stack

Start the full stack:

```bash
docker compose up
```

If you want to rebuild before starting:

```bash
docker compose up --build
```

To start up everthing with GPU:

```bash
docker compose --profile gpu up -d
```

## 4. Verify Output

After the service runs a download, check the generated JSON file in your project directory.

Default output file:

zotero_group_items.json

## Access the Services

- DARC-EL API (FastApi): http://localhost:8000
- DARC-EL UI (Django): http://localhost:8081
- Neo4j Browser: http://localhost:7474
- Neo4j Bolt: bolt://localhost:7687
- Ollama API: http://localhost:6543

For backend endpoints, LLM client configuration, upload behavior, linting, and upload test scripts, see [`darc-el-backend/README.md`](darc-el-backend/README.md).

For UI local runtime and integration settings, see [`darc-el-ui/README.md`](darc-el-ui/README.md).

## Notes

- Keep `.env` private. Do not commit real API keys.
- Dependencies are installed from each service's `pyproject.toml` during image build.