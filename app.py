import os
import requests
from flask import Flask, request, jsonify
from geopy.geocoders import Nominatim
from urllib.parse import urlencode

app = Flask(__name__)
geolocator = Nominatim(user_agent="deeplink-generator")

ADJUST_ENDPOINT = "https://automate.adjust.com/engage/deep-links"
DEFAULT_LINK_TOKEN = os.getenv("ADJUST_LINK_TOKEN")

ALLOWED_WEBLINK_DOMAINS = [
    "link.jobandtalent.com",
    "open.jobandtalent.com",
    "open.staging.jobandtalent.com",
    "biz.jobandtalent.com",
    "biz.staging.jobandtalent.com",
    "candidates.jobandtalent.com",
    "candidates.staging.jobandtalent.com",
    "es.jobandtalent.com",
    "jobs.jobandtalent.com",
    "jobs.staging.jobandtalent.com"
]

def validate_weblink(url):
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    if any(domain.endswith(allowed) for allowed in ALLOWED_WEBLINK_DOMAINS):
        return True
    raise ValueError("Invalid weblink: not allowed by security policy")

def resolve_order(sort_by):
    return {
        "created_at": "desc",
        "start_at": "asc",
        "location": "asc",
        "best_paid": "desc",
        "most_hours": "desc",
        "least_hours": "asc"
    }.get(sort_by, "asc")

def utm_params_to_query(utm):
    return urlencode({
        "utm_source": utm.get("utm_source", ""),
        "utm_campaign": utm.get("utm_campaign", ""),
        "utm_medium": utm.get("utm_medium", "")
    })

def geocode_address(address):
    location = geolocator.geocode(address)
    if not location:
        raise ValueError("Unable to geocode address")
    return {
        "lat": location.latitude,
        "lon": location.longitude,
        "address": location.address
    }

def build_deeplink(screen, params, utm):
    jt_domain = "jobandtalent.com"

    if screen == "jobcard":
        vacancy_request_id = params["vacancy_request_id"]
        # Simulate API call to fetch job_opportunity (mocked)
        job_opportunity_id = vacancy_request_id  # In production, you'd fetch this

        deeplink_path = f"candidates/jobs/{job_opportunity_id}"
        weblink = f"https://jobs.{jt_domain}/es/logistics/madrid/job-title"

    elif screen == "jobfeed":
        geo = geocode_address(params["full_address"])
        filters = {
            "sort_by": params["sort_by"],
            "sort_order": resolve_order(params["sort_by"]),
            "lat": geo["lat"],
            "lon": geo["lon"],
            "address": geo["address"],
            "radius": int(params.get("radius", 150)) * 1000
        }
        if params.get("categories"):
            filters["categories"] = params["categories"].replace(" ", "")

        deeplink_path = f"job_opportunities/country/{params['country_code']}?{urlencode(filters)}&{utm_params_to_query(utm)}"
        weblink = f"https://jobs.{jt_domain}/{params['country_code'].lower()}?{utm_params_to_query(utm)}"

    elif screen == "checkout":
        deeplink_path = f"checkout_flow/{params['checkout_id']}/{params['candidate_id']}?{utm_params_to_query(utm)}"
        weblink = f"https://es.{jt_domain}/checkout"

    else:
        raise ValueError("Invalid screen type")

    validate_weblink(weblink)
    return deeplink_path, weblink

@app.route("/generate-deeplink", methods=["POST"])
def generate_deeplink():
    data = request.json

    try:
        screen = data["screen"]
        params = data["params"]
        utm = data.get("utm", {})
        link_token = data.get("link_token") or DEFAULT_LINK_TOKEN

        if not link_token:
            return jsonify({"error": "Missing Adjust link_token"}), 400

        deeplink_path, weblink = build_deeplink(screen, params, utm)

        payload = {
            "link_token": link_token,
            "shorten_url": True,
            "ios_deep_link_path": deeplink_path,
            "android_deep_link_path": deeplink_path,
            "fallback": weblink,
            "redirect_macos": weblink
        }

        headers = {
            "Authorization": f"Bearer {os.getenv('ADJUST_API_TOKEN')}",
            "Content-Type": "application/json"
        }

        response = requests.post(ADJUST_ENDPOINT, headers=headers, json=payload)

        if response.status_code != 200:
            return jsonify({"error": "Adjust API error", "details": {"raw_response": response.text}}), 400

        deeplink = response.json().get("url")
        return jsonify({"deeplink_final": deeplink}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return "Deeplink Generator API is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
