FROM python:3.12-slim
ARG GIT_SHA=dev
LABEL git_sha=${GIT_SHA}
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
