FROM python:3.13.7-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY fritzexporter /app/fritzexporter

EXPOSE 18000

ENTRYPOINT ["python", "-m", "fritzexporter"]
