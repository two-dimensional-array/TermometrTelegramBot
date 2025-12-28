from os import makedirs, getenv
from flask import Flask, request
from termometr import Termometr, TermometerHandler
from bot import TermometerBot

app = Flask(__name__)

TERMOMETR_RECORDS_DIRECTORY = "./termometr_records"
makedirs(TERMOMETR_RECORDS_DIRECTORY, exist_ok=True)

termometers = TermometerHandler(TERMOMETR_RECORDS_DIRECTORY)
bot = TermometerBot(termometers, getenv("TELEGRAM_BOT_TOKEN"), getenv("http_proxy"))

termometers.load_all_termometrs()

@app.route('/termometer', methods=['POST'])
def process_termometer_data():
    try:
        info = request.get_json()

        if termometers.find_termometr_by_id(info["id"]) is None:
            termometers.add_termometr(Termometr(info["id"], info["name"]))
        else:
            termometers.update_termometr(info["id"], info["temperature"], info["humidity"], info["name"])

        return "Data received", 200
    except Exception as e:
        return f"Error: {e}", 400

@app.route('/', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        update_dict = request.get_json()

        bot.webhook_handler(update_dict)

        return "OK", 200
    return "Forbidden", 403

@app.route('/setup')
def setup_webhook():
    webhook_url = f"{getenv('USER').lower()}.pythonanywhere.com"
    success = bot.set_webhook(webhook_url)

    return f"Webhook set to {webhook_url}: {success}"
