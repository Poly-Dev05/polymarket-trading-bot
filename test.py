import requests
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("GET_POSITIONS_URL")

params = {
    "market": os.getenv("MARKET"),
    "status": "OPEN",
    "limit": 50,
    "user": os.getenv("FUNDER")
}

response = requests.get(url, params=params)

print(response.status_code)
print(response.json())
