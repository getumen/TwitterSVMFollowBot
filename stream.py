import tweepy
import os
import env
import sqlite3
import MeCab
import time
import datetime
import numpy as np
from sklearn import svm
from scipy import stats


class MyExeption(BaseException): pass


class StreamListener(tweepy.streaming.StreamListener):

    def __init__(self):
        super(StreamListener,self).__init__()
        self.conn = sqlite3.connect('tweet.db')
        self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TABLE IF NOT EXISTS user
             (statuses_count integer DEFAULT 0,
             followers_count integer DEFAULT 0,
             friends_count integer,
             protected boolean DEFAULT 0,
             favourites_count integer DEFAULT 0,
             user_id integer PRIMARY KEY )''')
        self.cur.execute('CREATE TABLE IF NOT EXISTS word (word text)')
        self.mecab = MeCab.Tagger()
        self.count = 1
        self.conn.commit()

    def __del__(self):
        self.cur.close()
        self.conn.close()

    def _parse_status(self, status):
        user = status.author
        followers_count = user.followers_count
        friends_count = user.friends_count
        protected = user.protected
        favourites_count = user.favourites_count
        statuses_count = user.statuses_count
        user_id = user.id
        return statuses_count, followers_count, friends_count, protected, favourites_count, user_id

    def _parse_text(self, text):
        parsed = self.mecab.parse(text)
        words = [w for w in [w.split('\t') for w in parsed.split('\n')] if len(w) >= 2]
        return [(w[0],) for w in words if w[1] and w[1].split(',')[0] == '名詞']

    def on_status(self, status):
        if status.lang != 'ja':
            return True
        self.cur.execute("REPLACE INTO user VALUES (?,?,?,?,?,?)", self._parse_status(status))
        # self.cur.executemany("INSERT INTO word VALUES (?)", self._parse_text(status.text))
        self.count += 1
        print(self.count, status.text.rstrip())
        if self.count % 100 == 0:
            self.conn.commit()
        if self.count % env.FOLLOW_PER_TWEET == 0:
            raise MyExeption
        return True

    def on_error(self, status_code):
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
    _auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    _auth.set_access_token(access_key, access_secret)
    return _auth


class ML(object):

    def __init__(self):
        super(object, self).__init__()
        self.api = tweepy.API(get_oauth())
        self.conn = sqlite3.connect('tweet.db')
        self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TABLE IF NOT EXISTS following(user_id INTEGER PRIMARY KEY)''')
        self.cur.execute('''CREATE TABLE IF NOT EXISTS followed(user_id INTEGER PRIMARY KEY)''')
        self.cur.execute('''CREATE TABLE IF NOT EXISTS data(
        user_id INTEGER PRIMARY KEY,
        label INTEGER,
        ts datetime
        )''')
        self.conn.commit()

    def __del__(self):
        self.cur.close()
        self.conn.close()

    def follow_user(self, follow_id):
        try:
            self.api.create_friendship(id=int(follow_id))
        except tweepy.error.TweepError:
            pass

    def update_relation(self):
        my_id = self.api.me().id
        followed_list = self.api.followers_ids(id=my_id)
        self.cur.execute('DELETE FROM followed')
        self.conn.commit()
        self.cur.executemany('INSERT INTO followed VALUES (?)', [(e,) for e in followed_list])
        following_list = self.api.friends_ids(id=my_id)
        self.cur.execute('DELETE FROM following')
        self.conn.commit()
        self.cur.executemany('INSERT INTO following VALUES (?)', [(e,) for e in following_list])

    def update_label(self):
        self.cur.execute(
            '''insert or ignore into data select user_id, -1, ?
            from following where user_id not in (select user_id from data)''', (datetime.datetime.now(),))
        self.cur.execute('update data set label=1 WHERE user_id IN (SELECT user_id FROM followed)')
        self.conn.commit()
        self.cur.execute('''select following.user_id from following,data
        where following.user_id = data.user_id AND ts<(select ?)
        AND following.user_id NOT IN (SELECT user_id FROM followed)''',
                         (datetime.datetime.now()-datetime.timedelta(days=env.PENDING_TIME),))
        remove_list = self.cur.fetchall()
        for remove_id in remove_list:
            self.api.destroy_friendship(id=remove_id[0])
            time.sleep(1)
        self.cur.execute(
            '''update data set label=0 WHERE user_id IN
            (select following.user_id from following,data
            where following.user_id = data.user_id AND ts<(select ?)
            AND following.user_id NOT IN (SELECT user_id FROM followed))''',
            (datetime.datetime.now()-datetime.timedelta(days=env.PENDING_TIME),))
        self.conn.commit()

    def follow_back(self):
        self.cur.execute('''select user_id from followed WHERE user_id NOT IN
        (SELECT user_id FROM following)''')
        follow_list = self.cur.fetchall()
        count = 0
        for follow_id in follow_list:
            self.follow_user(follow_id[0])
            time.sleep(1)
            count += 1
        self.cur.execute('''insert into data selct user_id, 1, ? from followed WHERE user_id NOT IN
        (SELECT user_id FROM following''', (datetime.datetime.now()))
        self.conn.commit()
        return count

    def follow(self, num):
        self.cur.execute('''select label, statuses_count, followers_count, friends_count, protected, favourites_count
        from data, user where user.user_id=data.user_id AND label>=0''')
        Z = np.array(self.cur.fetchall(), dtype=np.float64)
        follow_list = []
        if len(Z.shape) == 2 and np.any(Z[:, 0] == 0) and np.any(Z[:, 0] == 1):
            y_train = np.nan_to_num(Z[:, 0]).astype(int)
            X_train = np.nan_to_num(Z[:, 1:])
            self.cur.execute('''select user_id, statuses_count, followers_count, friends_count, protected, favourites_count
                        from user WHERE user_id not in (SELECT user_id FROM followed)
                        and user_id not in (SELECT user_id FROM following)
                        and user_id not in (SELECT user_id FROM data)''')
            user_data = np.array(self.cur.fetchall(), dtype=np.float64)
            X_predict = np.nan_to_num(user_data[:, 1:])
            n_train, p = X_train.shape
            n_predict, _ = X_predict.shape
            X = np.zeros((n_train+n_predict, p))
            X[:n_train, :] = X_train
            X[n_train:, :] = X_predict
            X = np.nan_to_num(stats.zscore(X.copy(), axis=0))
            X_train = X[:n_train, :]
            X_predict = X[n_train:, :]

            clf = svm.SVC(probability=True)
            clf.fit(X_train, y_train)

            score_list = []
            y_predict = clf.predict(X_predict)
            y_score = np.absolute(clf.decision_function(X_predict))
            y_score[y_predict == 0] = -y_score[y_predict == 0]
            v= y_score
            for i in range(len(y_score)):
                score_list.append((user_data[i, 0], v[i]))
            score_list = sorted(score_list, key=lambda e: e[1], reverse=True)
            print(score_list[:num])
            follow_list = [e[0] for e in score_list[:num]]
            delete_list = [e[0] for e in score_list[:500]] if len(score_list) > 500 else []
            self.cur.execute('delete from user where user_id in ('+','.join('?'*len(delete_list))+') and user_id not in (select user_id from data)')
        else:
            self.cur.execute(
                '''select user_id from user
                WHERE user_id not in (SELECT user_id FROM followed)
                and user_id not in (SELECT user_id FROM following) ORDER BY RANDOM() limit ?''', (num,))
            follow_list = [r[0] for r in self.cur.fetchall()]
        for follow_id in follow_list:
            self.follow_user(follow_id)
            time.sleep(1)
        param = [(uid, -1, datetime.datetime.now()) for uid in follow_list]
        self.cur.executemany('''replace into data VALUES (?,?,?)''', param)
        self.conn.commit()

    def run(self):
        self.update_relation()
        self.update_label()
        count = self.follow_back()
        me = self.api.me()
        friend = me.friends_count
        followed = me.followers_count
        can_follow = max(5000, int(followed*1.1)) - friend
        follow_num = min(can_follow, env.FOLLOW_AT_ONCE-count if env.FOLLOW_AT_ONCE-count >= 0 else 0)
        self.follow(follow_num)


if __name__ == '__main__':
    auth = get_oauth()
    stream = tweepy.Stream(auth, StreamListener())
    while True:
        try:
            stream.filter(track=env.TWEET_FILTER_WORDS)
        except MyExeption:
            time.sleep(60)
            ml = ML()
            ml.run()
            time.sleep(60)
            stream = tweepy.Stream(auth, StreamListener())
