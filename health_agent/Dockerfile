FROM python:3.12-slim

WORKDIR /app
COPY agent ./agent
COPY skills ./skills
COPY prompts ./prompts
COPY pyproject.toml requirements.lock ./

CMD ["python", "-m", "agent.main"]
