import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
import time
from datetime import datetime

# 設定設定檔路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEYWORDS_FILE = os.path.join(BASE_DIR, 'keywords.txt')
SEEN_POSTS_FILE = os.path.join(BASE_DIR, 'seen_posts.json')

# 預設關鍵字（若本機 keywords.txt 不存在時寫入）
DEFAULT_KEYWORDS = ["王國之淚", "pokopia"]

# 模擬 Mock XML 資料（供企業內網測試與功能驗證使用）
MOCK_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>PTT Gamesale 看板</title>
  <updated>2026-07-20T14:00:00+08:00</updated>
  <entry>
    <title>[售] Switch 王國之淚 中文全新版</title>
    <link href="https://www.ptt.cc/bbs/gamesale/M.1111111111.A.001.html" />
    <id>https://www.ptt.cc/bbs/gamesale/M.1111111111.A.001.html</id>
    <author><name>gamer1</name></author>
    <published>2026-07-20T13:50:00+08:00</published>
    <content type="html"><![CDATA[售一片 Switch 王國之淚，全新未拆！]]></content>
  </entry>
  <entry>
    <title>[買] 全新 Switch 王國之淚 徵求中</title>
    <link href="https://www.ptt.cc/bbs/gamesale/M.2222222222.A.002.html" />
    <id>https://www.ptt.cc/bbs/gamesale/M.2222222222.A.002.html</id>
    <author><name>buyer1</name></author>
    <published>2026-07-20T13:52:00+08:00</published>
    <content type="html"><![CDATA[希望能徵到全新王國之淚。]]></content>
  </entry>
  <entry>
    <title>[售] 各平台 pokopia 序號現貨</title>
    <link href="https://www.ptt.cc/bbs/gamesale/M.3333333333.A.003.html" />
    <id>https://www.ptt.cc/bbs/gamesale/M.3333333333.A.003.html</id>
    <author><name>pokofan</name></author>
    <published>2026-07-20T13:55:00+08:00</published>
    <content type="html"><![CDATA[出售 pokopia 啟動序號！]]></content>
  </entry>
  <entry>
    <title>[售] Switch 瑪利歐賽車 實體版</title>
    <link href="https://www.ptt.cc/bbs/gamesale/M.4444444444.A.004.html" />
    <id>https://www.ptt.cc/bbs/gamesale/M.4444444444.A.004.html</id>
    <author><name>racerx</name></author>
    <published>2026-07-20T13:58:00+08:00</published>
    <content type="html"><![CDATA[售二手瑪利歐賽車 8。]]></content>
  </entry>
