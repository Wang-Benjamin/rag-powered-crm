# ./prelude-crm/Dockerfile
# Build context: Must be run from prelude/ directory (parent)
# Command: cd prelude && docker build -f prelude-crm/Dockerfile .

# --- Stage 1: Builder (Installs dependencies in a virtual environment) ---
FROM python:3.12-slim AS builder

# Set the working directory for the builder stage
WORKDIR /app/crm-build

# --- Install build dependencies (like Git and the venv package) ---
RUN apt-get update && \
    apt-get install -y git python3-venv && \
    rm -rf /var/lib/apt/lists/*

# --- Create a virtual environment and install dependencies into it ---
RUN python3 -m venv /opt/venv

# Copy shared packages from parent context and requirements
COPY prelude-csv /app/crm-build/prelude-csv
COPY prelude-shared /app/crm-build/prelude-shared
COPY prelude-crm/requirements.txt .

# Fix the relative paths in requirements.txt for Docker build context
RUN sed -i 's|-e \.\./prelude-csv|./prelude-csv|g' requirements.txt && \
    sed -i 's|-e \.\./prelude-shared|./prelude-shared|g' requirements.txt

# Install dependencies (csv-mapping-lib will be found via relative path)
RUN . /opt/venv/bin/activate && pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Runtime (Uses the virtual environment, does NOT include git) ---
FROM python:3.12-slim

# --- Install Tini in the final stage ---
RUN apt-get update && apt-get install -y tini && rm -rf /var/lib/apt/lists/*

# --- Optional: Create and switch to a non-root user ---
RUN adduser --system --no-create-home appuser
USER appuser

# --- Copy ONLY the created virtual environment from the builder stage ---
COPY --from=builder /opt/venv /opt/venv

# Set the final working directory for the application
WORKDIR /app/prelude-crm

# Copy the application source code
COPY --chown=appuser:nogroup prelude-crm/ .

# --- Set PATH to include the virtual environment's bin directory ---
ENV PATH="/opt/venv/bin:$PATH"

# --- Prevent Python from writing bytecode files (.pyc) ---
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# --- Use Tini as ENTRYPOINT ---
ENTRYPOINT ["/usr/bin/tini", "--"]

# CMD to run your application via main.py which handles PORT environment variable
CMD ["python", "main.py"]

# EXPOSE the port
EXPOSE 8080
