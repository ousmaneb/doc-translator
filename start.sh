#!/bin/bash
# Start the DocTranslator Python app
cd "$(dirname "$0")"
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
