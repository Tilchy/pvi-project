FROM python:3.12.8-slim

WORKDIR /app

COPY requirements.txt /app/

RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app /app/app

EXPOSE 80

CMD ["fastapi", "run", "app/main.py", "--port", "80"]