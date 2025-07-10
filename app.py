import os
import requests
from flask import Flask, request, jsonify
from urllib.parse import urlencode

app = Flask(__name__)

# Cargar variables de entorno
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
        return None

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
    campaign = payload.get("campaign", "")
    adgroup = payload.get("adgroup", "")
    creative = payload.get("creative", "")

    if screen not in {"jobfeed", "jobcard", "checkout"}:
        return jsonify({"error": f"Invalid screen type: {screen}"}), 400

    deep_link = build_deeplink(screen, params)
    if not deep_link:
        return jsonify({"error": "Could not construct deep_link"}), 400

    # Construir payload según Adjust Shortlink API
    request_payload = {
        "adjust_link": {
            "app_token": APP_TOKEN,
            "deep_link": deep_link,
            "campaign": campaign,
            "adgroup": adgroup,
            "creative": creative,
            "utm_parameters": {
                "utm_source": utm.get("utm_source", ""),
                "utm_campaign": utm.get("utm_campaign", ""),
                "utm_medium": utm.get("utm_medium", "")
            }
        }
    }

    headers = {
        "Authorization": f"Token {ADJUST_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://shortlink.adjust.net/link",
        headers=headers,
        json=request_payload
    )

    if response.status_code != 200:
        try:
            error_details = response.json()
        except ValueError:
            error_details = {"raw_response": response.text}
        return jsonify({"error": "Adjust API error", "details": error_details}), 400

    shortlink = response.json().get("shortlink")

    if not shortlink:
        return jsonify({"error": "Shortlink creation succeeded but no link returned"}), 500

    return jsonify({
        "deeplink_final": shortlink
    })
