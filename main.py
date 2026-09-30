# -*- coding: utf-8 -*-
"""
매일 아침 6:40 (한국시간) 실행용 당일 증시 심층 분석 리포트
- Gemini API 리포트 생성 (429 Quota 자동 대기 및 모델 폴백)
- 텔레그램 메신저 자동 전송
"""

from datetime import datetime
import os
import re
import time
from google import genai
import pytz
import requests

# ============================================================
# 설정 (검증된 정식 모델명 구성 및 모델별 분리)
# ============================================================
CANDIDATE_MODELS = [
    "gemini-2.5-flash",  # 1순위: 가장 빠르고 안정적인 플래시 모델
    "gemini-2.5-pro",    # 2순위: 2.5 프로 모델
    "gemini-2.0-flash",  # 3순위: 2.0 플래시 백업
]

MAX_RETRIES_PER_MODEL = 2


def get_today_str() -> str:
  kst = pytz.timezone("Asia/Seoul")
  now = datetime.now(kst)
  weekdays = ["월", "화", "수", "목", "금", "토", "일"]
  return f"{now.year}년 {now.month}월 {now.day}일 ({weekdays[now.weekday()]})"


def build_prompt(today: str) -> str:
  return f"""
당신은 한국 증시 전문 애널리스트입니다.
아래 요구사항을 **정확히** 지켜서 오늘({today}) 기준의 당일 증시 심층 분석 글을 작성하세요.

반드시 지켜야 할 형식:

1. 글 시작 전 한국 시간 기준 당일 오늘 날짜를 넣어라.
2. 당일 증시 심층 분석.
3. 한국 오늘 새벽과 아침 미국 증시와 국내 경제·산업과 증권, 정치와 외교, 대통령 관련 뉴스 심층 정리.
4. 매크로 지표, FOMC 관련, 반도체 사이클, 유가 영향까지 포함.
5. 가장 중요한 테마와 대장주 가능성 종목군도 말해.
6. 정치 외교 산업 관련종목 코스피 코스닥 각각 10개 뜨거운 관심 받는 걸로 순환매매 가능종목 번호 넣어서 말해.
   - 코스피 종목 1부터 10 번호 순서 넣고 하트 ♡ 모양 넣어. 각 종목명 옆에 테마와 섹터 적어.
   - 코스닥 종목도 1부터 10 번호 넣고 ♡ 모양 넣어. 각 종목명 옆에 테마와 섹터 적어.
7. 방금 나온 앞 내용으로 당일 오전 매매 가능한 종목 영업이익과 유보율 좋은 종목으로 수혜를 받을 수 있는 종목으로 당일 섹터와 테마 뉴스 있는 것으로
   - 코스피로 20개 1등주와 2등주 추천 (추천시 1등주 종목명 테마와 섹터 / 2등주 종목명 테마와 섹터 넣어줘)
   - 그 다음은 코스닥으로 20개 1등주와 2등주 추천 (같은 형식)
8. 마지막에는 중요 표시로 종목 권유와 투자에 관한 책임은 투자자에게 있다는 경고 문구 꼭 포함.
9. 끝에 "출처 AI"라고 글 적어.

주의사항:
- 실제 존재하는 종목만 사용해라.
- 매일 내용이 달라지도록 최신 테마와 이슈를 반영해라.
- 형식은 위 요구사항을 한 글자도 빠뜨리지 말고 정확히 지켜라.
- 한국어로만 작성해라.
"""


def split_for_telegram(text: str, max_length: int = 4000) -> list[str]:
  """텔레그램 4096자 제한 대응을 위해 줄바꿈 기준으로 분할"""
  if len(text) <= max_length:
    return [text]

  chunks = []
  while text:
    if len(text) <= max_length:
      chunks.append(text)
      break

    split_pos = text.rfind("\n", 0, max_length)
    if split_pos == -1 or split_pos < max_length // 2:
      split_pos = max_length

    chunks.append(text[:split_pos].rstrip())
    text = text[split_pos:].lstrip()

  return chunks


def send_to_telegram(text: str) -> None:
  """텔레그램 메시지 전송"""
  bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
  chat_id = os.getenv("TELEGRAM_CHAT_ID")

  if not bot_token or not chat_id:
    print("텔레그램 전송 스킵: TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다.")
    return

  url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
  chunks = split_for_telegram(text, max_length=4000)

  for i, chunk in enumerate(chunks, 1):
    payload = {
        "chat_id": chat_id,
        "text": chunk,
    }

    try:
      response = requests.post(url, json=payload, timeout=15)
      if response.status_code != 200:
        print(f"텔레그램 전송 실패 ({i}/{len(chunks)}): 상태 코드 {response.status_code}, 응답: {response.text}")
      else:
        print(f"텔레그램 전송 성공 ({i}/{len(chunks)})")
      time.sleep(1)
    except Exception as e:
      print(f"텔레그램 전송 오류 발생 ({i}/{len(chunks)}): {e}")


def generate_report_with_llm() -> str:
  api_key = os.getenv("GEMINI_API_KEY")
  if not api_key:
    raise ValueError("GEMINI_API_KEY 환경변수가 없습니다.")

  client = genai.Client(api_key=api_key)
  today = get_today_str()
  prompt = build_prompt(today)

  last_error = None

  for model_name in CANDIDATE_MODELS:
    print(f"\n모델 시도 시작: {model_name}")

    for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
      try:
        print(f"  → 시도 {attempt}/{MAX_RETRIES_PER_MODEL}")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        print(f"성공! 사용 모델: {model_name}")
        return response.text

      except Exception as e:
        last_error = e
        error_str = str(e)

        if (
            "503" in error_str
            or "UNAVAILABLE" in error_str
            or "429" in error_str
            or "RESOURCE_EXHAUSTED" in error_str
            or "high demand" in error_str.lower()
        ):
          # API가 지시하는 대기 시간 파싱 (예: Please retry in 53s)
          retry_match = re.search(r"retryDelay':\s*'(\d+)s'", error_str) or re.search(r"retry in (\d+)", error_str)
          if retry_match:
            wait_time = int(retry_match.group(1)) + 2
          else:
            wait_time = 15 * attempt

          print(f"  일시적 한도/과부하 발생. {wait_time}초 대기 후 재시도...")
          time.sleep(wait_time)
        else:
          print(f"  실패 ({model_name}): {e}")
          break

    print(f"모델 {model_name} 실패. 다음 후보 모델로 이동합니다.")

  raise RuntimeError(f"모든 모델 시도 실패. 마지막 에러: {last_error}")


def main():
  print("리포트 생성 중... (Gemini API 호출)")
  report = generate_report_with_llm()

  print("\n" + "=" * 60)
  print(report)
  print("=" * 60)

  # 파일 저장
  kst = pytz.timezone("Asia/Seoul")
  today_file = datetime.now(kst).strftime("%Y%m%d")
  full_filename = f"report_{today_file}.txt"

  with open(full_filename, "w", encoding="utf-8") as f:
    f.write(report)
  print(f"\n전체 리포트 저장 완료: {full_filename}")

  # 텔레그램 전송
  print("\n텔레그램으로 전송 시작...")
  send_to_telegram(report)
  print("텔레그램 전송 작업 완료.")


if __name__ == "__main__":
  main()