</feed>
"""

def load_keywords():
    """讀取 keywords.txt，如果不存在就自動建立預設關鍵字"""
    if not os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(DEFAULT_KEYWORDS) + '\n')
        print(f"已建立預設的關鍵字設定檔: {KEYWORDS_FILE}")
        return DEFAULT_KEYWORDS
    
    with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        keywords = [line.strip() for line in f if line.strip()]
    return keywords

def load_seen_posts():
    """讀取已通知文章清單"""
    if not os.path.exists(SEEN_POSTS_FILE):
        return []
    try:
        with open(SEEN_POSTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_seen_posts(seen_list):
    """保存已通知文章清單到 json，最多保留 200 筆，避免檔案過大"""
    seen_list = seen_list[-200:]
    with open(SEEN_POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(seen_list, f, ensure_ascii=False, indent=2)

def fetch_feed(use_mock=False):
    """抓取 PTT Gamesale RSS XML 內容，支援自動代理切換"""
    if use_mock:
        print("💡 正在使用本地偽裝資料 (Mock Mode) 執行測試。")
        return MOCK_XML

    rss_base_url = 'https://www.ptt.cc/atom/gamesale.xml'
    
    # 先將 exclusion parameter 加入到 PTT URL，再進行 URL 編碼阻絕快取 (解決 400 Bad Request)
    target_url = f"{rss_base_url}?_={int(time.time())}"
    
    # 代理清單定義
    proxies = [
        {
            'name': '直接連線',
            'url': target_url,
            'parse': lambda data: data
        },
        {
            'name': 'CorsProxy.io 代理',
            'url': f'https://corsproxy.io/?url={urllib.parse.quote(target_url)}',
            'parse': lambda data: data
        },
        {
            'name': 'CodeTabs 代理',
            'url': f'https://api.codetabs.com/v1/proxy/?quest={urllib.parse.quote(target_url)}',
            'parse': lambda data: data
        },
        {
            'name': 'AllOrigins JSON 代理',
            'url': f'https://api.allorigins.win/get?url={urllib.parse.quote(target_url)}',
            'parse': lambda data: json.loads(data).get('contents', '')
        },
        {
            'name': 'AllOrigins Raw 代理',
            'url': f'https://api.allorigins.win/raw?url={urllib.parse.quote(target_url)}',
            'parse': lambda data: data
        },
        {
            'name': 'Corsfix 代理',
            'url': f'https://proxy.corsfix.com/?{urllib.parse.quote(target_url)}',
            'parse': lambda data: data
        }
    ]

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    for proxy in proxies:
        print(f"🔄 嘗試透過 [{proxy['name']}] 獲取 RSS...")
        try:
            req = urllib.request.Request(
                proxy['url'], 
                headers={'User-Agent': user_agent}
            )
            # 增加 timeout 到 25 秒給慢速代理緩衝
            with urllib.request.urlopen(req, timeout=25) as response:
                raw_data = response.read().decode('utf-8')
                parsed_xml = proxy['parse'](raw_data)
                if parsed_xml and '<feed' in parsed_xml:
                    print(f"✅ 成功透過 [{proxy['name']}] 取得 PTT RSS 資料！")
                    return parsed_xml
                else:
                    print(f"⚠️ [{proxy['name']}] 回傳的內容不是有效的 Atom Feed XML。")
        except Exception as e:
            print(f"❌ [{proxy['name']}] 失敗: {e}")
            
    # 若所有代理皆失敗且處於離線 Mock 測試模式，才回傳 Mock 資料；否則拋出例外讓工作流回報錯誤
    if use_mock:
        print("💡 代理皆失敗，已回傳 Mock 虛擬資料。")
        return MOCK_XML
    else:
        raise RuntimeError("❌ 所有連線代理與直連皆失敗，監控任務中止。")

def parse_xml_to_articles(xml_str):
    """解析 Atom XML 為文章列表"""
    try:
        # 去除命名空間前綴，方便使用 ElementTree 簡單解析
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        print(f"❌ XML 解析失敗: {e}")
        return []

    # Atom feed 命名空間處理
    ns = {'ns': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('ns:entry', ns)
    
    articles = []
    for entry in entries:
        title = entry.find('ns:title', ns)
        link_elem = entry.find('ns:link', ns)
        author = entry.find('ns:author/ns:name', ns)
        content = entry.find('ns:content', ns)
        published = entry.find('ns:published', ns)
        if published is None:
            published = entry.find('ns:updated', ns)
        
        title_text = title.text if title is not None else ""
        link_url = link_elem.attrib.get('href', '') if link_elem is not None else ""
        author_name = author.text if author is not None else "未知"
        content_text = content.text if content is not None else ""
        published_text = published.text if published is not None else ""

        articles.append({
            'id': link_url, # 使用連結 URL 作為去重 ID
            'title': title_text,
            'link': link_url,
            'author': author_name,
            'content': content_text,
            'published': published_text
        })
    return articles

def filter_articles(articles, keywords):
    """
    過濾邏輯：
    1. 必須含有 "售" (不分大小寫、全半寬)
    2. 且標題或內容含有關鍵字 (OR 關係)
    """
    filtered = []
    for art in articles:
        title_and_content = f"{art['title']} {art['content']}".lower()
        
        # 1. 必要條件："售"
        if "售" not in title_and_content:
            continue
            
        # 2. OR 關鍵字條件
        matched_kw = [kw for kw in keywords if kw.lower() in title_and_content]
        if matched_kw:
            filtered.append(art)
            print(f"🎯 匹配成功: {art['title']} (匹配關鍵字: {', '.join(matched_kw)})")
            
    return filtered

def send_line_notification(token, user_id, articles):
    """透過 LINE Messaging API 發送單一包裹推播訊息"""
    if not token or not user_id:
        print("⚠️ 未檢測到 LINE 信物環境變數 (LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID)。跳過 LINE 推播發送。")
        return False

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    # 重組精雅的推送字串
    message_lines = ["🔔 【PTT 關鍵字雷達新通知】", "發現符合條件的最新販售文章：\n"]
    for i, art in enumerate(articles, 1):
        message_lines.append(f"{i}. {art['title']}")
        message_lines.append(f"  👤 作者: {art['author']}")
        message_lines.append(f"  🔗 連結: {art['link']}\n")
    
    message_text = "\n".join(message_lines).strip()

    payload = {
        'to': user_id,
        'messages': [
            {
                'type': 'text',
                'text': message_text
            }
        ]
    }

    url = 'https://api.line.me/v2/bot/message/push'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            print("🚀 LINE 推播發送成功！")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ LINE 推播發送失敗! HTTP 狀態碼: {e.code}")
        print(f"❌ 回傳內容: {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"❌ LINE 推播發生未知錯誤: {e}")
        return False

def calculate_feed_velocity(articles):
    """計算並輸出 PTT 版塊發文流速統計"""
    if len(articles) < 2:
        return
        
    parsed_times = []
    for art in articles:
        date_str = art.get('published')
        if not date_str:
            continue
        try:
            parsed_times.append(datetime.fromisoformat(date_str))
        except Exception:
            try:
                parsed_times.append(datetime.strptime(date_str.split('+')[0], "%Y-%m-%dT%H:%M:%S"))
            except Exception:
                pass
                
    if len(parsed_times) < 2:
        return
        
    parsed_times.sort(reverse=True) # 從新到舊
    newest = parsed_times[0]
    oldest = parsed_times[-1]
    diff = newest - oldest
    total_minutes = diff.total_seconds() / 60
    count = len(parsed_times)
    avg_interval = total_minutes / (count - 1)
    
    # GitHub Action 預設定時定頻大約為 30 分鐘，用以評估安全性
    cron_interval = 30 
    
    print("\n================== 📊 PTT Gamesale 發文流速數據 ==================")
    print(f"🔹 目前 RSS 內包含文章數 : {count} 篇")
    print(f"🔹 最新文章發文時間     : {newest.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔹 最舊文章發文時間     : {oldest.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔹 20 篇文章的時間跨度  : {total_minutes:.1f} 分鐘 ({total_minutes/60:.2f} 小時)")
    print(f"🔹 平均發文速率         : 每一篇間隔 {avg_interval:.1f} 分鐘")
    
    if total_minutes > cron_interval:
        print(f"🟢 [安全] 塞滿 20 篇需要 {total_minutes:.1f} 分鐘，高於目前排程間隔 ({cron_interval} 分鐘)，現有排程安全不會漏文。")
    else:
        print(f"⚠️ [警告] 塞滿 20 篇僅花費 {total_minutes:.1f} 分鐘，已低於目前排程間隔 ({cron_interval} 分鐘)，高機率漏文，建議優化排程！")
    print("=================================================================\n")

def main():
    # 支援手動命令列參數 `--mock` 強制啟用 mock
    use_mock = '--mock' in sys.argv or os.environ.get('PTT_MOCK') == '1'

    # 1. 載入設定
    keywords = load_keywords()
    seen_posts = load_seen_posts()
    
    print(f"📋 載入關鍵字: {keywords}")
    print(f"📁 載入已通知文章數: {len(seen_posts)} 筆")

    # 2. 獲取 RSS 元資料
    xml_str = fetch_feed(use_mock=use_mock)

    # 3. 解析與過濾文章
    all_articles = parse_xml_to_articles(xml_str)
    print(f"🔍 總共解析出 {len(all_articles)} 篇貼文")
    
    # 📊 計算發文流速數據
    calculate_feed_velocity(all_articles)
    
    filtered_articles = filter_articles(all_articles, keywords)
    
    # 4. 去除已經發送過的文章
    new_articles = [art for art in filtered_articles if art['id'] not in seen_posts]
    print(f"📨 過濾去重後，剩餘 {len(new_articles)} 篇新文章需要發送通知")

    if not new_articles:
        print("😴 沒有任何新文章需要發送，監控任務結束。")
        return

    # 5. 發送 LINE 通報
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")
    
    success = send_line_notification(line_token, line_user_id, new_articles)
    
    # 6. 如果發送成功 (或是處於無 Token 純測試環境下)，更新去重檔案
    if success or (not line_token or not line_user_id):
        # 將新通知的文章加入已通知清單
        for art in new_articles:
            seen_posts.append(art['id'])
        save_seen_posts(seen_posts)
        print("💾 已更新去重狀態記錄檔 (seen_posts.json)")

if __name__ == '__main__':
    main()
