#!/Users/claratu/Desktop/dt/dt_slack_bots/diversabot/diversavenv/bin/python3.10

from datetime import date
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
import boto3
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
''' 
diversaspots
Time
Name
Spotter
Tagged
Image
Flagged
'''

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
    ]
    return random.choice(greetings)


def count_spots(name: str) -> int:
    '''Returns the number of spots a user has'''
    result = conn.execute(
        text(
            " SELECT COUNT(Name) FROM diversaspots \
            WHERE Name = '{name}' \
            AND Flagged != 1; "
            .format(name=name)
        )
    ).fetchone()
    for line in result:
        result = int(line)
        break
    return int(result)


def get_image_url(message) -> str:
    ''' Store Slack image into AWS S3 Bucket and return AWS image URL '''
    image_url = message['files'][0]['url_private']

    path = urlparse(image_url).path
    # file_path = os.path.splitext(path)[0].split("/")[-1]
    ext = os.path.splitext(path)[1]
    file_name = message["ts"] + "_" + message["user"] + ext

    # Put image object into S3 Bucket
    resp = requests.get(image_url, headers={'Authorization': 'Bearer %s' % os.environ.get('SLACK_BOT_TOKEN')})
    s3.put_object(Bucket='diversaspots', Body=resp.content, Key=file_name)

    return "https://diversaspots.s3.us-west-1.amazonaws.com/" + file_name


def spotter_leaderboard():
    ''' 
    Name (the spotter)
    Count (# of spots)
    '''
    result = conn.execute(
        text(
            " CREATE TEMPORARY TABLE leaderboard \
            SELECT Name, COUNT(*) AS Count \
            FROM diversaspots \
            WHERE Flagged != 1 \
            GROUP BY Name \
            ORDER BY Count DESC; "
        )
    )
    return result

# Spot and Snipe Actions
@app.event({
    "type" : "message",
    "subtype" : "file_share"
})
def record_spot(message, client, logger):
    user = message["user"]
    message_ts = message["ts"]
    image = get_image_url(message)
    flagged = False
    channel_id = message["channel"]
    tagged = find_all_mentions(message["text"])

    # TODO: check for duplicates
    timestamp = conn.execute(
            text(
                " SELECT Time FROM diversaspots \
                WHERE Time = {message_ts}; "
                .format(message_ts=message_ts)
            )
        )
    for line in timestamp:
        print(line)
    if timestamp == None:
        print("yas")
    # if message_ts in df_spot_history['TIME'].values:
    #     logger.warn("DUPLICATE: ", message_ts)
    #     return

    if len(tagged) == 0:
        reply = f"{random_disappointed_greeting()} <@{user}>, this DiversaSpot doesn't count because you didn't mention anyone! Delete and try again."
    elif message['files'][0]['filetype'] != 'jpg' and message['files'][0]['filetype'] != 'png' and message['files'][0]['filetype'] != 'heic':
        reply = f"{random_disappointed_greeting()} <@{user}>, This DiversaSpot doesn't count because you didn't attach a JPG, HEIC, or a PNG file! Delete and try again."
    else:
        response = app.client.users_info(user=user)
        name = response["user"]["real_name"]
        conn.execute(
            text(
                " INSERT INTO diversaspots \
                VALUES ('{message_ts}', '{name}', '{user}', '{tagged[0]}', '{image}', {flagged}); "
                .format(message_ts=message_ts, name=name, user=user, tagged=tagged, image=image, flagged=flagged)
            )
        )
        conn.commit()
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

# TODO: Snipe
# @app.message("Snipe")
# def record_snipe(message, client):
#     user = message["user"]
#     message_ts = message["ts"]
#     channel_id = message["channel"]
#     tagged = find_all_mentions(message["text"])

#     if len(tagged) == 0:
#         reply = f"{random_disappointed_greeting()} <@{user}>, this DiversaSpot doesn't count because you didn't mention anyone! Delete and try again."
#     else:
#         reply = f"{random_excited_greeting()} <@{user}>, you just DiversaSniped! You now have ___ DiversaSpots!"

#     client.chat_postMessage(
#         channel=channel_id,
#         thread_ts=message_ts,
#         text=reply
#     )

