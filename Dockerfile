FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md LICENSE ./
COPY config ./config
COPY src ./src

RUN uv pip install --system --no-cache .

CMD ["python", "src/main.py"]


