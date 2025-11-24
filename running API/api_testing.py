from flask import Flask, jsonify, request
import time

app = Flask(__name__)

# Initial variables
START_TIME = None
API_RUNNING = False
SELECTED_STATUS = 200


@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>API Control Panel</title>
        <style>
            body {
                font-family: "Segoe UI", sans-serif;
                background: #fff7f0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
            }
            h1 { color: #333; }
            .card {
                background: white;
                padding: 25px 40px;
                border-radius: 16px;
                box-shadow: 0 3px 10px rgba(0,0,0,0.15);
                text-align: center;
            }
            button {
                background: #ff7b00;
                border: none;
                color: white;
                padding: 10px 25px;
                margin: 10px;
                border-radius: 10px;
                cursor: pointer;
                font-size: 17px;
                transition: 0.3s;
            }
            button:hover {
                background: #e26f00;
            }
            select {
                padding: 8px;
                border-radius: 8px;
                font-size: 15px;
                margin-top: 10px;
            }
            .status {
                margin-top: 15px;
                font-size: 18px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>API Control Panel</h1>
            <button id="toggleBtn">Start API</button>
            <br>
            <label for="statusCode">Select Status Code:</label>
            <select id="statusCode">
                <option value="200">200 OK</option>
                <option value="400">400 Bad Request</option>
                <option value="404">404 Not Found</option>
                <option value="500">500 Server Error</option>
            </select>
            <div class="status" id="apiStatus">API is Stopped</div>
        </div>

        <script>
            const toggleBtn = document.getElementById("toggleBtn");
            const apiStatus = document.getElementById("apiStatus");
            const statusCode = document.getElementById("statusCode");

            toggleBtn.addEventListener("click", async () => {
                const res = await fetch("/toggle", { method: "POST" });
                const data = await res.json();
                if (data.running) {
                    toggleBtn.textContent = "Stop API";
                    apiStatus.textContent = "API is Running";
                    apiStatus.style.color = "green";
                } else {
                    toggleBtn.textContent = "Start API";
                    apiStatus.textContent = "API is Stopped";
                    apiStatus.style.color = "red";
                }
            });

            statusCode.addEventListener("change", async () => {
                const selected = statusCode.value;
                await fetch("/set_status", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ status: selected })
                });
            });
        </script>
    </body>
    </html>
    """


@app.route("/toggle", methods=["POST"])
def toggle_api():
    global API_RUNNING, START_TIME
    API_RUNNING = not API_RUNNING
    if API_RUNNING:
        START_TIME = time.time()
    return jsonify({"running": API_RUNNING})


@app.route("/set_status", methods=["POST"])
def set_status():
    global SELECTED_STATUS
    data = request.get_json()
    SELECTED_STATUS = int(data.get("status", 200))
    return jsonify({"status": SELECTED_STATUS})


@app.route("/health")
def health():
    if not API_RUNNING:
        return jsonify({
            "status": "down",
            "code": 503,
            "message": "API is stopped"
        }), 503

    elapsed = int(time.time() - START_TIME)
    response = {
        "status": "up",
        "code": SELECTED_STATUS,
        "uptime_seconds": elapsed
    }
    return jsonify(response), SELECTED_STATUS


if __name__ == "__main__":
    app.run(port=7000, debug=True)
