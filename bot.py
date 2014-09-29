import os
import requests
import json
import zulip
import random
from pymongo import MongoClient
from collections import defaultdict
from collections import namedtuple

SENTIMENT_URL = 'http://text-processing.com/api/sentiment/'
# TODO: change this
MONGO_URI = 'localhost'
DB_NAME = 'test'

class Message(object):
	def __init__(self, msg, mood=None):
		self.msg = msg
		self.mood = mood

class MoodBot(object):

	def __init__(self, msg_log={}, mood_msgs=defaultdict(list)):
		self.msg_log = msg_log
		self.mood_msgs = mood_msgs
		self.setup();

	def setup(self):
		self.client = zulip.Client(
			email=os.environ['ZULIP_BOT_EMAIL'], 
			api_key=os.environ['ZULIP_KEY']
		)

		self.db = MongoClient()[DB_NAME]
		for obj in list(self.db.messages.find()):
			mood, msg = obj['type'], obj['message']
			self.mood_msgs[mood].append(msg)

	def get_mood_msg(self, mood):
		# this will raises IndexError if mood_msg[mood] is empty
		return random.choice(self.mood_msgs[mood])

	def sentiment_analysis(self, content):
		resp = requests.post(SENTIMENT_URL, data=dict(text=content))
		status = resp.status_code
		
		if status == 503: # we've gone over the API limit
			return 'I\'ve been chatting too much. I need a break! Talk to me some other day'
		
		if status == 400:
			return 'I don\'t understand you!'

		replies = {
			'pos': Message('I think you are happy!? :smiley:', 'happy'),
			'neg': Message('I guess you are not happy? :cry:', 'unhappy'),
			'neutral': Message('You sound neutral? :neutral_face:', 'okay')
		}
		return replies[json.loads(resp.text)['label']]

	def process(self, msg):
		sender = msg['sender_email']
		# prevent the bot from talking to itself
		if sender == 'mood-bot@students.hackerschool.com': return

		# TODO: find user by email and get mood history?
		content = msg['content'].lower()

		if content.startswith(('hi', 'hello', 'hey', 'mood-log')):
			user = self.db.users.find_one({'email': sender})
			if not user:
				reply = 'I don\'t know you. Please introduce yourself on [Mood Tracker](http://hs-mood.herokuapp.com).'
			else:
				reply = self.make_emoji_log(user['moods'])
		# fetch the last message for the sender if exist
		elif sender in self.msg_log:
			if content.startswith('yes'):
				last_msg = self.msg_log.pop(sender)
				reply = self.get_mood_msg(last_msg.mood)
			elif content.startswith('no'):
				last_msg = self.msg_log.pop(sender)
				reply = 'Give me another chance!'
			else:
				reply = 'I\'m confused :confused:. Please say yes or no!'
		else:
			result = self.sentiment_analysis(content)
			reply = result.msg
			self.msg_log[sender] = Message(reply, result.mood)
		
		self.client.send_message({
				'type': msg['type'], 
				'to': sender,
				'content': reply
			})

	def make_emoji_log(self, moods):
		reply = ''
		emoji = {
			'happy': ':smiley:',
			'unhappy': ':cry:',
			'okay': ':neutral_face:'
		}

		for date in sorted(moods.keys()):
			#reply += "%s: %s\t" % (date, emoji[moods[date]])
			reply += emoji[moods[date]]
		return reply

if __name__ == '__main__':
	bot = MoodBot()
	# Listening: This is a blocking call that will run forever
	bot.client.call_on_each_message(bot.process)
