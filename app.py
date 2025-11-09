from flask import Flask, request, jsonify, render_template, redirect
import json, os, random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from livekit import AccessToken, VideoGrant  # ✅ Correct import

load_dotenv()   # Loads .env file with LIVEKIT keys

app = Flask(__name__)

KB_FILE = "AI_Receptionist_memory.json"     # AI memory (known answers)
HR_FILE = "help_requests.json"              # Help requests (unknown answers)

TIMEOUT_MINUTES = 60   # Change to 2–3 min while testing


# ===========================
# Helper functions
# ===========================

def load_knowledge():
    if not os.path.exists(KB_FILE):
        return []
    with open(KB_FILE, "r") as f:
        return json.load(f)

def load_requests():
    if not os.path.exists(HR_FILE):
        return []
    with open(HR_FILE, "r") as f:
        return json.load(f)

def save_requests(data):
    with open(HR_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ✅ Auto timeout logic for supervisor dashboard
def enforce_timeouts(reqs):
    """Mark pending requests as 'unresolved' if too old."""
    changed = False
    for r in reqs:
        if r.get("status") == "pending":
            created = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - created > timedelta(minutes=TIMEOUT_MINUTES):
                r["status"] = "unresolved"
                r["timeout_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                changed = True
    if changed:
        save_requests(reqs)


# ===========================
# ✅ LIVEKIT TOKEN ENDPOINT
# ===========================

@app.route("/get_livekit_token")
def get_livekit_token():
    room = "ai_voice_room"
    identity = f"caller_{random.randint(1000,9999)}"

    token = AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET"),
        identity=identity
    )

    # ✅ Add video grant the old SDK way
    token.video = {
        "roomJoin": True,
        "room": room
    }

    return jsonify({
        "token": token.to_jwt(),
        "url": os.getenv("LIVEKIT_URL"),
        "identity": identity,
        "room": room
    })




# ===========================
# ROUTES
# ===========================

@app.route('/')
def home():
    return redirect("/ask")


# ✅ CUSTOMER PAGE (text + voice)
@app.route("/ask")
def ask_page():
    return render_template("customer.html", title="Ask AI")


# ✅ SUPERVISOR PAGE
@app.route("/supervisor")
def supervisor_page():
    requests = load_requests()
    enforce_timeouts(requests)

    pending    = [r for r in requests if r.get("status") == "pending"]
    resolved   = [r for r in requests if r.get("status") == "resolved"]
    unresolved = [r for r in requests if r.get("status") == "unresolved"]

    return render_template(
        "supervisor.html",
        title="Supervisor Dashboard",
        pending=pending,
        resolved=resolved,
        unresolved=unresolved
    )


# ✅ SUPERVISOR SUBMITS AN ANSWER
@app.route("/supervisor/answer", methods=['POST'])
def supervisor_answer():
    req_id = int(request.form.get("id"))
    answer = request.form.get("answer", "").strip()

    if not answer:
        return "Answer cannot be empty", 400

    help_reqs = load_requests()
    current = None
    for req in help_reqs:
        if req["id"] == req_id:
            current = req
            break

    if not current:
        return "Request not found", 404

    # ✅ Mark as resolved
    current["status"] = "resolved"
    current["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current["answer"] = answer
    save_requests(help_reqs)

    # ✅ Add to knowledge base
    kb = load_knowledge()
    kb.append({
        "question": current["question"],
        "answer": answer,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    with open(KB_FILE, "w") as f:
        json.dump(kb, f, indent=4)

    print(f"✅ Supervisor answered request #{req_id}: {current['question']} -> {answer}")
    print(f"🤖 AI will now answer automatically next time.")

    return redirect("/supervisor")


# ✅ AI receives customer question (text OR speech)
@app.route('/receive_call', methods=['POST'])
def receive_call():
    data = request.get_json()
    question = data.get("question", "").strip().lower()

    # Check knowledge base
    kb = load_knowledge()
    for item in kb:
        if item["question"].lower() == question:
            return jsonify({"response": item["answer"]})

    # Unknown → save to pending
    help_reqs = load_requests()
    new_id = (help_reqs[-1]["id"] + 1) if help_reqs else 1

    new_req = {
        "id": new_id,
        "question": question,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    help_reqs.append(new_req)
    save_requests(help_reqs)

    print(f"📞 New help request #{new_id}: {question}")
    print("📩 Supervisor will see this.")

    return jsonify({
        "response": "Let me check with my supervisor and get back to you."
    })


# ===========================
# ✅ RUN SERVER
# ===========================

if __name__ == '__main__':
    app.run(debug=True)
