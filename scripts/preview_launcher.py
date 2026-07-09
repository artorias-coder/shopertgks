import sys

PROJECT_ROOT = "/Users/artemkornikov/Documents/KSTGShop"
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(f"{PROJECT_ROOT}/.env")

import os

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{PROJECT_ROOT}/preview.db"
os.environ["WEBHOOK_URL"] = ""
os.environ["REDIS_URL"] = ""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
