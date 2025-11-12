import json

with open("config.json") as f:
    config = json.load(f)

def get_calendly_link():
    return config.get("calendly_link")
