#!/Users/claratu/Desktop/dt/dt_slack_bots/diversabot/diversavenv/bin/python3.10

import os
import random
import re
from typing import Optional
from dotenv import load_dotenv  # type: ignore
import logging
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
import pymysql
from sqlalchemy import create_engine, text
import requests
from urllib.parse import urlparse
import io
from PIL import Image
import boto3
from botocore.exceptions import ClientError
import time

load_dotenv('.env')

# Initializes your app with your bot token and signing secret
app = App(
    token=os.environ.get('SLACK_BOT_TOKEN'),
    signing_secret=os.environ.get('SLACK_SIGNING_SECRET')
)

# Initializes MySQL Database
user = os.environ.get('SQLUSER')
pw = os.environ.get('PW')
db = os.environ.get('DB')

engine = create_engine(
    "mysql+pymysql://{user}:{pw}@localhost:3306/{db}"
                           .format(user=user, pw=pw, db=db),
)
conn = engine.connect()

# Initialize S3 Bucket
s3 = boto3.client('s3',
    aws_access_key_id=os.environ.get('ACCESS_KEY'),
    aws_secret_access_key=os.environ.get('SECRET_KEY'))

# Testing
@app.message("ping")
def message_pong(message, client):
    channel_id = message['channel']
    print(message)
    msg = "pong"
    client.chat_postMessage(channel=channel_id, text=msg)

# Helper Functions

def find_all_mentions(msg: str) -> list:
    '''Returns all user_ids mentioned in msg'''
    member_ids = re.findall(r'<@([\w]+)>', msg, re.MULTILINE)
    return member_ids


def random_excited_greeting() -> str:
    '''Returns a random greeting'''
    greetings = [
        "Hey",
        "Hi",
        "What's schlaying",
        "What's poppin'",
        "Greetings",
        "DiversaHi",
        "Attention",
        "DiversaSLAY",
        "Howdy"
    ]
    return random.choice(greetings)


def random_disappointed_greeting() -> str:
    '''Returns a random greeting'''
    greetings = [
        "Oh no",
        "Whoops",
        "Stupid",
        "WRONGFUL SPOT",
    ]
    return random.choice(greetings)

def count_spots(name: str) -> int:
    '''Returns the number of spots a user has'''
    result = conn.execute(
        text(
            " SELECT COUNT(Name) FROM diversaspots \
            WHERE Name = '{name}' "
            .format(name=name)
        )
    ).fetchone()
    for line in result:
        result =  int(line)
        break
    return int(result)

def get_image_url(message) -> str:
    image_url = message['files'][0]['url_private']

    path = urlparse(image_url).path
    file_path = os.path.splitext(path)[0].split("/")[-1]
    ext = os.path.splitext(path)[1]
    # TODO: rename file_path
    file_name = file_path + ext

    # Put image object into S3 Bucket
    resp = requests.get(image_url, headers={'Authorization': 'Bearer %s' % os.environ.get('SLACK_BOT_TOKEN')})
    s3.put_object(Bucket='diversaspots', Body=resp.content, Key=file_name)

    return "https://diversaspots.s3.us-west-1.amazonaws.com/" + file_name

# Spot and Snipe Actions
@app.message("spot")
def record_spot(message, client):
    user = message["user"]
    message_ts = message["ts"]
    image = get_image_url(message)
    flagged = False
    channel_id = message["channel"]
    tagged = find_all_mentions(message["text"])

    if len(tagged) == 0:
        reply = f"{random_disappointed_greeting()} <@{user}>, this DiversaSpot doesn't count because you didn't mention anyone! Delete and try again."
    else:
        response = app.client.users_info(user=user)
        name = response["user"]["real_name"]
        conn.execute(
            text(
                " INSERT INTO diversaspots \
                VALUES ('{name}', '{user}', '{tagged[0]}', '{image}', '{message_ts}', {flagged}); "
                .format(name=name, user=user, tagged=tagged, image=image, message_ts=message_ts, flagged=flagged)
            )
        )
        # conn.commit()
        result = conn.execute(
            text(
                " SELECT * FROM diversaspots "
            )
        )
        for line in result:
            print(line)
        numSpots = count_spots(name)
        reply = f"{random_excited_greeting()} <@{user}>, you now have {numSpots} DiversaSpots!"

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        text=reply
    )


@app.message("Snipe")
def record_snipe(message, client):
    user = message["user"]
    message_ts = message["ts"]
    channel_id = message["channel"]
    tagged = find_all_mentions(message["text"])

    if len(tagged) == 0:
        reply = f"{random_disappointed_greeting()} <@{user}>, this DiversaSpot doesn't count because you didn't mention anyone! Delete and try again."
    else:
        reply = f"{random_excited_greeting()} <@{user}>, you just DiversaSniped! You now have ___ DiversaSpots!"

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        text=reply
    )

# diversabot actions (in order of importance)
# TODO: diversabot leaderboard
@app.message("diversabot leaderboard")
def post_leaderboard(message, client):
    user = message["user"]
    message_ts = message["ts"]
    channel_id = message["channel"]
    tagged = find_all_mentions(message["text"])

    if len(tagged) == 0:
        reply = f"{random_disappointed_greeting()} <@{user}>, this DiversaSpot doesn't count because you didn't mention anyone! Delete and try again."
    else:
        reply = f"{random_excited_greeting()} <@{user}>, you just DiversaSniped! You now have ___ DiversaSpots!"

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        text=reply
    )
# TODO: diversabot stats
# TODO: diversabot flag
# TODO: diversabot team leaderboard
# TODO: diversabot miss
# TODO: diversabot help (can copy and paste technically)
# TODO: diversabot recap (automatic and not an action) — recap with who spotted the most that week, who was the most spotted, and like 3-5 pics of most reacted to spots (need to implement a count reacts)
# TODO: diversabot chum - for the chumming channel to count into diversaspots?

@app.message("diversabot rules")
def post_rules(message, client):
    ''' Returns the rules of a successful how diversaspotting challenges work '''
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "DiversaSpot Official Rules & Regulations"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "It is everyone’s responsability to hold everyone accountable for following the rules! If you see a post that violates any of the following rules and regulations, you should reply ‘diversabot flag’ in the thread. Please use this command in good faith!"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Rule 1:* The person being spotted must be identifiable. Some ambiguity is allowed (i.e their back is turned but we can tell it’s them, half their face is showing, etc), but total ambiguity is not (i.e the image is completely blurry, they’re too small to discern, their back is turned but they could literally be any asian dude with a black hoodie, etc)."
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Rule 2:* Spotting multiple DT members in the same group or vicinity counts a 1 spot. Specifically, you cannot get multiple points from spotting the same group."
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Rule 3:* You cannot get multiple points for spotting individuals or groups at the same function. For example, you cannot spot a project team meeting at Moffitt and then spot them again an hour later. As another example, if you’re hanging out with DT member(s), you cannot spot them more than once just because you moved locations. In cognition that this rule is subjective and ambiguous, it is recommended to post a spot anyways if you’re unsure whether it violates this rule."
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Rule 4:* In the case of a spotting duel where two (or more) people are attempting to spot one another, the winner is the first person to successfully post their spot in the slack channel, and everyone else’s spots do not count."
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Rule 5:* The project team with the most combined DiversaSpot will be rewarded with ... TBD"
            }
        }
    ]
    channel_id = message["channel"]
    client.chat_postMessage(
        channel=channel_id,
        blocks=blocks
    )

# Start your app
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
