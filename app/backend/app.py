import os
import logging
from flask import Flask, request, jsonify
from azure.identity import DefaultAzureCredential
from approaches.chatreadretrieveread import ChatReadRetrieveReadApproach
from dotenv import load_dotenv
from subprocess import check_output
import requests
import json

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path, verbose=True, override=True)

# Replace these with your own values, either in environment variables or directly here
AZURE_OPENAI_SERVICE = os.environ.get("AZURE_OPENAI_SERVICE") or "myopenai"
AZURE_OPENAI_GPT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_GPT_DEPLOYMENT") or "davinci"
AZURE_OPENAI_CHATGPT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHATGPT_DEPLOYMENT") or "chat"

chat_approaches = {
    "rrr": ChatReadRetrieveReadApproach(AZURE_OPENAI_CHATGPT_DEPLOYMENT, AZURE_OPENAI_GPT_DEPLOYMENT)
}

app = Flask(__name__)

@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def static_file(path):
    print(path)
    return app.send_static_file(path)

@app.route("/chat", methods=["POST"])
def chat():

    # ensure_openai_token()
    approach = request.json["approach"]
    try:
        impl = chat_approaches.get(approach)
        if not impl:
            return jsonify({"error": "unknown approach"}), 400
        defaultHeaders = {}
        if (request.json["tracing"]["enabled"]):
            accessTokenResult = check_output(["az", "account", "get-access-token"]).decode().strip()
            accessTokenJson = json.loads(accessTokenResult)
            url = "https://management.azure.com/" + os.getenv("APIM_GW_RESOURCE_ID") + "/listDebugCredentials?api-version=2023-05-01-preview"
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + accessTokenJson["accessToken"]
            }
            body = {
                "credentialsExpireAfter": "PT1H",
                "apiId": os.getenv("APIM_API_RESOURCE_ID"),
                "purposes": ["tracing"]
            }
            response = requests.post(url, headers=headers, json=body)
            defaultHeaders = { "Apim-Debug-Authorization": response.json()["token"] }
        r = impl.run(request.json["history"], request.json.get("overrides") or {}, request.json.get("sessionConfig") or {}, request.json.get("userInfo") or {}, dict(request.headers) or {}, defaultHeaders)
        trace = ""
        if (request.json["tracing"]["enabled"]):
            traceid = r["headers"]["apim-trace-id"]
            url = "https://management.azure.com/" + os.getenv("APIM_GW_RESOURCE_ID") + "/listTrace?api-version=2023-05-01-preview"
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + accessTokenJson["accessToken"]
            }
            body = {
                "traceId": traceid            }
            traceResponse = requests.post(url, headers=headers, json=body)
            trace = traceResponse.json()
        return jsonify({"answer": r["answer"], "trace": trace })

    except Exception as e:
        logging.exception("Exception in /chat")
        return jsonify({"error": str(e)}), 500

@app.route("/tracingAuth", methods=["GET"])
def tracingAuth():

    accessTokenResult = check_output(["az", "account", "get-access-token"]).decode().strip()
    accessTokenJson = json.loads(accessTokenResult)
    url = "https://management.azure.com/" + os.getenv("APIM_GW_RESOURCE_ID") + "/listDebugCredentials?api-version=2023-05-01-preview"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + accessTokenJson["accessToken"]
    }
    body = {
        "credentialsExpireAfter": "PT1H",
        "apiId": os.getenv("APIM_API_RESOURCE_ID"),
        "purposes": ["tracing"]
    }
    response = requests.post(url, headers=headers, json=body)
    return response.json(), response.status_code 

if __name__ == "__main__":
    app.run()
