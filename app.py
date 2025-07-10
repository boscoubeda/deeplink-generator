from flask import Flask, request, jsonify
from urllib.parse import urlencode

app = Flask(__name__)

@app.route("/")
def index():
    return "Deeplink Generator is running."

@app.route("/generate-deeplinks", methods=["POST"])
def generate_deeplinks():
    rows = request.json.get("data", [])
    results = []

    for row in rows:
        token = row.get("token")
        deeplink = row.get("deeplink")
        campaign = row.get("campaign", "")
        adgroup = row.get("adgroup", "")
        creative = row.get("creative", "")

        if not token or not deeplink:
            results.append({**row, "deeplink_final": None, "error": "Missing token or deeplink"})
            continue

        base_url = f"https://app.adjust.com/{token}"
        params = {
            "deep_link": deeplink,
            "campaign": campaign,
            "adgroup": adgroup,
            "creative": creative
        }

        final_url = f"{base_url}?{urlencode(params)}"
        results.append({**row, "deeplink_final": final_url})

    return jsonify({"results": results})
