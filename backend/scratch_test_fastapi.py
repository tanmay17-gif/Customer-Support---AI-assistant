import sys
sys.path.insert(0, r"c:\Users\tanmay\Documents\CS_Assistant\backend")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

response = client.get("/api/v1/emails/")
print("Status Code:", response.status_code)
print("Response:", response.text)
