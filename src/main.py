from quart import Quart, render_template
from googleapiclient.discovery import build
import json
from pytube import YouTube
import re
from typing import *
import jsonify
import datetime, calendar

config_read = open('./config.json', 'r')
config = json.load(config_read)
API_KEY = config["API_KEY"]
client = build('youtube', 'v3', developerKey=API_KEY)
app = Quart(__name__)

def get_years(timeBetween, year, reverse):
    years = 0

    while True:
        if reverse:
            year -= 1
        else:
            year += 1

        year_days = 366 if calendar.isleap(year) else 365 
        year_seconds = year_days * 86400

        if timeBetween < year_seconds:
            break

        years += 1
        timeBetween -= year_seconds

    return timeBetween, years, year
def get_months(timeBetween, year, month, reverse):
    months = 0

    while True:
        month_days = calendar.monthrange(year, month)[1]
        month_seconds = month_days * 86400

        if timeBetween < month_seconds:
            break

        months += 1
        timeBetween -= month_seconds

        if reverse:
            if month > 1:
                month -= 1
            else:
                month = 12
                year -= 1
        else:
            if month < 12:
                month += 1
            else:
                month = 1
                year += 1

    return timeBetween, months

def getReadableTimeBetween(first, last, reverse=False):
    timeBetween = int(last-first)
    now = datetime.datetime.now()
    year = now.year
    month = now.month

    timeBetween, years, year = get_years(timeBetween, year, reverse)
    timeBetween, months = get_months(timeBetween, year, month, reverse)
    
    weeks   = int(timeBetween/604800)
    days    = int((timeBetween-(weeks*604800))/86400)
    hours   = int((timeBetween-(days*86400 + weeks*604800))/3600)
    minutes = int((timeBetween-(hours*3600 + days*86400 + weeks*604800))/60)
    seconds = int(timeBetween-(minutes*60 + hours*3600 + days*86400 + weeks*604800))
    msg = ""
    
    if years > 0:
        msg += "1 year, " if years == 1 else "{:,} years, ".format(years)
    if months > 0:
        msg += "1 month, " if months == 1 else "{:,} months, ".format(months)
    if weeks > 0:
        msg += "1 week, " if weeks == 1 else "{:,} weeks, ".format(weeks)
    if days > 0:
        msg += "1 day, " if days == 1 else "{:,} days, ".format(days)
    if hours > 0:
        msg += "1 hour, " if hours == 1 else "{:,} hours, ".format(hours)
    if minutes > 0:
        msg += "1 minute, " if minutes == 1 else "{:,} minutes, ".format(minutes)
    if seconds > 0:
        msg += "1 second, " if seconds == 1 else "{:,} seconds, ".format(seconds)

    if msg == "":
        return "0 seconds"
    else:
        return msg[:-2]	

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
    # elif time > 15*60:
    #     return {"status":"error", "message":"Video duration more than 15 minutes."}
    else:
        url = f'https://www.youtube.com/watch?v={video_code}'
        yt_obj = YouTube(url)
        best = sorted(yt_obj.streams.filter(type="video"), key=lambda stream: int(stream.resolution.replace("p", "")), reverse=True)[0]
        lowest = sorted(yt_obj.streams.filter(type="video"), key=lambda stream: int(stream.resolution.replace("p", "")), reverse=False)[0]
        audio = sorted(yt_obj.streams.filter(type="audio"), key=lambda stream: int(stream.bitrate))[0]
        data["thumbnail"] = results["items"][0]["snippet"]["thumbnails"]["maxres"]["url"]
        data["title"] = results["items"][0]["snippet"]["title"]
        data["duration"] = time
        data["highest"] = best.resolution + str(best.fps)
        data["lowest"] = lowest.resolution + str(lowest.fps)
        return data
 
@app.route('/')
async def index():
    return await render_template('index.html', getReadableTimeBetween=getReadableTimeBetween)

@app.route('/convert/<code>')
async def convert(code):
    return await download_video(code)

app.run()