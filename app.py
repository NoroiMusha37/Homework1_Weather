from dotenv import load_dotenv
from groq import Groq
import os
import datetime as dt
import json
import re

import requests
from flask import Flask, jsonify, request
load_dotenv()
WEATHER_API = os.getenv('WEATHER_API')
TOKEN = os.getenv('TOKEN')
LLM = os.getenv('LLM')
app = Flask(__name__)


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


def get_weather(location, date):
    url_base_url = ("https://weather.visualcrossing.com/VisualCrossingWebServices"
                    f"/rest/services/timeline/{location}/{date}?key={WEATHER_API}"
                    f"&unitGroup=metric&include=days&elements=tempmax,tempmin,temp,cloudcover,"
                    "humidity,pressure,sunrise,sunset,visibility,windspeed")

    response = requests.get(url_base_url)

    if response.status_code == requests.codes.ok:
        weather = json.loads(response.text)
        return weather["days"][0]
    else:
        raise InvalidUsage(response.text, status_code=response.status_code)

def get_advice(weather):
    client = Groq(api_key=LLM)
    question = (f"{weather} Based on weather data, advise on the best clothing for this day."
                "Answer should be 4 sentences long")
    completion = client.chat.completions.create(
        model="deepseek-r1-distill-llama-70b",
        messages=[
            {
                "role": "user",
                "content": question
            }
        ],
        temperature=0.8
        )

    response = completion.choices[0].message.content
    advice = re.sub(r'<think>\n.*?\n</think>\n\n', '', response, flags=re.DOTALL).strip()

    return advice

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/")
def home_page():
    return "<p><h2>KMA L2: python Saas.</h2></p>"


@app.route("/content/api/v1/generate", methods=["POST"])
def weather_endpoint():
    start_dt = dt.datetime.now()
    json_data = request.get_json()
    json_data["timestamp"] = start_dt.strftime("%Y-%m-%d %H:%M:%S")

    if json_data.get("token") is None:
        raise InvalidUsage("token is required", status_code=400)

    token = json_data.get("token")

    if token != TOKEN:
        raise InvalidUsage("wrong API token", status_code=403)

    json_data.pop("token")
    weather = get_weather(json_data["location"], json_data["date"])
    json_data["weather"] = weather
    json_data["advice"] = get_advice(weather)
    return json_data
