import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("NOTION_PAGE_ID")

url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2026-03-11",
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)
data = response.json()

# with open("./test_data/test_notion1.json", "w", encoding="utf-8") as f:
#     json.dump(data, f, indent=4, ensure_ascii=False)

# print("Response saved to test_notion.json")

print(data, end="\n\n")

print("Object:", data.get("object"))
print("Number of blocks:", len(data.get("results", [])))
print("Has more:", data.get("has_more"))
print("Next cursor:", data.get("next_cursor"))

for block in data["results"]:
    print()
    print("ID:", block["id"])
    print("Type:", block["type"])
    print("Has children:", block["has_children"])


for block in data["results"]:
    block_type = block["type"]

    print("\nTYPE:", block_type)

    content = block.get(block_type)

    print(content)
