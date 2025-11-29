from flask import Flask, request, render_template_string
from datetime import datetime
import csv
import os
import pandas as pd

app = Flask(__name__)

# ファイルパス
BASE_DIR = '/home/takano/ダウンロード/Python/貸出品管理システム'
CSV_FILE = os.path.join(BASE_DIR, 'transactions.csv')
USER_MASTER_FILE = os.path.join(BASE_DIR, 'user_master.csv')
ITEM_MASTER_FILE = os.path.join(BASE_DIR, 'item_master.csv')

# スタイル（スマホ対応）
STYLE = '''
<style>
body { font-family: sans-serif; padding: 1em; max-width: 600px; margin: auto; }
h2 { font-size: 1.5em; }
button, select { font-size: 1.2em; padding: 0.5em; width: 100%; margin-top: 1em; }
input[type="text"] { font-size: 1.2em; padding: 0.5em; width: 100%; }
a.button {
    display: block;
    padding: 1em;
    margin: 1em 0;
    background: #007BFF;
    color: white;
    text-align: center;
    text-decoration: none;
    border-radius: 8px;
    font-size: 1.2em;
}
</style>
'''

# HTMLテンプレート：貸出・返却フォーム
HTML_FORM = STYLE + '''
<h2>備品貸出 / 返却フォーム</h2>
<p><strong>備品ID:</strong> {{ item_id }}</p>
<p><strong>アイテム名:</strong> {{ item_name }}</p>
<p><strong>現在の状態:</strong> {{ current_status }}</p>
<form method="post">
  <input type="hidden" name="item_id" value="{{ item_id }}">
  <input type="hidden" name="item_name" value="{{ item_name }}">
  {% if status == '貸出中' %}
    <p><strong>返却者:</strong> {{ current_user }}</p>
    <input type="hidden" name="user_name" value="{{ current_user }}">
  {% else %}
    <label>お名前を選択:</label><br>
    <select name="user_name" required>
      {% for name in names %}
        <option value="{{ name }}">{{ name }}</option>
      {% endfor %}
    </select>
  {% endif %}
  {% if status == '貸出中' %}
    <button type="submit" name="action" value="返却">返却を記録</button>
  {% elif status == '返却済' %}
    <button type="submit" name="action" value="貸出">貸出を記録</button>
  {% endif %}
</form>
'''

# HTMLテンプレート：完了画面
HTML_DONE = STYLE + '''
<h2>処理が完了しました</h2>
<p>ご協力ありがとうございました。</p>
<a class="button" href="/menu">メニューに戻る</a>
'''

# HTMLテンプレート：未返却一覧
HTML_UNRETURNED = STYLE + '''
<h2>未返却備品一覧</h2>
{% if data %}
<table border="1" cellpadding="8">
<tr><th>備品ID</th><th>アイテム名</th><th>貸出者</th><th>貸出日時</th></tr>
{% for row in data %}
<tr><td>{{ row.item_id }}</td><td>{{ row.item_name }}</td><td>{{ row.user_name }}</td><td>{{ row.timestamp }}</td></tr>
{% endfor %}
</table>
{% else %}
<p>未返却の備品はありません。</p>
{% endif %}
<a class="button" href="/menu">メニューに戻る</a>
'''

# HTMLテンプレート：メニュー画面（Excel削除済）
HTML_MENU = STYLE + '''
<h2>貸出管理メニュー</h2>
<a class="button" href="/unreturned">📋 未返却リストを表示</a>
<p style="font-size:0.9em; color:gray;">※ 貸出・返却処理はQRコードからアクセスしてください。</p>
'''

# ===== ルート定義 =====

@app.route('/lend', methods=['GET', 'POST'])
def lend():
    if request.method == 'POST':
        action = request.form['action']
        item_id = request.form['item_id']
        item_name = request.form['item_name']
        user_name = request.form['user_name']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(['日時', '動作', '備品ID', 'アイテム名', '名前'])
            writer.writerow([timestamp, action, item_id, item_name, user_name])

        return render_template_string(HTML_DONE)

    item_id = request.args.get('item_id', '')
    item_name = get_item_name(item_id)
    status, last_user = get_current_status_and_user(item_id)
    current_status = f"貸出中（{last_user} さんが使用中）" if status == '貸出中' else "貸出可能"
    names = load_user_master()

    return render_template_string(
        HTML_FORM,
        item_id=item_id,
        item_name=item_name,
        names=names,
        current_status=current_status,
        status=status,
        current_user=last_user
    )

@app.route('/done')
def done():
    return render_template_string(HTML_DONE)

@app.route('/unreturned')
def unreturned():
    if not os.path.exists(CSV_FILE):
        return render_template_string(HTML_UNRETURNED, data=[])

    df = pd.read_csv(CSV_FILE)
    latest = df.groupby('備品ID').tail(1)
    unreturned = latest[latest['動作'] == '貸出']

    result = []
    for _, row in unreturned.iterrows():
        result.append({
            'item_id': row['備品ID'],
            'item_name': row['アイテム名'],
            'user_name': row['名前'],
            'timestamp': row['日時']
        })

    return render_template_string(HTML_UNRETURNED, data=result)

@app.route('/menu')
def menu():
    return render_template_string(HTML_MENU)

# ===== ユーティリティ関数 =====

def load_user_master():
    try:
        df = pd.read_csv(USER_MASTER_FILE)
        return df['名前'].dropna().tolist()
    except:
        return []

def get_item_name(item_id):
    try:
        df = pd.read_csv(ITEM_MASTER_FILE)
        match = df[df['item_id'] == item_id]
        return match.iloc[0]['アイテム名'] if not match.empty else f"(不明なID: {item_id})"
    except:
        return "(読み込み失敗)"

def get_current_status_and_user(item_id):
    try:
        if not os.path.exists(CSV_FILE):
            return "返却済", ""
        df = pd.read_csv(CSV_FILE)
        df_item = df[df['備品ID'] == item_id]
        if df_item.empty:
            return "返却済", ""
        last_row = df_item.iloc[-1]
        return ("貸出中", last_row['名前']) if last_row['動作'] == "貸出" else ("返却済", "")
    except:
        return "状態不明", ""

# Flaskアプリ実行
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
