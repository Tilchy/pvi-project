FROM python:3.12.8-slim AS build

WORKDIR /app

RUN apt-get update -y && apt-get install -y curl build-essential

# Install Rust needed for nicegui
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python dependencies into a temporary directory
COPY requirements.txt /app/
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Final ---
FROM python:3.12.8-slim

WORKDIR /app

# Copy only installed packages from build stage
COPY --from=build /install /usr/local
COPY app /app/app

EXPOSE 8080

CMD ["python", "app/main.py"]
