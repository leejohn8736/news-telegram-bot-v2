import os
import sys
import json
import time
import html
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# 1. Secrets에서 텔레그램 정보 가져오기
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 2. 순환 감시할 키워드 목록
KEYWORDS = [
    "삼성전자",
    "AI",
    "반도체",
    "증권",
    "부동산",
    "금리",
    "주식",
    "현대차",
    "SK하이닉스",
    "배터리"
]

SENT_LINKS_FILE = "sent_links.txt"
LAST_INDEX_FILE = "last_keyword_index.txt"  # 마지막 감시 키워드 순번 저장 파일

def load_sent_links():
    if os.path.exists(SENT_LINKS_FILE):
        with open(SENT_LINKS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_sent_links(sent_links):
    with open(SENT_LINKS_FILE, "w", encoding="utf-8") as f:
        for link in sent_links:
            f.write(f"{link}\n")

def load_last_index():
    """마지막으로 검사했던 키워드 인덱스 불러오기"""
    if os.path.exists(LAST_INDEX_FILE):
        try:
            with open(LAST_INDEX_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except ValueError:
            return -1
    return -1

def save_last_index(index):
    """검사 완료한 키워드 인덱스 저장하기"""
    with open(LAST_INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(str(index))

def send_telegram_msg(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 설정값이 없습니다.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return True
    except Exception as e:
        print(f"❌ 텔레그램 발송 오류: {e}")
        return False

def fetch_rss_news(keyword):
    """발행된 지 5분 이내의 뉴스만 골라내는 크롤러"""
    encoded_keyword = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
    articles = []
    
    # 현재 한국 시간(KST) 구하기
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read().decode('utf-8')
            items = xml_data.split('<item>')
            
            for item in items[1:]:
                pub_date_str = ""
                if '<pubDate>' in item and '</pubDate>' in item:
                    pub_date_str = item.split('<pubDate>')[1].split('</pubDate>')[0].strip()
                
                is_within_5_min = False
                pub_formatted = ""
                
                if pub_date_str:
                    try:
                        # 기사 발행 시간을 KST로 변환
                        dt = parsedate_to_datetime(pub_date_str).astimezone(kst)
                        pub_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # (현재 시간 - 기사 발행 시간) 계산 (초 단위)
                        time_diff_seconds = (now_kst - dt).total_seconds()
                        
                        # 발행된 지 0초 이상 300초(5분) 이내인 기사만 필터링
                        if 0 <= time_diff_seconds <= 300:
                            is_within_5_min = True
                    except Exception:
                        pass
                
                # 5분이 넘었거나 시간 계산이 안 된 기사는 제외
                if not is_within_5_min:
                    continue

                title = ""
                if '<title>' in item and '</title>' in item:
                    title = item.split('<title>')[1].split('</title>')[0]
                    title = title.replace('<![CDATA[', '').replace(']]>', '').strip()
                
                link = ""
                if '<link>' in item and '</link>' in item:
                    link = item.split('<link>')[1].split('</link>')[0].strip()
                
                source = "언론사 미상"
                if '<source' in item and '</source>' in item:
                    source = item.split('>')[1].split('</source>')[0].strip()

                if keyword in title and link:
                    articles.append({
                        'keyword': keyword,
                        'title': title,
                        'link': link,
                        'source': source,
                        'pub_time': pub_formatted
                    })
    except Exception as e:
        print(f"❌ [{keyword}] 뉴스 수집 실패: {e}")
        
    return articles

def main():
    print("🚀 5분 실시간 뉴스 감시 로봇 실행...")
    sent_links = load_sent_links()
    last_index = load_last_index()
    total_keywords = len(KEYWORDS)
    
    # 발송 여부와 관계없이 매 실행(5분)마다 다음 키워드로 순환 이동
    target_index = (last_index + 1) % total_keywords
    keyword = KEYWORDS[target_index]
    
    print(f"🔍 이번 타겟 키워드: [{keyword}] (인덱스: {target_index})")
    
    # 현재 키워드로 5분 이내 뉴스 조회
    articles = fetch_rss_news(keyword)
    sent_in_this_run = False
    
    for article in articles:
        link = article['link']
        if link in sent_links:
            continue
        
        safe_keyword = html.escape(article['keyword'])
        safe_title = html.escape(article['title'])
        safe_source = html.escape(article['source'])
        safe_pub_time = html.escape(article['pub_time'])
        
        # 텔레그램 메시지 헤더 (5분 이내 및 키워드 명시)
        message = (
            f"🚨 <b>[5분 이내 실시간 뉴스 - {safe_keyword}]</b>\n\n"
            f"<b>제목:</b> {safe_title}\n"
            f"<b>출처:</b> {safe_source}\n"
            f"<b>발행 시간:</b> {safe_pub_time}\n\n"
            f"🔗 <a href='{link}'>기사 읽기</a>"
        )
        
        if send_telegram_msg(message):
            sent_links.add(link)
            save_sent_links(sent_links)
            print(f"✅ [{keyword}] 5분 이내 뉴스 발송 성공: {article['title']}")
            sent_in_this_run = True
            break
            
    if not sent_in_this_run:
        print(f"ℹ️ [{keyword}] 최근 5분 이내 신규 뉴스가 없습니다. 5분 후 다음 키워드로 자동 전환됩니다.")
    
    # 기사 탐색/발송 유무와 무관하게 이번에 검사한 키워드 위치를 저장하여 다음 5분 뒤 실행 시 무조건 다음 키워드를 검사함
    save_last_index(target_index)

if __name__ == "__main__":
    main()
