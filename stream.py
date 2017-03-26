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
import random
import requests


class MyExeption(BaseException): pass


class WarningException(BaseException): pass


def parse_user_data(user):
    followers_count = user.followers_count
    friends_count = user.friends_count
    protected = user.protected
    favourites_count = user.favourites_count
    statuses_count = user.statuses_count
    user_id = user.id
    return statuses_count, followers_count, friends_count, protected, favourites_count, user_id

def parse_status(status):
    user = status.author
    return parse_user_data(user)


def get_oauth():
    consumer_key = os.environ['TWITTER_CONSUMER_KEY']
    consumer_secret = os.environ['TWITTER_CONSUMER_SECRET']
    access_key = os.environ['TWITTER_ACCESS_KEY']
    access_secret = os.environ['TWITTER_ACCESS_SECRET']
    _auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    _auth.set_access_token(access_key, access_secret)
    return _auth


class StreamListener(tweepy.streaming.StreamListener):

    def __init__(self, status_list):
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
        self.count = len(status_list)
        self.conn.commit()
        self.status_list = status_list

    def free_conn(self):
        self.cur.close()
        self.conn.close()

    def _parse_text(self, text):
        parsed = self.mecab.parse(text)
        words = [w for w in [w.split('\t') for w in parsed.split('\n')] if len(w) >= 2]
        return [(w[0],) for w in words if w[1] and w[1].split(',')[0] == '名詞']

    def on_status(self, status):
        self.status_list.append(status)
        # self.cur.executemany("INSERT INTO word VALUES (?)", self._parse_text(status.text))
        self.count += 1

        print(self.count, status.text.replace('\n', '').replace('\r', ''))
        if self.count % 100 == 0:
            self.conn.commit()
        if self.count % env.FOLLOW_PER_TWEET == 0:
            raise MyExeption
        return True

    def on_error(self, status_code):
        if status_code == 420:
            raise MyExeption
        return False

    def on_timeout(self):
        raise MyExeption

    def on_limit(self, track):
        """Called when a limitation notice arrives"""
        with open('error_log.txt','a') as f:
            f.write('bursting {}\n'.format(track))

    def on_warning(self, notice):
        print(notice)
        with open('error_log.txt','a') as f:
            f.write('{}\n'.format(notice))
        raise WarningException


    def on_disconnect(self, notice):
        """Called when twitter sends a disconnect notice
        Disconnect codes are listed here:
        https://dev.twitter.com/docs/streaming-apis/messages#Disconnect_messages_disconnect
        """
        with open('error_log.txt','a') as f:
            f.write('disconnect\n')
        raise MyExeption


