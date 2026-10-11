import sys
import requests

API_URL = "http://127.0.0.1:8000/api/v1/verify-credential"

def test_file(file_path: str):
    with open(file_path, "rb") as f:
        files = {"file": f}
        print(f"Uploading {file_path} to LatchOS pipeline...")
        response = requests.post(API_URL, files=files)
        print(f"Status: {response.status_code}")
        print("Response JSON:")
        print(response.json())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <path_to_image_or_pdf>")
    else:
        test_file(sys.argv[1])