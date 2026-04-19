# DARC-EL Backend

FastAPI backend for DARC-EL.

## Scope

This README documents backend-specific setup and operations.
For project-wide architecture and full-stack orchestration, see [`../README.md`](../README.md).

## Run locally

```bash
python src/main.py --llm-config-path ../config/llm_models.yaml
```

## Run with Docker Compose

From the repository root:

```bash
docker compose build darc-el-backend
docker compose up darc-el-backend
```

To rebuild and recreate only the backend service:

```bash
docker compose up -d --build --force-recreate darc-el-backend
```

## API Endpoints

- `GET /health` checks backend service health.
- `GET /status` reports runtime status.
- `GET /llm/status` returns non-secret LLM client configuration and initialization state.
- `POST /llm/default-model` sends a prompt to the configured default model.
- `POST /download` triggers literature download processing.
- `POST /upload` ingests uploaded documents.
- `GET /documents` lists ingested documents.
- `DELETE /documents/{file_name}` deletes all ingested records for a file name.

## Shared LLM Clients

The backend initializes a shared OpenAI-compatible client registry at startup.
Client registrations are read from [`../config/llm_models.yaml`](../config/llm_models.yaml), where each model defines provider and base URL.
For `openrouter` providers, the backend uses the dedicated OpenRouter SDK client path during registration.

## Default Model Prompt Endpoint

Use `POST /llm/default-model` with JSON payload:

- `prompt` (required)
- `system_prompt` (optional)
- `max_tokens` (optional)
- `temperature` (optional)

The endpoint invokes the configured default model through the shared client registry and returns model/provider metadata together with generated response text.

## Document Uploads

Use `POST /upload` with `multipart/form-data` and one or more files in the `files` field.

Supported types in this implementation:

- PDF
- DOCX
- plain text

The API extracts text and metadata, chunks the text, and writes the result to Neo4j as:

- one `Document` node per file
- one `DocumentMetadata` node per file
- one `DocumentChunk` node per chunk

For PDFs with large compressed content streams, the parser decompression limit is configurable
through `PDF_ZLIB_MAX_OUTPUT_LENGTH` (default: `200000000` bytes).

The upload response now reports per-file outcomes in `files` with `status` values of
`parsed` or `error`. Batch uploads can complete with `status: "partial"` when at least one
file succeeds and one or more files fail.

The current Neo4j connection used by the app inside Docker is `bolt://neo4j-kg:7687`, with credentials controlled by `NEO4J_USER` and `NEO4J_PASS`.

## Document Management

The backend document workflow is implemented through `DocumentService` and persists records using Neo4j.

- Use `GET /documents` to retrieve ingested document rows including parser, chunk count, update time, and metadata summary.
- Use `DELETE /documents/{file_name}` to remove all matching document records by file name.

## Static Analysis

This project uses Ruff for Python static code analysis and linting.

From the repository root:

```bash
make lint
make lint-fix
```

Or from the backend folder:

```bash
pip install -e .[dev]
ruff check src tests
ruff check --fix src tests
```

## Test File Upload Script

PowerShell helper script location:

- [`scripts/test-upload-pdf.ps1`](scripts/test-upload-pdf.ps1)

From the backend folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\test-upload-pdf.ps1 -PdfPath "..\data\10.1002_adfm.202107862.pdf"
```

## Notes

- Keep `.env` private. Do not commit real API keys.
- Dependencies are installed from `pyproject.toml` during image build.
