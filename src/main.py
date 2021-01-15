import tempfile
import pytube
from pytube.extract import video_id
from quart import Quart, render_template
from googleapiclient.discovery import build
import json
from pytube import YouTube
import re
from typing import *
import jsonify
import datetime, calendar
import tempfile
import aiohttp
import functools
import requests
import ffmpeg
from moviepy.editor import *
import os


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

data = {}
# bestStream : pytube.Stream = None
# lowestStream : pytube.Stream = None

async def get_yt_obj(video_code):
    url = f'https://www.youtube.com/watch?v={video_code}'
    yt_obj = YouTube(url)
    audio : pytube.Stream = sorted(yt_obj.streams.filter(type="audio", only_audio=True), key=lambda stream: int(stream.bitrate), reverse=True)[0]
    bestStream : pytube.Stream = sorted(yt_obj.streams.filter(type="video", only_video=True), key=lambda stream: int(stream.resolution.replace("p", "")), reverse=True)[0]
    lowestStream : pytube.Stream = sorted(yt_obj.streams.filter(type="video", only_video=True), key=lambda stream: int(stream.resolution.replace("p", "")), reverse=False)[0]
    return (bestStream, lowestStream, yt_obj, audio)

async def get_data(video_code : str):
    """
    Returns data of the video (thumbnail, duration, options available, etc.).
    Returns None if the video could not be found.
    Returns None if the video is longer than 15 minutes.
    """
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
        bestStream, lowestStream, yt_obj, audio = await get_yt_obj(video_code)
        # audio = sorted(yt_obj.streams.filter(type="audio"), key=lambda stream: int(stream.bitrate))[0]
        data["code"] = video_code
        data["thumbnail"] = results["items"][0]["snippet"]["thumbnails"]["maxres"]["url"]
        data["title"] = results["items"][0]["snippet"]["title"]
        data["duration"] = time
        data["highest"] = bestStream.resolution + str(bestStream.fps)
        data["lowest"] = lowestStream.resolution + str(lowestStream.fps)
        return data

async def get_link(path):
    files = {
        'file' : ('your video.mp4', open(path, 'rb'))
    }
    response = requests.post('https://file.io/?expires=2d', files=files)
    return response

@app.route("/download", defaults={'quality' : 'best', 'code' : ''})
@app.route("/download/<code>/<quality>")
async def download(code, quality):
    bestStream, lowestStream, yt_obj, audio = await get_yt_obj(code)
    with tempfile.TemporaryFile() as file:
        if quality == 'best':
            bVidPath = bestStream.download(filename=code + "-video")
            audioPath = audio.download(filename=code + "-audio")
            audioclip = AudioFileClip(audioPath)
            videoclip = VideoFileClip(bVidPath)
            audioclip2 = CompositeAudioClip([audioclip])
            videoclip.audio = audioclip2
            videoclip.write_videofile("your video.mp4")
            # audioclip = ffmpeg.input(audioPath)
            # videoclip = ffmpeg.input(bVidPath)
            # ffmpeg.concat(videoclip, audioclip, v=1, a=1).output('your video.mp4').run()
            link = await get_link(os.getcwd() + '/your video.mp4')
            file.seek(0)
            return link
        elif quality == 'lowest':
            bVidPath = lowestStream.download(filename=f"{code}-lowest.mp4")
            link = await get_link(bVidPath)
            file.seek(0)
            return link
        else:
            file.seek(0)
            return None
 
@app.route('/')
async def index():
    return await render_template('index.html', getReadableTimeBetween=getReadableTimeBetween)

@app.route('/convert/<code>')
async def convert(code):
    return await get_data(code)

app.run()