import requests
import json
import os

class LLM:
    def __init__(self, api_key):
        self.api_key = api_key
        # Switch to lite for higher quota in 2026 environment
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={self.api_key}"

    def chat(self, prompt, system_instruction=None, history=None):
        payload = {
            "contents": [],
            "generationConfig": {
                "temperature": 0.9,
                "maxOutputTokens": 2048,
            }
        }
        
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
            
        if history:
            for msg in history:
                role = "model" if msg["role"] == "assistant" else "user"
                payload["contents"].append({"role": role, "parts": [{"text": msg["content"]}]})
        
        payload["contents"].append({"role": "user", "parts": [{"text": prompt}]})
        
        try:
            response = requests.post(self.url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Gemini API Error: {e}")
            if 'response' in locals(): print(response.text)
            return f"Error connecting to Gemini API: {str(e)}"

    def generate_json(self, prompt, system_instruction=None):
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "response_mime_type": "application/json",
            }
        }
        
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
            
        try:
            response = requests.post(self.url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text)
        except Exception as e:
            print(f"Gemini JSON Error: {e}")
            return {"error": "Failed to parse JSON", "exception": str(e)}
