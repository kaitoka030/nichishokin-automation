import re
import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from linebot import LineBotApi
from linebot.models import TextSendMessage

# --- GitHubの金庫から情報を読み出す設定 ---
# ローカルでテストする時は今まで通り文字列を入れ、GitHubに上げる時は空にします
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_TOKEN', 'あなたのトークンをここに貼る')
USER_ID = os.environ.get('LINE_USER_ID', 'あなたのIDをここに貼る')
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS')
#LINE APIの初期化
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)

# service_account.jsonの場所をカレントディレクトリに指定
base_path = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(base_path, 'service_account.json')

# Google Sheets APIに接続
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

if GOOGLE_CREDENTIALS_JSON:
    # GitHub上で動く場合（金庫から復元）
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
else:
    # 自分のPCで動く場合（今まで通りファイルから読み込み）
    base_path = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_path, 'service_account.json')
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)

client = gspread.authorize(creds)

sheet = client.open("銘柄一覧").sheet1

# シート内の全データを取得
all_data = sheet.get_all_values()
targets = []
for row in all_data[1:]: # 2行目以降
    url = row[1]
    name = row[2]
    if url: # URLが空でなければリストに追加
        targets.append({"name": name, "url": url})

# 確認表示
for target in targets:
    print(f"銘柄名: {target['name']} / URL: {target['url']}")
    url = target["url"]
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    #銘柄名と銘柄コードの抽出
    cop_name = soup.select_one(".heading__ttl").text
    match = re.search(r"^(.*?)\s*銘柄コード\s*(\d{4})(.*)$", cop_name)
    if match:
        name_before_code = match.group(1).strip() #銘柄名
        brand_code = match.group(2) #銘柄コード
        after_code = match.group(3).strip() #銘柄コードの後ろ全て
    else:
        name_before_code = ""
        brand_code = ""
        after_code = ""
    brand_after = f"{brand_code} {after_code}".strip()

    #品貸料率料率（品貸料率（品貸日数分/円）の取得
    item_rental_rate = soup.select_one(".result-detail__table-row:nth-of-type(11) td:nth-of-type(2)").text
    #差引残高の取得
    balance = soup.select_one(".result-detail__table-row:nth-of-type(9) td:nth-of-type(2)").text
    #応札ランクの取得
    rank = soup.select_one(".result-detail__table-row:nth-of-type(16) td:nth-of-type(2)").text
    #制限措置の取得
    limit = soup.select_one(".result-detail__table-row:nth-of-type(17) td:nth-of-type(2)").text
    #当日の制限措置の取得
    limit_today = soup.select_one(".result-detail__table-row:nth-of-type(17) td:nth-of-type(2)").text


    #LINEに送信するメッセージの作成
    message = f"""銘柄名: {name_before_code}
銘柄コード: {brand_code}
品貸料率（品貸日数分/円）: {item_rental_rate}
差引残高: {balance}
応札ランク: {rank}
制限措置: {limit}
当日の制限措置: {limit_today}"""

    #LINEにメッセージを送信
    try:
        line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
        print("LINEにメッセージを送信しました。")
    except Exception as e:
        print("LINEへのメッセージ送信に失敗しました。", e)