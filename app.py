import os
import requests
from flask import Flask, request, jsonify
from urllib.parse import urlencode

app = Flask(__name__)

ADJUST_TOKEN = os.getenv("ADJUST_API_TOKEN")
APP_TOKEN = os.getenv("ADJUST_APP_TOKEN")

def build_deeplink(screen, params):
    if screen == "jobfeed":
        query = {
            "country_code": params.get("country_code", ""),
            "sort_by": params.get("sort_by", ""),
            "full_address": params.get("full_address", ""),
            "radius": params.get("radius", ""),
            "categories": params.get("categories", "")
        }
    elif screen == "jobcard":
        query = {
            "vacancy_request_id": params.get("vacancy_request_id", "")
        }
    elif screen == "checkout":
        query = {
            "candidate_id": params.get("candidate_id", ""),
            "checkout_id": params.get("checkout_id", "")
        }
    else:
        return None  # pantalla no válida

    return f"myapp://{screen}?{urlencode(query)}"

@app.route("/")
def home():
    return "Adjust Deeplink Generator is up."

@app.route("/generate-deeplink", methods=["POST"])
def generate_deeplink():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No JSON body found"}), 400

    screen = payload.get("screen")
    params = payload.get("params", {})
    utm = payload.get("utm", {})
    tracker_data = {
        "name": payload.get("name", "Unnamed Link"),
        "campaign": payload.get("campaign", ""),
        "adgroup": payload.get("adgroup", ""),
        "creative": payload.get("creative", ""),
        "deep_link": build_deeplink(screen, params),
    }

    if not tracker_data["deep_link"]:
        return jsonify({"error": "Invalid screen type or missing params"}), 400

    headers = {
        "Authorization": f"Token {ADJUST_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"https://api.adjust.com/trackers?app_token={APP_TOKEN}",
        headers=headers,
        json={"tracker": tracker_data}
    )

    if response.status_code != 201:
        return jsonify({"error": "Adjust API error", "details": response.json()}), 400

    tracker_token = response.json()["tracker"]["tracker_token"]

    # Armar deeplink final con utm tags
    adjust_url = f"https://app.adjust.com/{tracker_token}"
    query_params = {
        "deep_link": tracker_data["deep_link"],
        "utm_source": utm.get("utm_source", ""),
        "utm_campaign": utm.get("utm_campaign", ""),
        "utm_medium": utm.get("utm_medium", "")
    }
    full_link = f"{adjust_url}?{urlencode(query_params)}"

    return jsonify({
        "tracker_token": tracker_token,
        "deeplink_final": full_link
    })