# diversabot actions (in order of importance)
@app.message("diversabot leaderboard")
def post_leaderboard(message, client):
    leaderboard = spotter_leaderboard()
    message_text = ""
    rank = 1
    for line in leaderboard:
        message_text += f"*#{rank}: {line[0]}* with {line[1]} spots \n"
        rank += 1
        if rank == 11:
            break
    message_ts = message["ts"]
    channel_id = message["channel"]

    blocks = [
		{
			"type": "header",
			"text": {
				"type": "plain_text",
				"text": ":trophy:  DiversaSpot Leaderboard  :trophy:"
			}
		},
		{
			"type": "context",
			"elements": [
				{
					"text": f"*{date.today()}*",
					"type": "mrkdwn"
				}
			]
		},
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": message_text
			}
		},
        {
			"type": "context",
			"elements": [
				{
					"type": "mrkdwn",
					"text": "To see your individual stats, type 'diversabot stats'!"
				}
			]
		}
	]

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        blocks=blocks
    )

@app.message("diversabot stats")
def post_stats(message, client):
    leaderboard = spotter_leaderboard()
    message_text = ""
    user = message["user"]

    spotter = conn.execute(
        text(
            " SELECT Name FROM diversaspots \
            WHERE Spotter = '{user}'; "
            .format(user=user)
        )
    )
    if spotter == None:
        message_text = f"You have not spotted anyone yet :( Go get out there!"
    else:
        result = conn.execute(
            text(
                " SELECT * FROM leaderboard;"
            )
        )
        for line in result:
            print(line)

        # rank = conn.execute(
        #     text(
        #         " SELECT 
        #     )
        # )

        # rank = int(leaderboard[leaderboard['SPOTTER']==user]['RANK'].iloc[0])
        # size = len(leaderboard)
        # for i in range(max(0, rank - 5), min(size, rank + 4)):
        #     row = leaderboard.iloc[i]
        #     if row['SPOTTER'] == user:
        #         message_text += f"_*#{i + 1}: {row['NAME']} with {row['COUNT']} spots*_ \n"
        #         name = row['NAME']
        #     else:
        #         message_text += f"#{i + 1}: {row['NAME']} with {row['COUNT']} spots \n"

    message_ts = message["ts"]
    channel_id = message["channel"]

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        text="hello"
    )

# TODO: diversabot flag
@app.message("diversabot flag")
def flag_spot(message, client, logger):
    logger.warn(message)
    flagger = message['user']
    channel_id = message["channel"]

    if 'thread_ts' not in message:
        reply = f"{random_disappointed_greeting()} <@{flagger}>, to flag a spot, you have to reply 'diversaspot flag' in the thread of the spot that you'd like to flag."
        message_ts = message['ts']
    else:
        spot_ts = message['thread_ts']
        message_ts = spot_ts

        timestamp = conn.execute(
            text(
                " SELECT Time FROM diversaspots \
                WHERE Time = {message_ts}; "
                .format(message_ts=message_ts)
            )
        )
        if timestamp == None:
            reply = f"{random_disappointed_greeting()} <@{flagger}>, this is not a valid DiversaSpot to flag!"
        else:
            spotter = conn.execute(
                text(
                    " SELECT Name FROM diversaspots \
                    WHERE Time = {spot_ts}; "
                    .format(spot_ts=spot_ts)
                )
            )
            # TODO: fix bug where won't @ the spotter idk why
            for line in spotter:
                spotter = line[0]
                break
            conn.execute(
                text(
                    " UPDATE diversaspots \
                    SET Flagged = 1 \
                    WHERE Time = {spot_ts}; "
                    .format(spot_ts=spot_ts)
                )
            )
            conn.commit()
            
            reply = f"{random_disappointed_greeting()} <@{spotter}>, this spot has been flagged by <@{flagger}> as they believe it is in violation of the official DiversaSpotting rules and regulations. If you would like to review the official DiversaSpotting rules and regulations, you can type 'diversabot rules'. If you would like to dispute this flag, please @ Thomas Wang or Clara Tu in this thread with a relevant explanation."
    
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        text=reply
    )

# TODO: diversabot stats
# TODO: diversabot team leaderboard
# TODO: diversabot miss
# TODO: diversabot help (can copy and paste technically)
# TODO: diversabot recap (automatic and not an action) — recap with who spotted the most that week, who was the most spotted, and like 3-5 pics of most reacted to spots (need to implement a count reacts)
# TODO: diversabot unflag (only allowed by me or tommy)
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
