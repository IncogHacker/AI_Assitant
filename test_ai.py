import requests

# URL of your running Flask server
url = "http://127.0.0.1:5000/receive_call"

print("🤖 AI Receptionist ready! Type your question below.")
print("Type 'exit' anytime to stop.\n")

while True:
    question = input("Ask AI something: ").strip()
    if question.lower() == "exit":
        print("👋 Goodbye!")
        break

    try:
        response = requests.post(url, json={"question": question})
        if response.status_code == 200:
            data = response.json()
            print("AI:", data["response"])
        else:
            print("⚠️ Error:", response.status_code)
    except Exception as e:
        print("❌ Could not reach AI server:", e)