class ML(object):

    def __init__(self, status_list):
        super(object, self).__init__()
        self.api = tweepy.API(get_oauth())
        sqlite3.enable_callback_tracebacks(True)
        self.conn = sqlite3.connect('tweet.db')
        self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TABLE IF NOT EXISTS following(user_id INTEGER PRIMARY KEY)''')
        self.cur.execute('''CREATE TABLE IF NOT EXISTS followed(user_id INTEGER PRIMARY KEY)''')
        self.cur.execute('''CREATE TABLE IF NOT EXISTS data(
        user_id INTEGER PRIMARY KEY,
        label INTEGER,
        ts datetime
        )''')
        self.cur.executemany(
            "REPLACE INTO user VALUES (?,?,?,?,?,?)",
            [parse_status(status) for status in status_list]
        )
        self.conn.commit()

    def free_conn(self):
        self.cur.close()
        self.conn.close()

    def follow_user(self, follow_id, wt=1):
        follow_id = int(follow_id)
        try:
            time.sleep(random.random()*wt*60)
            self.api.create_friendship(user_id=follow_id)
        except tweepy.error.TweepError as e:
            with open('error_log.txt','a') as f:
                f.write('{} user_id={},\n'.format(e.reason, follow_id))
            if e.api_code == 162:
                self.cur.execute('replace into data VALUES (?, 0, ?)', (follow_id, datetime.datetime.now()))
            elif e.api_code == 108:
                self.cur.execute('delete FROM user where user_id = ?', (follow_id,))
            else:
                pass

    def remove_user(self, remove_id):
        remove_id = int(remove_id)
        try:
            time.sleep(random.random()*2*60)
            self.api.destroy_friendship(user_id=remove_id)
        except tweepy.error.TweepError as e:
            with open('error_log.txt','a') as f:
                f.write('{} user_id={},\n'.format(e.reason, remove_id))


    def update_relation(self):
        my_id = self.api.me().id
        followed_list = []
        following_list = []
        me = self.api.me()
        followed_list = self.api.followers_ids(me.id)
        following_list = self.api.friends_ids(me.id)
        if me.followers_count != len(followed_list):
            print(me.followers_count, len(followed_list))
            for followers in tweepy.Cursor(self.api.followers).pages():
                print(followers)
                followed_list += [follower.id for follower in followers]
                followed_list = list(set(followed_list))
                time.sleep(60)
        if me.friends_count != len(following_list):
            print(me.friends_count, len(following_list))
            for followings in tweepy.Cursor(self.api.friends).pages():
                print(followings)
                following_list += [following.id for following in followings]
                following_list = list(set(following_list))
                time.sleep(60)
        self.cur.execute('DELETE FROM followed')
        self.conn.commit()
        self.cur.executemany('INSERT INTO followed VALUES (?)', [(e,) for e in followed_list])

        self.cur.execute('DELETE FROM following')
        self.conn.commit()
        self.cur.executemany('INSERT INTO following VALUES (?)', [(e,) for e in following_list])
        return len(following_list), len(followed_list)

    def update_label(self):
        self.cur.execute(
            '''insert or ignore into data select user_id, -1, ?
            from following where user_id not in (select user_id from data)''', (datetime.datetime.now(),))
        self.cur.execute('update data set label=1 WHERE user_id IN (SELECT user_id FROM followed)')
        self.conn.commit()
        self.cur.execute('''select user_id from data
        where label=-1 AND ts<(select ?)
        AND user_id NOT IN (SELECT user_id FROM followed)''',
        (datetime.datetime.now()-datetime.timedelta(days=env.PENDING_TIME),))
        remove_list = [e[0] for e in self.cur.fetchall()][:env.REMOVE_AT_ONCE]
        for remove_id in remove_list:
            self.remove_user(remove_id)

        self.cur.execute(
            '''update data set label=0 WHERE user_id IN
            (select user_id from data
            where label=-1 AND ts<(select ?)
            AND user_id IN ('''
            +','.join('?'*len(remove_list))
            +'''))''',
            [datetime.datetime.now()-datetime.timedelta(days=env.PENDING_TIME),]+remove_list)
        self.conn.commit()


    def follow_back(self, wt=1):
        self.cur.execute('''select user_id from followed WHERE user_id NOT IN
        (SELECT user_id FROM following)''')
        follow_list = [e[0] for e in self.cur.fetchall()][:env.FOLLOW_BACK_AT_ONECE]
        for follow_id in follow_list:
            self.follow_user(follow_id, wt)
        self.cur.execute(
            'replace into data select user_id, 1, ? from followed '
            + 'WHERE user_id IN ('
            +','.join('?'*len(follow_list))+')', [datetime.datetime.now()]+ follow_list)
        self.conn.commit()

    def follow(self, num):
        self.cur.execute('''select label, statuses_count, followers_count, friends_count, protected, favourites_count
        from data, user where user.user_id=data.user_id AND label>=0''')
        Z = np.array(self.cur.fetchall(), dtype=np.float64)
        follow_list = []
        if len(Z.shape) == 2 and np.any(Z[:, 0] == 0) and np.any(Z[:, 0] == 1):
            y_train = Z[:, 0].astype(int)
            X_train = Z[:, 1:]
            self.cur.execute('''select user_id, statuses_count, followers_count, friends_count, protected, favourites_count
                        from user WHERE user_id not in (SELECT user_id FROM followed)
                        and user_id not in (SELECT user_id FROM following)
                        and user_id not in (SELECT user_id FROM data)''')
            query_result = self.cur.fetchall()
            user_ids = [e[0] for e in query_result]
            user_data = np.array(query_result, dtype=np.float64)
            X_predict = user_data[:, 1:]
            n_train, p = X_train.shape
            n_predict, _ = X_predict.shape
            X = np.zeros((n_train+n_predict, p+6))

            X[:n_train, :p] = X_train
            X[n_train:, :p] = X_predict

            X[:,p] = X[:,1]/(X[:,2]+1)
            X[:,p+1] = X[:,1]-X[:,2]
            X[:,p+2] = X[:,1]/(X[:,3]+1)
            X[:,p+3] = X[:,1]-X[:,3]
            X[:,p+4] = X[:,2]/(X[:,3]+1)
            X[:,p+5] = X[:,2]-X[:,3]

            X = np.nan_to_num(stats.zscore(X.copy(), axis=0))
            X_train = X[:n_train, :]
            X_predict = X[n_train:, :]

            clf = svm.SVC(probability=True)
            clf.fit(X_train, y_train)

            score_list = []
            y_predict = clf.predict(X_predict)
            y_score = np.absolute(clf.decision_function(X_predict))
            y_score[y_predict == 0] = -y_score[y_predict == 0]
            v = y_score
            for i in range(len(y_score)):
                score_list.append((user_ids[i], v[i]))
            score_list = sorted(score_list, key=lambda e: e[1], reverse=True)
            print(score_list[:num])
            with open('score_log.txt', 'a') as f:
                f.write(str(score_list[:num])+'\n')
            follow_list = [e[0] for e in score_list[:num]]
            delete_list = [e[0] for e in score_list[int(num*1000):]] if len(score_list) > int(num*1000) else []
            self.cur.execute(
                'delete from user where user_id in ('
                +','.join('?'*len(delete_list))
                +') and user_id not in (select user_id from data)'
                , delete_list
            )
        else:
            self.cur.execute(
                '''select user_id from user
                WHERE user_id not in (SELECT user_id FROM followed)
                and user_id not in (SELECT user_id FROM following) ORDER BY RANDOM() limit ?''', (num,))
            follow_list = [r[0] for r in self.cur.fetchall()]
        for follow_id in follow_list:
            self.follow_user(follow_id)
        param = [(uid, -1, datetime.datetime.now()) for uid in follow_list]
        self.cur.executemany('''replace into data VALUES (?,?,?)''', param)
        self.conn.commit()

    def update_user(self):
        user_list = self.api.followers(self.api.me().id)
        user_data_list = [parse_user_data(u) for u in user_list]
        self.cur.executemany("REPLACE INTO user VALUES (?,?,?,?,?,?)", user_data_list)

    def run(self):
        print('update_relation')
        following_num, followed_num = self.update_relation()
        print('update_user')
        self.update_user()
        print('update_label')
        self.update_label()
        print('follow_back')
        self.follow_back()
        me = self.api.me()
        friend = me.friends_count
        followed = me.followers_count
        can_follow = max(5000, int(followed*1.1)) - friend
        follow_num = min(can_follow, env.FOLLOW_AT_ONCE)
        print('follow')
        if following_num < 3*followed_num:
            self.follow(follow_num)


if __name__ == '__main__':
    auth = get_oauth()
    status_list = []

    while True:
        try:
            lister = StreamListener(status_list)
            stream = tweepy.Stream(auth, lister)
            stream.filter(
                track=env.TWEET_FILTER_WORDS,
                languages=['ja'],
            )
        except MyExeption as e:
            pass
        except requests.packages.urllib3.exceptions.ProtocolError as e:
            with open('error_log.txt','a') as f:
                f.write('{}, status_list={}\n'.format(e, len(status_list)))
        except AttributeError as e:
            with open('error_log.txt','a') as f:
                f.write('{},\n'.format(e))
        except WarningException as e:
            print('Warning arrives')
            time.sleep(60*60)
        finally:
            lister.free_conn()

        if len(status_list) <= env.FOLLOW_PER_TWEET:
            continue

        try:
            ml = ML(status_list)
            ml.run()
            status_list.clear()
        except tweepy.error.TweepError as e:
            if e.api_code == 88:
                time.sleep(60*60)
            else:
                time.sleep(60*15)
            with open('error_log.txt','a') as f:
                f.write('ml error = {},\n'.format(e))

        except Exception as e:
            with open('error_log.txt','a') as f:
                f.write('ml error = {},\n'.format(e))
            time.sleep(60*15)
        finally:
            ml.free_conn()
