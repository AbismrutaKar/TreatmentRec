#!/usr/bin/env python3
"""
treatapp.py  —  Treatment Recommendation Service
Runs on port 5001 (medibot_api runs on 5000)

Accepts the exact output that medibot_api._build_results() returns and
maps every condition name to a structured treatment plan.

Endpoints
─────────
POST /api/treatment          body: { "results": <medibot results object> }
GET  /api/treatment          ?condition=Common Cold
GET  /api/conditions         list all 32 supported condition names
GET  /api/health
"""

import datetime
import os
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Treatment plans — keyed by the exact condition names medibot produces
# (matches CONDITIONS list in medibot.py / medibot_api._build_results output)

TREATMENTS = {
    "Common Cold": {
        "severity": "Low", "specialist": "General Physician", "duration": "7–10 days",
        "recommendations": [
            {"type": "Rest",       "description": "7–10 days of adequate rest"},
            {"type": "Fluids",     "description": "Drink 8–10 glasses of water daily"},
            {"type": "Medication", "description": "OTC antihistamines or decongestants; throat lozenges"},
        ],
        "follow_up": "If symptoms persist beyond 10 days, consult a doctor.",
    },
    "Influenza (Flu)": {
        "severity": "Medium", "specialist": "General Physician", "duration": "5–7 days",
        "recommendations": [
            {"type": "Medication", "description": "Antiviral (Oseltamivir) within 48 h of onset"},
            {"type": "Rest",       "description": "Strict bed rest; isolate until 24 h fever-free"},
            {"type": "Fluids",     "description": "Acetaminophen/ibuprofen for fever; stay hydrated"},
        ],
        "follow_up": "Seek ER if breathing difficulty or persistent chest pain.",
    },
    "COVID-19": {
        "severity": "High", "specialist": "Infectious Disease / Pulmonologist", "duration": "10–14 days",
        "recommendations": [
            {"type": "Isolate",    "description": "Isolate immediately for at least 5 days"},
            {"type": "Monitor",    "description": "Check SpO₂ regularly — ER if below 94%"},
            {"type": "Medication", "description": "Paracetamol for fever; antivirals if prescribed"},
        ],
        "follow_up": "Contact doctor if symptoms worsen; follow local public-health guidance.",
    },
    "Pneumonia": {
        "severity": "High", "specialist": "Pulmonologist", "duration": "2–4 weeks",
        "recommendations": [
            {"type": "Emergency",  "description": "Seek immediate medical evaluation"},
            {"type": "Medication", "description": "Antibiotics (Amoxicillin/Azithromycin) as prescribed"},
            {"type": "Oxygen",     "description": "Supplemental oxygen if SpO₂ is low"},
        ],
        "follow_up": "Follow-up chest X-ray 4–6 weeks after recovery.",
    },
    "Asthma": {
        "severity": "Medium", "specialist": "Pulmonologist / Allergist", "duration": "Chronic — ongoing",
        "recommendations": [
            {"type": "Inhaler",    "description": "Use rescue inhaler (salbutamol) as prescribed"},
            {"type": "Avoid",      "description": "Identify and avoid personal triggers"},
            {"type": "Preventer",  "description": "Take preventer inhaler daily as prescribed"},
        ],
        "follow_up": "ER immediately if rescue inhaler gives no relief.",
    },
    "Bronchitis": {
        "severity": "Low", "specialist": "General Physician", "duration": "1–3 weeks",
        "recommendations": [
            {"type": "Rest",       "description": "Increase fluids and rest"},
            {"type": "Steam",      "description": "Steam inhalation to loosen mucus"},
            {"type": "Avoid",      "description": "Avoid smoking and air pollutants"},
        ],
        "follow_up": "See a doctor if cough persists beyond 3 weeks.",
    },
    "Allergic Rhinitis": {
        "severity": "Low", "specialist": "Allergist / ENT", "duration": "Seasonal — ongoing",
        "recommendations": [
            {"type": "Medication", "description": "Antihistamines (loratadine/cetirizine) daily"},
            {"type": "Spray",      "description": "Intranasal corticosteroid spray"},
            {"type": "Avoid",      "description": "Minimise allergen exposure when possible"},
        ],
        "follow_up": "Consider allergy testing for long-term management.",
    },
    "Migraine": {
        "severity": "Medium", "specialist": "Neurologist", "duration": "4–72 h per episode",
        "recommendations": [
            {"type": "Rest",       "description": "Rest in a dark, quiet room during attacks"},
            {"type": "Medication", "description": "Triptans (Sumatriptan) or NSAIDs early in attack"},
            {"type": "Diary",      "description": "Track triggers with a headache diary"},
        ],
        "follow_up": "Consult neurologist if attacks exceed 4 per month.",
    },
    "Tension Headache": {
        "severity": "Low", "specialist": "General Physician", "duration": "Hours",
        "recommendations": [
            {"type": "Medication", "description": "OTC ibuprofen or paracetamol"},
            {"type": "Heat",       "description": "Warm compress on neck and shoulders"},
            {"type": "Lifestyle",  "description": "Improve posture; take regular screen breaks"},
        ],
        "follow_up": "Persistent daily headaches warrant a neurological evaluation.",
    },
    "Sinusitis": {
        "severity": "Low", "specialist": "ENT (Otolaryngologist)", "duration": "7–10 days",
        "recommendations": [
            {"type": "Irrigation", "description": "Saline nasal irrigation (Neti pot)"},
            {"type": "Steam",      "description": "Steam inhalation for congestion relief"},
            {"type": "Medication", "description": "OTC decongestants short-term; antibiotics only if bacterial"},
        ],
        "follow_up": "See a doctor if symptoms last more than 10 days.",
    },
    "Gastroenteritis": {
        "severity": "Medium", "specialist": "Gastroenterologist", "duration": "2–5 days",
        "recommendations": [
            {"type": "Hydration",  "description": "Oral Rehydration Salts (ORS) frequently"},
            {"type": "Diet",       "description": "BRAT diet: Banana, Rice, Applesauce, Toast"},
            {"type": "Avoid",      "description": "Avoid dairy, caffeine, and alcohol"},
        ],
        "follow_up": "ER if unable to keep fluids down for more than 24 hours.",
    },
    "Acid Reflux / GERD": {
        "severity": "Low", "specialist": "Gastroenterologist", "duration": "Chronic — ongoing",
        "recommendations": [
            {"type": "Diet",       "description": "Avoid spicy, fatty, and caffeinated foods"},
            {"type": "Lifestyle",  "description": "Eat smaller meals; elevate head of bed"},
            {"type": "Medication", "description": "OTC antacids or H2 blockers"},
        ],
        "follow_up": "Doctor if symptoms persist despite lifestyle changes.",
    },
    "Appendicitis": {
        "severity": "High", "specialist": "Emergency Surgery", "duration": "Surgical",
        "recommendations": [
            {"type": "Emergency",  "description": "SEEK EMERGENCY CARE IMMEDIATELY"},
            {"type": "Avoid",      "description": "Do NOT take laxatives or antacids"},
            {"type": "Surgery",    "description": "Appendectomy is the standard treatment"},
        ],
        "follow_up": "Do not delay — untreated appendicitis is life-threatening.",
    },
    "Urinary Tract Infection (UTI)": {
        "severity": "Medium", "specialist": "Urologist / General Physician", "duration": "3–7 days",
        "recommendations": [
            {"type": "Medication", "description": "Doctor for antibiotic prescription"},
            {"type": "Fluids",     "description": "Drink plenty of water to flush bacteria"},
            {"type": "Avoid",      "description": "Avoid caffeine and alcohol during treatment"},
        ],
        "follow_up": "Urgent care if fever or back pain develops — may indicate kidney infection.",
    },
    "Kidney Stones": {
        "severity": "High", "specialist": "Urologist", "duration": "Days to weeks",
        "recommendations": [
            {"type": "Fluids",     "description": "Drink 2–3 L water daily to help pass stone"},
            {"type": "Medication", "description": "NSAIDs or prescription pain relief"},
            {"type": "Doctor",     "description": "Lithotripsy or surgery for large stones"},
        ],
        "follow_up": "Seek immediate care if fever develops alongside pain.",
    },
    "Hypertension": {
        "severity": "Medium", "specialist": "Cardiologist / Internal Medicine", "duration": "Chronic — lifelong",
        "recommendations": [
            {"type": "Monitor",    "description": "Check blood pressure daily"},
            {"type": "Diet",       "description": "Low-sodium DASH diet; limit alcohol"},
            {"type": "Medication", "description": "Take antihypertensives as prescribed"},
        ],
        "follow_up": "Regular follow-up every 1–3 months.",
    },
    "Heart Attack (MI)": {
        "severity": "High", "specialist": "Cardiologist / Emergency", "duration": "Emergency",
        "recommendations": [
            {"type": "Emergency",  "description": "CALL 108/112 IMMEDIATELY"},
            {"type": "Aspirin",    "description": "Chew 300 mg aspirin if not allergic"},
            {"type": "Rest",       "description": "Lie down and rest — do NOT drive yourself"},
        ],
        "follow_up": "Time is critical — every minute counts for heart muscle survival.",
    },
    "Stroke": {
        "severity": "High", "specialist": "Neurologist / Emergency", "duration": "Emergency",
        "recommendations": [
            {"type": "Emergency",  "description": "CALL EMERGENCY SERVICES IMMEDIATELY"},
            {"type": "FAST",       "description": "FAST: Face droop, Arm weakness, Speech, Time to call"},
            {"type": "Note",       "description": "Note exact symptom onset time — critical for treatment"},
        ],
        "follow_up": "Do NOT give food or water. Time = brain cells.",
    },
    "Anxiety Disorder": {
        "severity": "Medium", "specialist": "Psychiatrist / Psychologist", "duration": "Ongoing",
        "recommendations": [
            {"type": "Breathing",  "description": "Deep breathing — 4-7-8 technique daily"},
            {"type": "Exercise",   "description": "Regular aerobic exercise 30 min/day"},
            {"type": "Therapy",    "description": "Cognitive Behavioural Therapy (CBT)"},
        ],
        "follow_up": "Medication may be appropriate if symptoms are severe or persistent.",
    },
    "Depression": {
        "severity": "Medium", "specialist": "Psychiatrist / Psychologist", "duration": "Ongoing",
        "recommendations": [
            {"type": "Support",    "description": "Seek professional mental health support"},
            {"type": "Therapy",    "description": "Talk therapy (CBT/IPT) is highly effective"},
            {"type": "Lifestyle",  "description": "Regular exercise and maintain social connections"},
        ],
        "follow_up": "Antidepressants may be prescribed; never stop without doctor guidance.",
    },
    "Panic Attack": {
        "severity": "Medium", "specialist": "Psychiatrist / Psychologist", "duration": "Minutes",
        "recommendations": [
            {"type": "Grounding",  "description": "5-4-3-2-1 senses grounding technique"},
            {"type": "Breathing",  "description": "Slow diaphragmatic breathing during attack"},
            {"type": "Therapy",    "description": "CBT to prevent and manage recurrence"},
        ],
        "follow_up": "Avoid caffeine; see a doctor if attacks are frequent.",
    },
    "Anemia": {
        "severity": "Medium", "specialist": "Haematologist / General Physician", "duration": "Weeks–months",
        "recommendations": [
            {"type": "Test",       "description": "Blood test to identify anemia type"},
            {"type": "Diet",       "description": "Iron-rich foods: red meat, spinach, lentils"},
            {"type": "Supplement", "description": "Iron supplements with Vitamin C for absorption"},
        ],
        "follow_up": "Treat the underlying cause alongside supplementation.",
    },
    "Hypothyroidism": {
        "severity": "Medium", "specialist": "Endocrinologist", "duration": "Lifelong",
        "recommendations": [
            {"type": "Test",       "description": "TSH blood test for diagnosis"},
            {"type": "Medication", "description": "Daily levothyroxine on empty stomach"},
            {"type": "Monitor",    "description": "Thyroid function check every 6–12 months"},
        ],
        "follow_up": "Do not skip doses; dosage may need adjustment over time.",
    },
    "Hyperthyroidism": {
        "severity": "Medium", "specialist": "Endocrinologist", "duration": "Months–years",
        "recommendations": [
            {"type": "Referral",   "description": "Endocrinologist referral essential"},
            {"type": "Medication", "description": "Antithyroid medications; beta-blockers for heart rate"},
            {"type": "Therapy",    "description": "Radioactive iodine therapy if medications fail"},
        ],
        "follow_up": "Monitor regularly for cardiac complications.",
    },
    "Type 2 Diabetes": {
        "severity": "Medium", "specialist": "Endocrinologist / Diabetologist", "duration": "Chronic — lifelong",
        "recommendations": [
            {"type": "Test",       "description": "Measure fasting blood glucose and HbA1c"},
            {"type": "Diet",       "description": "Low-GI diet; lose 5–10% body weight if overweight"},
            {"type": "Medication", "description": "Metformin is first-line medication"},
        ],
        "follow_up": "150+ min of exercise per week; regular foot and eye checks.",
    },
    "Dehydration": {
        "severity": "Low", "specialist": "General Physician", "duration": "Hours–1 day",
        "recommendations": [
            {"type": "Hydration",  "description": "Drink water or ORS immediately"},
            {"type": "Electrolyte","description": "Sports drinks for electrolyte replacement"},
            {"type": "Avoid",      "description": "Avoid caffeine and alcohol"},
        ],
        "follow_up": "IV fluids required if unable to keep liquids down.",
    },
    "Meningitis": {
        "severity": "High", "specialist": "Neurologist / Emergency", "duration": "Emergency",
        "recommendations": [
            {"type": "Emergency",  "description": "MEDICAL EMERGENCY — call 108/112 immediately"},
            {"type": "Watch",      "description": "Non-blanching rash = meningococcal emergency"},
            {"type": "Treatment",  "description": "IV antibiotics must start without delay"},
        ],
        "follow_up": "Every minute of delay increases risk of permanent damage.",
    },
    "Food Poisoning": {
        "severity": "Medium", "specialist": "General Physician", "duration": "1–3 days",
        "recommendations": [
            {"type": "Hydration",  "description": "ORS to maintain hydration"},
            {"type": "Diet",       "description": "BRAT diet when able to eat"},
            {"type": "Monitor",    "description": "Seek care if symptoms last > 48 h or high fever"},
        ],
        "follow_up": "Hospitalisation if severe dehydration or blood in stool.",
    },
    "Eczema": {
        "severity": "Low", "specialist": "Dermatologist", "duration": "Chronic — ongoing",
        "recommendations": [
            {"type": "Moisturise", "description": "Frequent fragrance-free emollient application"},
            {"type": "Avoid",      "description": "Identify and avoid personal triggers"},
            {"type": "Medication", "description": "Topical corticosteroids for flares"},
        ],
        "follow_up": "Antihistamines at night for itch relief during flares.",
    },
    "Gout": {
        "severity": "Medium", "specialist": "Rheumatologist", "duration": "Days per attack",
        "recommendations": [
            {"type": "Medication", "description": "NSAIDs or colchicine for acute attack"},
            {"type": "Ice",        "description": "Ice pack on affected joint"},
            {"type": "Diet",       "description": "Avoid alcohol and high-purine foods (red meat, shellfish)"},
        ],
        "follow_up": "Allopurinol for long-term uric acid control.",
    },
    "Lower Back Pain": {
        "severity": "Low", "specialist": "Physiotherapist / Orthopaedic", "duration": "Days–weeks",
        "recommendations": [
            {"type": "Activity",   "description": "Stay active — bed rest worsens recovery"},
            {"type": "Heat/Ice",   "description": "Heat or ice packs for pain relief"},
            {"type": "Medication", "description": "OTC NSAIDs or paracetamol"},
        ],
        "follow_up": "Core-strengthening physiotherapy for long-term prevention.",
    },
    "Conjunctivitis (Pink Eye)": {
        "severity": "Low", "specialist": "Ophthalmologist / General Physician", "duration": "5–7 days",
        "recommendations": [
            {"type": "Compress",   "description": "Warm compress for crusty discharge"},
            {"type": "Medication", "description": "Antibiotic drops for bacterial conjunctivitis"},
            {"type": "Hygiene",    "description": "Wash hands frequently; avoid touching eyes"},
        ],
        "follow_up": "Avoid contact lenses until fully resolved.",
    },
}

