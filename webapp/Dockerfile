FROM python:3.12.8-slim

WORKDIR /app

COPY requirements.txt /app/

RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install -y curl build-essential

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app /app/app

EXPOSE 8080

CMD ["python", "app/main.py"]