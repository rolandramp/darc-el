# DARC-EL: LLM-Based Data Extraction for Assessing Reporting Completeness in Electrocatalysis Literature

DARC-EL Data-driven Assessment of Reporting Completeness in Electrocatalysis Literature

## Project Description

Reliable evaluation of electrocatalysts requires consistent reporting of key properties such as activity, overpotential, and long-term stability, yet these metrics are frequently incomplete or inconsistently documented in the literature. This project's goal is to develop a GenAI-powered automated pipeline to systematically analyze a large body of electrocatalysis literature, extract key properties, and quantify how often essential information is missing. A benchmark on prompt-engineered and retrieval-augmented LLM approaches using a ground-truth dataset will be done, then the best-performing method will be applied to a broad corpus of papers. The system identifies underreporting trends and variations across journals and publication years, providing data-driven insights into the evolution of reporting practices in electrocatalysis.

## Author

- Roland Ramp
- ORCID: [0009-0003-5145-2197](https://orcid.org/0009-0003-5145-2197)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Prerequisites

- Docker installed and running
- A valid Zotero API key and library ID

## Project Structure

- `Dockerfile` builds the Python image
- `pyproject.toml` defines project dependencies
- `src/main.py` contains the application entry point
- `.env` stores runtime environment variables

## 1. Configure Environment Variables

Edit `.env` and set your own values:

ZOTERO_LIBRARY_ID=your_library_id
ZOTERO_API_KEY=your_api_key
ZOTERO_LIBRARY_TYPE=group

Optional:

ZOTERO_OUTPUT_FILE=zotero_group_items.json

## 2. Build the Docker Image

From the project root, run:

docker build -t darc-el:latest .

## 3. Run the Container

Run with your env file:

docker run --rm --env-file .env -v ${PWD}:/app darc-el:latest python src/main.py

If you are using PowerShell and `${PWD}` causes issues, use:

docker run --rm --env-file .env -v "${PWD}:/app" darc-el:latest python src/main.py

## 4. Verify Output

After the container finishes, check the generated JSON file in your project directory.

Default output file:

zotero_group_items.json

## Notes

- Keep `.env` private. Do not commit real API keys.
- Dependencies are installed from `pyproject.toml` during image build.
- The container work directory is `/app`.
