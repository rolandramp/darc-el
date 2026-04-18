# Ministral - llama.cpp Docker

## Prebuild image

Here we use a prebuilt image of llama.ccp with cuda support.

# Build the image

```bash
docker build -t ministral-llama-cpp-1 .
```

# Run the image

```bash
docker run --rm -p 1235:8080 --gpus all ministral-llama-cpp-1 -hf mistralai/Ministral-3-3B-Instruct-2512-GGUF --port 8080 --host 0.0.0.0
```
