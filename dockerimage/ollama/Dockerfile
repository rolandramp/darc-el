FROM ollama/ollama:latest

# Copy the helper script into the image, fix Windows CRLF line endings and make it executable
COPY load_ollama_model.sh /load_ollama_model.sh
RUN sed -i 's/\r$//' /load_ollama_model.sh && chmod +x /load_ollama_model.sh

# Override the base image entrypoint so the container starts ollama, pulls the configured model and signals readiness
ENTRYPOINT ["/bin/bash", "/load_ollama_model.sh"]

