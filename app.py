import os
import re
import requests
from flask import Flask, request, jsonify
from urllib.parse import urlencode
from geopy.geocoders import Nominatim

app = Flask(__name__)

# Config
ADJUST_API_TOKEN = os.getenv("ADJUST_API_TOKEN")
ADJUST_LINK_TOKEN = os.getenv("ADJUST_LINK_TOKEN")
ADJUST_API_URL = "https://automate.adjust.com/engage/deep-links"

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
    return any(re.match(pattern, weblink) for pattern in ALLOWED_WEBLINK_PATTERNS)

def build_utm_query(utm):
    return urlencode({k: v for k, v in utm.items() if v}) if utm else ""

def fetch_job_opportunity(vacancy_request_id):
    url = f"https://jobs.jobandtalent.com/api-external/v1/job_opportunities/vacancy_request/{vacancy_request_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()["data"]["job_opportunity"]

def generate_jobcard(params, utm_query):
    vacancy_id = params.get("vacancy_request_id")
    if not vacancy_id:
        return None, None, "Missing vacancy_request_id for jobcard"

    job = fetch_job_opportunity(vacancy_id)
    deeplink_path = f"candidates/jobs/{job['id']}"
    fallback = f"https://jobs.jobandtalent.com/{job['geodatum']['country']['country_code'].lower()}/{job['job_function_slug']}/{job['geodatum']['subdivision']['slug']}/{job['slug']}"
    if utm_query:
        fallback += f"?{utm_query}"

    if not is_weblink_allowed(fallback):
        return None, None, "Fallback URL not allowed"

    return deeplink_path, fallback, None

def generate_jobfeed(params, utm_query):
    country_code = params.get("country_code")
    sort_by = params.get("sort_by")
    full_address = params.get("full_address")
    radius = float(params.get("radius", 150)) * 1000
    categories = params.get("categories")

    if not (country_code and sort_by and full_address):
        return None, None, "Missing required jobfeed params"

    geolocator = Nominatim(user_agent="jobandtalent-deeplink")
    location = geolocator.geocode(full_address)
    if not location:
        return None, None, "Location not found"

    filters = {
        "sort_by": sort_by,
        "sort_order": "asc" if sort_by in ["start_at", "location", "least_hours"] else "desc",
        "lat": location.latitude,
        "lon": location.longitude,
        "address": location.address,
        "radius": int(radius)
    }
    if categories:
        filters["categories"] = categories.replace(" ", "")

    query = urlencode(filters)
    deeplink_path = f"job_opportunities/country/{country_code}?{query}"
    fallback = f"https://jobs.jobandtalent.com/{country_code.lower()}"
    if utm_query:
        fallback += f"?{utm_query}"

    return deeplink_path, fallback, None

def generate_checkout(params, utm_query):
    candidate_id = params.get("candidate_id")
    checkout_id = params.get("checkout_id")
    if not candidate_id or not checkout_id:
        return None, None, "Missing candidate_id or checkout_id"

    deeplink_path = f"checkout_flow/{checkout_id}/{candidate_id}"
    fallback = "https://es.jobandtalent.com/checkout"
    if utm_query:
        fallback += f"?{utm_query}"

    return deeplink_path, fallback, None

@app.route("/")
def home():
    return "Adjust Deep Link Builder is running."

@app.route("/generate-deeplink", methods=["POST"])
def generate_deeplink():
    payload = request.get_json()

    screen = payload.get("screen")
    params = payload.get("params", {})
    utm = payload.get("utm", {})
    utm_query = build_utm_query(utm)

    link_token = payload.get("link_token") or ADJUST_LINK_TOKEN
    if not screen:
        return jsonify({"error": "Missing required field: screen"}), 400
    if not link_token:
        return jsonify({"error": "Missing link_token and no default available"}), 400

    generators = {
        "jobcard": generate_jobcard,
        "jobfeed": generate_jobfeed,
        "checkout": generate_checkout
    }

    if screen not in generators:
        return jsonify({"error": f"Screen '{screen}' not supported yet."}), 400

    try:
        deeplink_path, fallback, err = generators[screen](params, utm_query)
        if err:
            return jsonify({"error": err}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to generate {screen} deeplink", "details": str(e)}), 400

    path_with_utm = deeplink_path + (f"?{utm_query}" if utm_query and "?" not in deeplink_path else "")

    adjust_payload = {
        "link_token": link_token,
        "shorten_url": True,
        "ios_deep_link_path": path_with_utm,
        "android_deep_link_path": path_with_utm,
        "fallback": fallback,
        "redirect_macos": fallback
    }

    headers = {
        "Authorization": f"Bearer {ADJUST_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(ADJUST_API_URL, headers=headers, json=adjust_payload)
        response.raise_for_status()
        return short_url, 200, {'Content-Type': 'text/plain'}
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Adjust API error", "details": str(e)}), 500
