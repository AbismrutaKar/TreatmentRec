# treatapp.py - Treatment Recommendation Service
# Runs on port 5001

import datetime
import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# load treatments from data folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TREATMENTS_PATH = os.path.join(BASE_DIR, "data", "treatments.json")

def load_treatments():
    with open(TREATMENTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
TREATMENTS = load_treatments()


# helper functions
def _lookup(condition):
    plan = TREATMENTS.get(condition)
    if plan:
        return condition, plan
    low = condition.lower()
    for key, val in TREATMENTS.items():
        if low in key.lower() or key.lower() in low:
            return key, val
    return None, None


def _build_plan(condition, plan, medibot_data=None):
    today = datetime.date.today().strftime("%B %d, %Y")
    return {
        "condition":       condition,
        "severity":        plan["severity"],
        "specialist":      plan["specialist"],
        "duration":        plan["duration"],
        "recommendations": plan["recommendations"],
        "follow_up":       plan["follow_up"],
        "doctor":          "AI Health Assistant",
        "date":            today,
        # Pass-through fields from medibot if available
        "risk":            medibot_data.get("risk")          if medibot_data else None,
        "urgency":         medibot_data.get("urgency")       if medibot_data else None,
        "severitySignal":  medibot_data.get("severitySignal") if medibot_data else None,
        "disclaimer":      medibot_data.get("disclaimer")    if medibot_data else
                           "This is not a substitute for professional medical advice.",
    }


# API routes

@app.route("/api/treatment", methods=["POST"])
def treatment_from_medibot():
    body = request.get_json(silent=True) or {}

    # Accept either { results: {...} } or the results object directly
    data = body.get("results", body)

    primary_name = data.get("primaryCondition", "").strip()
    if not primary_name:
        return jsonify({"error": "primaryCondition is required"}), 400

    # Primary condition plan
    matched_name, plan = _lookup(primary_name)
    if not plan:
        return jsonify({"error": f"No treatment plan found for '{primary_name}'"}), 404

    primary_plan = _build_plan(matched_name, plan, data)

    # Runner-up plans (conditions[1] and [2] from medibot's top-5)
    runner_ups = []
    for c in data.get("conditions", [])[1:3]:   # 2nd and 3rd conditions
        name = c.get("name", "")
        rname, rplan = _lookup(name)
        if rplan:
            runner_ups.append({
                "condition":  rname,
                "probability": c.get("probability"),
                "severity":   rplan["severity"],
                "specialist": rplan["specialist"],
                "duration":   rplan["duration"],
                "recommendations": rplan["recommendations"],
                "follow_up":  rplan["follow_up"],
            })

    return jsonify({
        "primary":    primary_plan,
        "runner_ups": runner_ups,
    }), 200


@app.route("/api/treatment", methods=["GET"])
def treatment_by_name():
    condition = request.args.get("condition", "").strip()
    if not condition:
        return jsonify({"error": "condition query param is required"}), 400

    matched_name, plan = _lookup(condition)
    if not plan:
        return jsonify({"error": f"No treatment plan found for '{condition}'"}), 404

    return jsonify(_build_plan(matched_name, plan)), 200


@app.route("/api/conditions", methods=["GET"])
def list_conditions():
    return jsonify({"count": len(TREATMENTS), "conditions": sorted(TREATMENTS.keys())}), 200


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "treatment-api",
                    "conditions": len(TREATMENTS)}), 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "Treatment Recommendation API",
        "port":    5001,
        "endpoints": {
            "POST /api/treatment": "Pass medibot results object → get full treatment plan",
            "GET  /api/treatment": "?condition=<name> → single plan lookup",
            "GET  /api/conditions": "List supported conditions",
            "GET  /api/health":    "Health check",
        }
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("TREATMENT_PORT", 5001))
    print(f"\n  [Treatment API] Running on port {port}")
    print(f"  [Treatment API] {len(TREATMENTS)} conditions loaded\n")
    app.run(host="0.0.0.0", port=port, debug=False)
