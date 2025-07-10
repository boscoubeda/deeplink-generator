import os
import re
import requests
from flask import Flask, request, jsonify
from urllib.parse import urlencode

app = Flask(__name__)

ADJUST_API_TOKEN = os.getenv("ADJUST_API_TOKEN")
ADJUST_LINK_TOKEN = os.getenv("ADJUST_LINK_TOKEN")  # <- NUEVO

ALLOWED_WEBLINK_PATTERNS = [
    r"^https?:\/\/link\.jobandtalent\.com([\/\#\?].*)?$",
    r"^https?:\/\/open\.jobandtalent\.com([\/\#\?].*)?$",
    r"^https?:\/\/open\.staging\.jobandtalent\.com([\/\#\?].*)?$",
    r"^https?:\/\/biz\.jobandtalent\.com([\/\#\?].*)?$",
    r"^https?:\/\/biz\.staging\.jobandtalent\.com([\/\#\?].*)?$",
    r"^https:\/\/(candidates\.staging\.jobandtalent\.com|candidates\.jobandtalent\.com)(\/.*)?$",
    r"^https:\/\/es\.jobandtalent\.com(\/.*)?$",
    r"^https:\/\/(jobs\.staging\.jobandtalent\.com|jobs\.jobandtalent\.com)(\/.*)?$"
]

def is_weblink_allowed(weblink):
    for pattern in ALLOWED_WEBLINK_PATTERNS:
        if re.match(pattern, weblink):
            return True
    return False

def build_utm_query(utm):
    if not utm:
        return ""
    return urlencode({k: v for k, v in utm.items() if v})

def fetch_job_opportunity(vacancy_request_id):
    url = f"https://jobs.jobandtalent.com/api-external/v1/job_opportunities/vacancy_request/{vacancy_request_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()["data"]["job_opportunity"]

@app.route("/")
def home():
    return "Adjust Deep Link Builder is running."

@app.route("/generate-deeplink", methods=["POST"])
def generate_deeplink():
    payload = request.get_json()

    screen = payload.get("screen")
    params = payload.get("params", {})
    utm = payload.get("utm", {})

    if not ADJUST_LINK_TOKEN or not screen:
        return jsonify({"error": "Missing required fields: screen or link_token not set in env"}), 400

    # JOBCARD
    if screen == "jobcard":
        vacancy_id = params.get("vacancy_request_id")
        if not vacancy_id:
            return jsonify({"error": "Missing vacancy_request_id for jobcard"}), 400

        try:
            job = fetch_job_opportunity(vacancy_id)
        except Exception as e:
            return jsonify({"error": "Failed to fetch job opportunity", "details": str(e)}), 400

        deeplink_path = f"candidates/jobs/{job['id']}"
        utm_query = build_utm_query(utm)

        fallback = f"https://jobs.jobandtalent.com/{job['geodatum']['country']['country_code'].lower()}/{job['job_function_slug']}/{job['geodatum']['subdivision']['slug']}/{job['slug']}"
        if utm_query:
            fallback += f"?{utm_query}"

        if not is_weblink_allowed(fallback):
            return jsonify({"error": "Fallback URL not allowed", "fallback": fallback}), 400

        adjust_payload = {
            "link_token": ADJUST_LINK_TOKEN,
            "shorten_url": True,
            "ios_deep_link_path": deeplink_path + (f"?{utm_query}" if utm_query else ""),
            "android_deep_link_path": deeplink_path + (f"?{utm_query}" if utm_query else ""),
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
            short_url = response.json().get("url")
            if not short_url:
                return jsonify({"error": "Adjust API did not return a URL"}), 500
            return jsonify({"deeplink_final": short_url})
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Adjust API error", "details": str(e)}), 500

    return jsonify({"error": f"Screen '{screen}' not supported yet."}), 400
