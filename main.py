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

# 2. 감시할 전체 키워드 목록
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

def load_sent_links():
    """이미 발송된 기사 링크 목록 불러오기"""
    if os.path.exists(SENT_LINKS_FILE):
        with open(SENT_LINKS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_sent_links(sent_links):
    """발송된 기사 링크 목록 저장하기"""
    with open(SENT_LINKS_FILE, "w", encoding="utf-8") as f:
        for link in sent_links:
            f.write(f"{link}\n")

def send_telegram_msg(text):
    """텔레그램 메시지 전송 함수"""
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
    """발행된 지 15분 이내(900초)의 뉴스만 골라내는 크롤러"""
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
                
                is_within_15_min = False
                pub_formatted = ""
                
                if pub_date_str:
                    try:
                        # 기사 발행 시간을 KST로 변환
                        dt = parsedate_to_datetime(pub_date_str).astimezone(kst)
                        pub_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # (현재 시간 - 기사 발행 시간) 계산 (초 단위)
                        time_diff_seconds = (now_kst - dt).total_seconds()
                        
                        # 발행된 지 0초 이상 900초(15분) 이내인 기사만 필터링
                        if 0 <= time_diff_seconds <= 900:
                            is_within_15_min = True
                    except Exception:
                        pass
                
                # 15분이 넘었거나 시간 계산이 안 된 기사는 제외
                if not is_within_15_min:
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
    print("🚀 실시간 뉴스 고속 감시 로봇 실행 (전체 키워드 일괄 검사)...")
    sent_links = load_sent_links()
    total_sent_count = 0
    
    # 매 실행마다 10개 키워드 전체를 순차적으로 모두 검사
    for keyword in KEYWORDS:
        print(f"🔍 키워드 감시 중: [{keyword}]")
        articles = fetch_rss_news(keyword)
        
        for article in articles:
            link = article['link']
            # 중복 발송 방지
            if link in sent_links:
                continue
            
            safe_keyword = html.escape(article['keyword'])
            safe_title = html.escape(article['title'])
            safe_source = html.escape(article['source'])
            safe_pub_time = html.escape(article['pub_time'])
            
            # 요청된 텔레그램 메시지 헤더 포맷 적용
            message = (
                f"🚨 <b>[실시간 신규 뉴스 발송 - {safe_keyword}]</b>\n\n"
                f"<b>제목:</b> {safe_title}\n"
                f"<b>출처:</b> {safe_source}\n"
                f"<b>발행 시간:</b> {safe_pub_time}\n\n"
                f"🔗 <a href='{link}'>기사 읽기</a>"
            )
            
            if send_telegram_msg(message):
                sent_links.add(link)
                save_sent_links(sent_links)
                print(f"✅ [{keyword}] 최신 뉴스 발송 성공: {article['title']}")
                total_sent_count += 1
                # 텔레그램 연속 발송 제한 방지를 위한 짧은 대기 (0.5초)
                time.sleep(0.5)

    if total_sent_count == 0:
        print("ℹ️ 이번 스케줄에서는 모든 키워드에 대해 최근 15분 이내 신규 뉴스가 없습니다.")
    else:
        print(f"🎉 총 {total_sent_count}건의 신규 뉴스를 성공적으로 발송했습니다.")

if __name__ == "__main__":
    main()
