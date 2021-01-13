from quart import Quart, render_template
from googleapiclient.discovery import build
import json
from pytube import YouTube
import re
from typing import *
import jsonify

config_read = open('./config.json', 'r')
config = json.load(config_read)
API_KEY = config["API_KEY"]
client = build('youtube', 'v3', developerKey=API_KEY)
app = Quart(__name__)



def get_seconds(timeString: str) -> Optional[int]:
    time_regex = re.compile("(?:(\d{1,5})(h|s|m|d))+?")
    time_dict = {"h":3600, "s":1, "m":60, "d":86400}
    matches = re.findall(time_regex, timeString.lower())
    time = 0
    for v, k in matches:
        try:
            time += time_dict[k]*float(v)
        except KeyError:
            return None
        except ValueError:
            return None
    return time

async def download_video(video_code : str):
    """
    Returns the downloaded video's link.
    Returns None if the video could not be found.
    Returns None if the video is longer than 15 minutes.
    """
    data = {}
    results = client.videos().list(
        part="id,snippet,contentDetails",
        id=video_code
    ).execute()
    # print(results)
    if not results["items"] and results["pageInfo"]["totalResults"] == 0:
        return {"status":"error", "message":"No valid videos found."}
    timeString = results["items"][0]["contentDetails"]["duration"].replace("PT", "")
    time = get_seconds(timeString=timeString)
    if not time: 
        return {"status":"error", "message":"Unknown error."}
    elif time > 15*60:
        return {"status":"error", "message":"Video duration more than 15 minutes."}
    else:
        url = f'https://www.youtube.com/watch?v={video_code}'
        yt_obj = YouTube(url)
        best = sorted(yt_obj.streams.filter(type="video"), key=lambda stream: int(stream.resolution.replace("p", "")), reverse=True)[0]
        lowest = sorted(yt_obj.streams.filter(type="video"), key=lambda stream: int(stream.resolution.replace("p", "")), reverse=False)[0]
        audio = sorted(yt_obj.streams.filter(type="audio"), key=lambda stream: int(stream.bitrate))[0]
        data["thumbnail"] = results["items"][0]["snippet"]["thumbnails"]["standard"]["url"]
        data["title"] = results["items"][0]["snippet"]["title"]
        data["duration"] = time
        data["options"] = {"highest": {"res":best.resolution,"fps":best.fps},
                           "lowest": {"res":lowest.resolution,"fps":lowest.fps},
                           "audio": {"bitrate": audio.bitrate}}
        return data
 
@app.route('/')
async def index():
    return await render_template('index.html', download_video=download_video)

@app.route('/convert/<code>')
async def convert(code):
    return await download_video(code)

app.run()