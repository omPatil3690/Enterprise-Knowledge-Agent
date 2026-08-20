import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("NOTION_PAGE_ID")

url = f"https://api.notion.com/v1/blocks/{PAGE_ID}"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2026-03-11",
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)
data = response.json()

with open("./test_data/test_notion1.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("Response saved to test_notion.json")