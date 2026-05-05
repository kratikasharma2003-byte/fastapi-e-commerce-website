# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://new-fastapi-e-commerce-website.onrender.com")
APP_HOST = os.getenv("APP_HOST", "https://new-fastapi-e-commerce-website.onrender.com")