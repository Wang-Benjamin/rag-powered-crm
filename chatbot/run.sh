#!/bin/bash
set -a
source .env
set +a

# Activate virtual environment and run the server
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload