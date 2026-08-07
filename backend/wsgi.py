"""Gunicorn entry point for production deployment."""
import main

application = main.app

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)
