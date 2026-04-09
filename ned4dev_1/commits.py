import os, requests

def get_commits():
    key = os.getenv("HARNESS_API_KEY")
    headers={"x-api-key":key}
    r = requests.get("https://app.harness.io/ng/api/commits",headers=headers)
    return r.json()
