import os
import requests
import json
import zulip
import random
from pymongo import MongoClient
from collections import defaultdict
from enum import Enum

SENTIMENT_URL = 'http://text-processing.com/api/sentiment/'
MONGO_URI = 'localhost'
MONGO_DB = 'test'

client = zulip.Client(email=os.environ['ZULIP_BOT_EMAIL'], api_key=os.environ['ZULIP_KEY'])
mongo = MongoClient()
db = mongo.test
#user = db.users.find_one(email=email)
msg_log = {}
mood_msg = defaultdict(list)

class Message(object):
	def __init__(self, msg, mood=None):
		self.msg = msg
		self.mood = mood

def set_mood_messages():
	for obj in list(db.messages.find()):
		mood, msg = obj['type'], obj['message']
		mood_msg[mood].append(msg)

def get_mood_msg(mood):
	# this will raises IndexError if mood_msg[mood] is empty
	return random.choice(mood_msg[mood])

def sent_analysis(content):
	resp = requests.post(SENTIMENT_URL, data=dict(text=content))
	status = resp.status_code
	
	if status == 503: # we've gone over the API limit
		return 'I\'ve been chatting too much. I need a break! Talk to me some other day'
	
	if status == 400:
		return 'I don\'t understand you!'

	replies = {
		'neg': Message('I guess you are not happy? :cry:', 'unhappy'),
		'pos': Message('I think you are happy!? :smiley:', 'happy'),
		'neutral': Message('You sound neutral?', 'okay')
	}
	return replies[json.loads(resp.text)['label']]

def process(msg):
	content = msg['content'].lower()
	sender = msg['sender_email']

	# TODO: calculate precision recall F1 score 
	# TODO: find user by email and get mood history
	if sender in msg_log:
		if content == 'yes':
			last_msg = msg_log.pop(sender)
			reply = get_mood_msg(last_msg.mood)
		elif content == 'no':
			last_msg = msg_log.pop(sender)
			reply = 'Okay I give up! Just tell me if you are `happy`, `okay` or `unhappy` by typing in `mood <your mood>`'
		else:
			reply = 'I\'m confused :confused:. Please say yes or no!'
	else:
		result = sent_analysis(content)
		reply = result.msg
		msg_log[sender] = Message(reply, result.mood)
	
	client.send_message({
			'type': msg['type'], 
			'to': sender,
			'content': reply
		})

if __name__ == '__main__':
	set_mood_messages()
	# Listening: This is a blocking call that will run forever
	client.call_on_each_message(process)
