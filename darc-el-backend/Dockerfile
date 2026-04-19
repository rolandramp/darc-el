FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY darc-el-backend/pyproject.toml ./pyproject.toml
COPY darc-el-backend/README.md ./README.md
COPY LICENSE ./LICENSE
COPY config ./config
COPY darc-el-backend/src ./src

RUN uv pip install --system --no-cache .

CMD ["python", "src/main.py", "--llm-config-path", "/app/config/llm_models.yaml"]


