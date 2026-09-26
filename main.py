# -*- coding: utf-8 -*-
"""
매일 아침 6:40 (한국시간) 실행용 당일 증시 심층 분석 리포트
LLM(Gemini)을 사용해 매일 새로운 내용 생성
"""

import os
from datetime import datetime
import pytz
import google.generativeai as genai

# ============================================================
# Gemini API 설정
# ============================================================
# GitHub Secrets에 GEMINI_API_KEY 등록 필요
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # 또는 gemini-1.5-pro


def get_today_str() -> str:
    """한국 시간 기준 오늘 날짜 문자열"""
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    return f"{now.year}년 {now.month}월 {now.day}일 ({weekdays[now.weekday()]})"


def build_prompt(today: str) -> str:
    """원본 요청 형식을 그대로 반영한 프롬프트"""
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


def generate_report_with_llm() -> str:
    """Gemini를 호출하여 리포트 생성"""
    today = get_today_str()
    prompt = build_prompt(today)

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 8192,
        }
    )
    return response.text


def main():
    print("리포트 생성 중... (Gemini API 호출)")
    report = generate_report_with_llm()

    # 콘솔 출력
    print(report)

    # 파일 저장
    kst = pytz.timezone("Asia/Seoul")
    today_file = datetime.now(kst).strftime("%Y%m%d")
    filename = f"report_{today_file}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n파일 저장 완료: {filename}")


if __name__ == "__main__":
    main()
