from quart import Quart, render_template
from googleapiclient.discovery import build
import json

config_read = open('./config.json', 'r')
config = json.load(config_read)
API_KEY = config["API_KEY"]
client = build('youtube', 'v3', developerKey=API_KEY)
app = Quart(__name__)

@app.route('/')
async def hello():
    return await render_template('index.html')

@app.route('/faq')
async def faq():
    return "not done yet."

app.run()