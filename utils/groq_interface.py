import os
import requests
import json
import re

with open("config.json") as f:
    config = json.load(f)

# Prefer environment variable to avoid committing secrets
API_KEY = os.getenv("GROQ_API_KEY") or config.get("groq_api_key", "")
MODEL = config.get("groq_model", "llama3-8b-8192")

def extract_meeting_info(user_input):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
Extract the following details from this message:
- List of emails
- Start date (YYYY-MM-DD)
- Time (HH:MM 24hr format)
- Number of days

Message: "{user_input}"

Return ONLY this JSON structure (no explanation):
{{
  "emails": ["email1@example.com", "email2@example.com"],
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "days": <number>
}}
"""

    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that extracts meeting scheduling info."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    try:
        if not API_KEY:
            return {
                "error": (
                    "Missing GROQ API key. Set environment variable 'GROQ_API_KEY' "
                    "or add 'groq_api_key' to config.json."
                )
            }

        response = requests.post(url, headers=headers, json=data, timeout=30)

        # Debug info (safe)
        print("Groq API Response Code:", response.status_code)

        # Handle non-200s with clearer messages
        if response.status_code != 200:
            try:
                err_json = response.json()
            except Exception:
                err_json = {"raw": response.text}

            # Special-case 401 for clearer guidance
            if response.status_code == 401:
                return {
                    "error": (
                        "Groq API Error 401: Invalid or missing API key. "
                        "Verify your 'GROQ_API_KEY' and that it has not been revoked."
                    ),
                    "details": err_json,
                }

            return {"error": f"Groq API Error {response.status_code}", "details": err_json}

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # Extract and parse the JSON from the content
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        else:
            return {"error": "Failed to extract JSON from model output."}

    except json.JSONDecodeError:
        return {"error": "Groq returned non-JSON response. Check API key or server status."}
    except Exception as e:
        return {"error": str(e)}
