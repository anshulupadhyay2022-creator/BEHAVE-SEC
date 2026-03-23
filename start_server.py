#!/usr/bin/env python3
"""
Quick Start Script for BEHAVE-SEC Backend
Checks dependencies and starts the server
"""

import sys
import subprocess
import os

def check_python_version():
    """Check if Python version is 3.8 or higher"""
    if sys.version_info < (3, 8):
        print("[X] Error: Python 3.8 or higher is required")
        print(f"    Current version: {sys.version}")
        sys.exit(1)
    print(f"[OK] Python version: {sys.version.split()[0]}")

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = ['fastapi', 'uvicorn', 'pydantic', 'sqlalchemy', 'sklearn', 'multipart', 'passlib', 'jose']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"[OK] {package} installed")
        except ImportError:
            missing_packages.append(package)
            print(f"[X] {package} not installed")
    
    if missing_packages:
        print("\n[!] Missing packages detected!")
        print("    Installing dependencies...\n")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("\n[OK] All dependencies installed!")

def start_server():
    """Start the FastAPI server"""
    print("\n" + "="*60)
    print("[RUN] Starting BEHAVE-SEC Backend Server")
    print("="*60)
    print("[URL] Server will run on: http://localhost:8000")
    print("[DOC] API Docs available at: http://localhost:8000/docs")
    print("[DIR] Data will be stored in: ./behavioral_data/")
    print("\n[INFO] Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Create data directory if it doesn't exist
    os.makedirs("behavioral_data", exist_ok=True)
    
    # Start the server using uvicorn correctly
    subprocess.run([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])

if __name__ == "__main__":
    print("\n[*] Checking system requirements...\n")
    check_python_version()
    check_dependencies()
    start_server()
