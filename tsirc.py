import feedparser
import lurklib
import time
from urllib.parse import quote as urlquote


def msg(msg):
	print("[%s] %s" % (time.strftime("%X", time.localtime()), msg))


class SearchFeed:
	def __init__(self, query):
		self.url = 'http://search.twitter.com/search.atom?q=' + urlquote(query)
		self.update_feed()
		self.last_tweet = None
		
		i = min(len(self.feed['entries']), 5)
		if i > 0:
			self.last_tweet = self.feed['entries'][i]['published_parsed']

	def update_feed(self):
		self.feed = feedparser.parse(self.url)

	def get_new_entries(self):
		self.update_feed()
		
		results = []
		dt = None
		for entry in reversed(self.feed['entries']):
			dt = entry['published_parsed']
			if not self.last_tweet or dt > self.last_tweet:
				results.append(self._format_message(entry))
		
		self.last_tweet = dt
		return results

	def _format_message(self, entry):
		return "(@%s) %s [ %s ]" % (
			entry['author'].split(' ')[0], 
			entry['title'], 
			entry['link']
		) 


class BrokenClientWorkaround(lurklib.Client):
	def process_once(self, timeout=0.01):
			try:
				event = self.recv(timeout)
				if event:
					event_t = event[0]
					event_c = event[1]
	
					if event_t == 'JOIN':
						self.on_join(event_c[0], event_c[1])
					elif event_t == 'PART':
						self.on_part(event_c[0], event_c[1], event_c[2])
					elif event_t == 'PRIVMSG':
						if event_c[1] in self.channels.keys():
							self.on_chanmsg(event_c[0], event_c[1], event_c[2])
						else:
							self.on_privmsg(event_c[0], event_c[2])
					elif event_t == 'NOTICE':
						if event_c[1] in self.channels.keys():
							self.on_channotice(event_c[0], event_c[1], event_c[2])
						else:
							self.on_privnotice(event_c[0], event_c[2])
					elif event_t == 'CTCP':
						if event_c[1] in self.channels.keys():
							self.on_chanctcp(event_c[0], event_c[1], event_c[2])
						else:
							self.on_privctcp(event_c[0], event_c[2])
					elif event_t == 'CTCP_REPLY':
						self.on_ctcp_reply(event_c[0], event_c[2])
					elif event_t == 'MODE':
						if event_c[0] == self.current_nick:
							self.on_umode(event_c[1])
						else:
							self.on_cmode(event_c[0], event_c[1], event_c[2])
					elif event_t == 'KICK':
						self.on_kick(event_c[0], event_c[1], event_c[2], \
						event_c[3])
					elif event_t == 'INVITE':
						self.on_invite(event_c[0], event_c[2])
					elif event_t == 'NICK':
						self.on_nick(event_c[0], event_c[1])
					elif event_t == 'TOPIC':
						self.on_topic(event_c[0], event_c[1], event_c[2])
					elif event_t == 'QUIT':
						self.on_quit(event_c[0], event_c[1])
					elif event_t == 'LUSERS':
						self.on_lusers(event_c)
					elif event_t == 'ERROR':
						self.on_error(event_c[0])
					elif event_t == 'UNKNOWN':
						self.on_unknown(event_c[0])
	
			except self.LurklibError as exception:
				self.on_exception(exception)


class Bot(BrokenClientWorkaround): 
	def __init__(self, server, nick, channels, wait=30):
		lurklib.Client.__init__(self, server=server, nick=nick)
		self.feeds = {}
		self.wait = wait

		for c in channels:
			self.feeds[c] = None

	def mainloop(self):
		last_time = time.time()
		while self.keep_going:
			with self.lock:
				if self.on_connect and not self.readable(2):
					self.on_connect()
					self.on_connect = None
				if not self.keep_going:
					break
				self.process_once()
				
				if time.time() > last_time + self.wait:
					self.send_messages()
					last_time = time.time()

	def send_messages(self, channel=None):
		if channel and self.feeds.get(channel):
			entries = self.feeds[channel].get_new_entries()
			msg("%s new tweets for '%s'." % (len(entries), channel))
			for e in entries:
				self.privmsg(self.sanitise_channel(channel), e)
			return

		for channel, feed in self.feeds.items():
			entries = feed.get_new_entries()
			msg("%s new tweets for '%s'." % (len(entries), channel))
			for e in entries:
				self.privmsg(self.sanitise_channel(channel), e)

	def on_connect(self):
		msg("Connected!")
		for c in self.feeds.keys():
			self.join(c)

	def sanitise_channel(self, channel):
		return "#" + channel.replace(' ', '+')

	def join(self, channel):
		schannel = self.sanitise_channel(channel)
		msg("Joined %s." % schannel)
		self.join_(schannel)

		self.feeds[channel] = SearchFeed(channel)
		self.send_messages(channel)
	
	def part(self, channel):
		schannel = self.sanitise_channel(channel)
		msg("Parted %s." % schannel)
		self.part_(schannel)

		del self.feeds[channel]


if __name__ == "__main__":
	import sys
	if len(sys.argv) <= 1:
		sys.exit()
	
	server = sys.argv[1]
	channels = sys.argv[2:]

	bot = Bot(
		server=server, 
		nick=("twtrbot", "twtrbot_"),
		channels=channels
	)

	bot.mainloop()
	
	
		
