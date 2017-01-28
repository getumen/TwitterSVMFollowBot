import requests
import datetime

d = datetime.datetime.now()+datetime.timedelta(days=90)
TWEET_FILTER_WORDS = []

while len(TWEET_FILTER_WORDS) < 399:
    year_str = str(d.year)
    season_str = str(int((d.month-1)/3)+1)
    response = requests.get('http://api.moemoe.tokyo/anime/v1/master/'+year_str+'/'+season_str).json()
    key_words = []
    key_words += [t['twitter_hash_tag'] for t in response ]
    key_words += [t['title_short1'] for t in response if t != '']
    key_words += [t['title_short2'] for t in response if t != '']
    key_words += [t['title_short3'] for t in response if t != '']

    d = d - datetime.timedelta(days=90)

    TWEET_FILTER_WORDS += [k for k in key_words if len(k)>0]
    TWEET_FILTER_WORDS = list(set(TWEET_FILTER_WORDS))
    print(len(TWEET_FILTER_WORDS))

TWEET_FILTER_WORDS = TWEET_FILTER_WORDS[:399]
# days
PENDING_TIME = 10
FOLLOW_PER_TWEET = 3000
FOLLOW_AT_ONCE = 5
FOLLOW_BACK_AT_ONECE = 20
REMOVE_AT_ONCE = 5
