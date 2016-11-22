Intelligent Twitter Bot
====

製作中

## Usage

install.shを参考にライブラリを入れたり，コンシュマー，アクセストークンを手に入れる．

env.pyのTWEET_FILTER_WORDSに取得したいツイートが含む単語のリストを入れる．  
(e.g. TWEET_FILTER_WORDS=['あああ','いいい'])

env.pyのPENDING_TIMEにフォローしてから何日待つかを指定

`python3 stream.py`

## 機能

- 自動フォロー返し
- SVMを用いてフォローするユーザを決める
