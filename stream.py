import sys
import tweepy
from tweepy.auth import OAuthHandler
from tweepy.api import API
import os
import env
import sqlite3
import MeCab

class MyExeption(BaseException): pass

class StreamListener(tweepy.streaming.StreamListener):

    def __init__(self):
        super(StreamListener,self).__init__()
        self.conn = sqlite3.connect('tweet.db')
        self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TABLE IF NOT EXISTS tweet
             (followers_count integer,
             friends_count integer,
             protected boolean,
             favourites_count integer,
             statuses_count integer,
             user_id integer)''')
        self.cur.execute('''CREATE TABLE IF NOT EXISTS word
             (word text)''')
        self.mecab = MeCab.Tagger()
        self.count = 1


    def __del__(self):
        self.c1.close()
        self.conn1.close()


    def _parse_status(self, status):
        user = status.author
        followers_count = user.followers_count
        friends_count = user.friends_count
        protected = user.protected
        favourites_count = user.favourites_count
        statuses_count = user.statuses_count
        user_id = user.id
        return (statuses_count, followers_count, friends_count, protected, favourites_count, user_id)


    def _parse_text(self, text):
        parsed = self.mecab.parse(text)
        words = [w for w in [w.split('\t') for w in parsed.split('\n')] if len(w)>=2]
        return [(w[0],) for w in words if w[1] and w[1].split(',')[0] == '名詞' ]


    def on_status(self, status):
        self.cur.execute("INSERT INTO tweet VALUES (?,?,?,?,?,?)", self._parse_status(status))
        self.cur.executemany("INSERT INTO word VALUES (?)", self._parse_text(status.text))

        self.count += 1
        if self.count % 100 == 0:
            self.conn.commit()
            self.count = 0
        return True

    def on_error(self,status):
        if status_code == 420:
            time.sleep(60*9)
            raise MyExeption
        return False

    def on_timeout(self):
        raise MyExeption


def get_oauth():
    consumer_key = os.environ['TWITTER_CONSUMER_KEY']
    consumer_secret = os.environ['TWITTER_CONSUMER_SECRET']
    access_key = os.environ['TWITTER_ACCESS_KEY']
    access_secret = os.environ['TWITTER_ACCESS_SECRET']
    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_key, access_secret)
    return auth

if __name__ == '__main__':
    auth = get_oauth()
    stream = tweepy.Stream(auth,StreamListener())
    while True :
        try:
            stream.filter(track=env.TWEET_FILTER_WORDS)
        except MyExeption:
            time.sleep(60)
            stream = tweepy.Stream(auth, StreamListener())
