FROM python:3.12-slim

WORKDIR /app
COPY agent_runtime ./agent_runtime

EXPOSE 8090
CMD ["python", "-m", "agent_runtime.server", "--host", "0.0.0.0", "--port", "8090"]
