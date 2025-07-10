import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ADJUST_API_URL = "https://automate.adjust.com/engage/deep-links"
LINK_TOKEN = os.getenv("ADJUST_LINK_TOKEN")
JT_DOMAIN = os.getenv("JT_DOMAIN", "jobandtalent.com")

# Dummy geocoding function for jobfeed
# In producción, deberías usar un servicio como Google Maps API

def geocode_address(address):
    return {
        "lat": 40.4168,
        "lon": -3.7038,
        "address": address
    }


def build_adjust_link(link_token, deeplink, weblink):
    headers = {
        "Authorization": f"Bearer {os.getenv('ADJUST_API_TOKEN')}",
        "Content-Type": "application/json"
    }
    payload = {
        "link_token": link_token,
        "shorten_url": True,
        "ios_deep_link_path": deeplink,
        "android_deep_link_path": deeplink,
        "fallback": weblink,
        "redirect_macos": weblink
    }

    response = requests.post(ADJUST_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json().get("url")
    else:
        return jsonify({"error": "Adjust API error", "details": response.text}), 400


@app.route("/")
def index():
    return "Adjust Deeplink Generator"


@app.route("/generate-deeplink", methods=["POST"])
def generate_deeplink():
    data = request.json
    screen = data.get("screen")
    params = data.get("params", {})
    utm = data.get("utm", {})
    link_token = data.get("link_token") or LINK_TOKEN

    if not link_token:
        return jsonify({"error": "Missing Adjust link_token"}), 400

    if screen == "jobcard":
        vacancy_id = params.get("vacancy_request_id")
        if not vacancy_id:
            return jsonify({"error": "Missing vacancy_request_id"}), 400

        deeplink_path = f"candidates/jobs/{vacancy_id}"
        deeplink = f"{deeplink_path}?utm_source={utm.get('utm_source')}&utm_campaign={utm.get('utm_campaign')}&utm_medium={utm.get('utm_medium')}"
        weblink = f"https://jobs.{JT_DOMAIN}/es/logistics/madrid/slug?utm_source={utm.get('utm_source')}&utm_campaign={utm.get('utm_campaign')}&utm_medium={utm.get('utm_medium')}"

        return build_adjust_link(link_token, deeplink, weblink)

    elif screen == "jobfeed":
        country = params.get("country_code")
        sort_by = params.get("sort_by")
        address = params.get("full_address")
        radius = int(params.get("radius", 150)) * 1000
        categories = params.get("categories", "").replace(" ", "")

        if not country or not sort_by or not address:
            return jsonify({"error": "Missing required jobfeed parameters"}), 400

        geo = geocode_address(address)
        query_params = [
            f"sort_by={sort_by}",
            f"sort_order={'desc' if sort_by in ['created_at', 'best_paid', 'most_hours'] else 'asc'}",
            f"lat={geo['lat']}",
            f"lon={geo['lon']}",
            f"address={geo['address']}",
            f"radius={radius}"
        ]
        if categories:
            query_params.append(f"categories={categories}")

        utm_params = f"utm_source={utm.get('utm_source')}&utm_campaign={utm.get('utm_campaign')}&utm_medium={utm.get('utm_medium')}"
        query_string = "&".join(query_params)

        deeplink_path = f"job_opportunities/country/{country}"
        deeplink = f"{deeplink_path}?{query_string}&{utm_params}"
        weblink = f"https://jobs.{JT_DOMAIN}/{country.lower()}?{utm_params}"

        return build_adjust_link(link_token, deeplink, weblink)

    elif screen == "checkout":
        candidate_id = params.get("candidate_id")
        checkout_id = params.get("checkout_id")

        if not candidate_id or not checkout_id:
            return jsonify({"error": "Missing checkout parameters"}), 400

        deeplink_path = f"checkout/{candidate_id}/{checkout_id}"
        deeplink = f"{deeplink_path}?utm_source={utm.get('utm_source')}&utm_campaign={utm.get('utm_campaign')}&utm_medium={utm.get('utm_medium')}"
        weblink = f"https://jobs.{JT_DOMAIN}/checkout/{candidate_id}/{checkout_id}?utm_source={utm.get('utm_source')}&utm_campaign={utm.get('utm_campaign')}&utm_medium={utm.get('utm_medium')}"

        return build_adjust_link(link_token, deeplink, weblink)

    else:
        return jsonify({"error": "Unsupported screen"}), 400
