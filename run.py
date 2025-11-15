#!/usr/bin/env python3
"""
Entry point for running the Flask application.
"""
from app.app import app

if __name__ == '__main__':
    app.run(debug=True, port=5001)

