FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY devices_config.py simulator.py inject.py inject_event.py ./

CMD ["python", "simulator.py", "--mode", "NORMAL"]
