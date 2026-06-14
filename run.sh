#!/bin/bash
# Exit on error
set -e

echo "============================================="
echo "   AI Video Dubber & Translator Launcher     "
echo "============================================="
echo ""
echo "Starting backend server inside WSL..."
echo "You can access the premium web app at:"
echo "👉 http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server."
echo "============================================="

# Run the FastAPI app using our virtual environment python
./venv/bin/python backend/main.py
