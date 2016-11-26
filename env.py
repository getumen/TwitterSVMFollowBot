import requests
from datetime import datetime as dt

year_str = str(dt.now().year)
season_str = str(int(dt.now().month/3)+1)
response = requests.get('http://api.moemoe.tokyo/anime/v1/master/'+year_str+'/'+season_str).json()
key_words = [t['twitter_hash_tag'] for t in response ]
key_words += [t['title_short1'] for t in response if t != '']
key_words += [t['title_short2'] for t in response if t != '']
key_words += [t['title_short3'] for t in response if t != '']

TWEET_FILTER_WORDS = [k for k in key_words if len(k)>0]

# days
PENDING_TIME = 3
FOLLOW_PER_TWEET = 10000
FOLLOW_AT_ONCE = 5
