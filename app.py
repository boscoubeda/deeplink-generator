import os
import re
import requests
from flask import Flask, request, jsonify
from urllib.parse import urlencode

app = Flask(__name__)

ADJUST_API_TOKEN = os.getenv("ADJUST_API_TOKEN")

# Patrones permitidos para fallback
ALLOWED_WEBLINK_PATTERNS = [
    r"^https?:\/\/link\.jobandtalent\.com([\/#\?].*)?$",
    r"^https?:\/\/open\.jobandtalent\.com([\/#\?].*)?$",
    r"^https?:\/\/open\.staging\.jobandtalent\.com([\/#\?].*)?$",
    r"^https?:\/\/biz\.jobandtalent\.com([\/#\?].*)?$",
    r"^https?:\/\/biz\.staging\.jobandtalent\.com([\/#\?].*)?$",
    r"^https:\/\/(candidates\.staging\.jobandtalent\.com|candidates\.jobandtalent\.com)(\/.*)?$",
    r"^https:\/\/es\.jobandtalent\.com(\/.*)?$",
    r"^https:\/\/(jobs\.staging\.jobandtalent\.com|jobs\.jobandtalent\.com)(\/.*)?$"
]

def is_weblink_allowed(weblink):
    for pattern in ALLOWED_WEBLINK_PATTERNS:
        if re.match(pattern, weblink):
            return True
    return False

def build_deeplink_path(screen, params):
    query = urlencode(params)
    return f"{screen}?{query}"

@app.route("/")
def home():
    return "Adjust Deep Link Builder is running."

@app.route("/generate-deeplink", methods=["POST"])
def generate_deeplink():
    payload = request.get_json()

    link_token = payload.get("link_token")
    screen = payload.get("screen")
    params = payload.get("params", {})
    fallback = payload.get("fallback")

    if not link_token or not screen or not fallback:
        return jsonify({"error": "Missing one or more required fields: link_token, screen, fallback"}), 400

    if not is_weblink_allowed(fallback):
        return jsonify({"error": f"Fallback URL not allowed by security policy: {fallback}"}), 400

    deeplink_path = build_deeplink_path(screen, params)

    adjust_payload = {
        "link_token": link_token,
        "shorten_url": True,
        "ios_deep_link_path": deeplink_path,
        "android_deep_link_path": deeplink_path,
        "fallback": fallback,
        "redirect_macos": fallback
    }

    headers = {
        "Authorization": f"Bearer {ADJUST_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://automate.adjust.com/engage/deep-links",
            headers=headers,
            json=adjust_payload
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Adjust API error", "details": str(e)}), 500

    try:
        short_url = response.json().get("url")
    except Exception:
        return jsonify({"error": "Invalid JSON from Adjust", "raw": response.text}), 500

    if not short_url:
        return jsonify({"error": "No shortlink returned"}), 500

    return jsonify({"deeplink_final": short_url})
