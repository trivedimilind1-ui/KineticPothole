"""
Vercel Serverless Entrypoint for KineticPothole Flask Application.
"""
import os
import sys

# Add project root directory to Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app

# Vercel serverless function entrypoint
if __name__ == "__main__":
    app.run()