# Helpers

def _lookup(condition: str):
    """Exact match first, then case-insensitive partial match."""
    plan = TREATMENTS.get(condition)
    if plan:
        return condition, plan
    low = condition.lower()
    for key, val in TREATMENTS.items():
        if low in key.lower() or key.lower() in low:
            return key, val
    return None, None


def _build_plan(condition: str, plan: dict, medibot_data: dict | None = None) -> dict:
    """Merge treatment plan with any extra context from medibot results."""
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
        "risk":            medibot_data.get("risk")          if medibot_data else None,
        "urgency":         medibot_data.get("urgency")       if medibot_data else None,
        "severitySignal":  medibot_data.get("severitySignal") if medibot_data else None,
        "disclaimer":      medibot_data.get("disclaimer")    if medibot_data else
                           "This is not a substitute for professional medical advice.",
    }

# Routes

@app.route("/api/treatment", methods=["POST"])
def treatment_from_medibot():
    """
    PRIMARY ENDPOINT — called right after medibot_api returns phase=results.

    Body: the exact `results` object from medibot_api._build_results()
    {
        "primaryCondition": "Common Cold",
        "conditions": [...],   // top-5 from ML
        "urgency": "Low",
        "risk": 72,
        "severitySignal": "Mild",
        "recommendations": [...],   // medibot's generic recs (ignored here)
        "disclaimer": "..."
    }

    Returns treatment plans for primaryCondition + up to 2 runner-up conditions.
    """
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
    """
    FALLBACK / SIMPLE ENDPOINT
    GET /api/treatment?condition=Common Cold
    """
    condition = request.args.get("condition", "").strip()
    if not condition:
        return jsonify({"error": "condition query param is required"}), 400

    matched_name, plan = _lookup(condition)
    if not plan:
        return jsonify({"error": f"No treatment plan found for '{condition}'"}), 404

    return jsonify(_build_plan(matched_name, plan)), 200


@app.route("/api/conditions", methods=["GET"])
def list_conditions():
    """GET /api/conditions — all 32 supported condition names."""
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
            "GET  /api/conditions": "List all 32 supported conditions",
            "GET  /api/health":    "Health check",
        }
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("TREATMENT_PORT", 5001))
    print(f"\n  [Treatment API] Running on port {port}")
    print(f"  [Treatment API] {len(TREATMENTS)} conditions loaded\n")
    app.run(host="0.0.0.0", port=port, debug=False)