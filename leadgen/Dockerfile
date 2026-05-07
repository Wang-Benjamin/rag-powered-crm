# ./prelude-leadgen/Dockerfile
# Build context: Must be run from prelude/ directory (parent)
# Command: cd prelude && docker build -f prelude-leadgen/Dockerfile .

# --- Stage 1: Builder (Installs dependencies in a virtual environment) ---
FROM python:3.12-slim AS builder

# Set the working directory for the builder stage
WORKDIR /app/lead-gen-build

# --- Install build dependencies and Playwright system dependencies ---
RUN apt-get update && \
    apt-get install -y git python3-venv \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libxrandr2 \
    libxss1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libatspi2.0-0 \
    libx11-xcb1 \
    libxcursor1 \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# --- Create a virtual environment and install dependencies into it ---
RUN python3 -m venv /opt/venv

# Copy shared packages from parent context and requirements
COPY prelude-csv /app/lead-gen-build/prelude-csv
COPY prelude-shared /app/lead-gen-build/prelude-shared
COPY prelude-leadgen/requirements.txt .

# Fix the relative paths in requirements.txt for Docker build context
RUN sed -i 's|-e \.\./prelude-csv|./prelude-csv|g' requirements.txt && \
    sed -i 's|-e \.\./prelude-shared|./prelude-shared|g' requirements.txt

# Install dependencies (csv-mapping-lib will be found via relative path)
RUN . /opt/venv/bin/activate && pip install --no-cache-dir -r requirements.txt

# --- Install Playwright browsers to a specific directory ---
ENV PLAYWRIGHT_BROWSERS_PATH="/opt/venv/playwright-browsers"
RUN . /opt/venv/bin/activate && PLAYWRIGHT_BROWSERS_PATH=/opt/venv/playwright-browsers playwright install chromium

# --- Stage 2: Final Runtime (Uses the virtual environment, does NOT include git) ---
FROM python:3.12-slim

# --- Install Tini and runtime dependencies for Playwright ---
RUN apt-get update && apt-get install -y tini \
    # Runtime dependencies for Playwright browsers
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libxrandr2 \
    libxss1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libatspi2.0-0 \
    libx11-xcb1 \
    libxcursor1 \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# --- Copy ONLY the created virtual environment from the builder stage ---
COPY --from=builder /opt/venv /opt/venv

# --- Create and switch to a non-root user (after copying venv) ---
RUN adduser --system --no-create-home appuser && \
    chown -R appuser:nogroup /opt/venv
USER appuser

# Set the working directory for the application
WORKDIR /app/lead_gen

# Copy the application source code
COPY prelude-leadgen/ .

# --- Set PATH to include the virtual environment's bin directory ---
ENV PATH="/opt/venv/bin:$PATH"

# --- Set Playwright browsers path to match builder stage ---
ENV PLAYWRIGHT_BROWSERS_PATH="/opt/venv/playwright-browsers"

# --- Use Tini as ENTRYPOINT ---
ENTRYPOINT ["/usr/bin/tini", "--"]

# CMD to run your application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}

# EXPOSE the port
EXPOSE 8080
