Intelligent Twitter Bot
====

This bot automatically learn who probably follow you by support vector machine and follow a person who probably follow you.


## Usage

install.shを参考にライブラリを入れたり，コンシュマー，アクセストークンを手に入れる．  

env.pyのTWEET_FILTER_WORDSに取得したいツイートが含む単語のリストを入れる．  
(e.g. TWEET_FILTER_WORDS=['あああ','いいい'])  

env.pyのPENDING_TIMEにフォローしてから何日待つかを指定  
FOLLOW_PER_TWEETにはストリームに何ツイート流れたらユーザをフォローするか決める．  
FOLLOW_AT_ONCEには一度に何人フォローするか決める．  
`python3 stream.py`  

## 機能

- 自動フォロー返し
- SVMを用いてフォローするユーザを決める
