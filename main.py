# -*- coding: utf-8 -*-
"""
매일 아침 6:40 (한국시간) 실행용 당일 증시 심층 분석 리포트
- 최신 google-genai + gemini-3.8-flash
- 텔레그램 4096자 제한 대응 (자동 분할)
"""

import os
from datetime import datetime
import pytz
from google import genai
from google.genai import types


# --------------------------------------------------
# 사용 가능한 모델 우선순위 (최신 → 안정)
# --------------------------------------------------
CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]


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


def split_for_telegram(text: str, max_length: int = 4000) -> list[str]:
    """
    텔레그램 메시지 길이 제한(4096자)을 피하기 위해
    안전하게 분할하는 함수 (기본 4000자)
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # 최대한 max_length 근처에서 줄바꿈으로 자르기
        split_pos = text.rfind("\n", 0, max_length)
        if split_pos == -1 or split_pos < max_length // 2:
            split_pos = max_length

        chunks.append(text[:split_pos].rstrip())
        text = text[split_pos:].lstrip()

    return chunks


def generate_report_with_llm() -> str:
    """여러 모델을 순차적으로 시도하여 리포트 생성"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY 환경변수가 없습니다.\n"
            "GitHub → Settings → Secrets and variables → Actions에서\n"
            "Name: GEMINI_API_KEY 로 등록하세요."
        )

    client = genai.Client(api_key=api_key)
    today = get_today_str()
    prompt = build_prompt(today)

    last_error = None

    for model_name in CANDIDATE_MODELS:
        try:
            print(f"모델 시도 중: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            print(f"성공! 사용 모델: {model_name}")
            return response.text
        except Exception as e:
            print(f"실패 ({model_name}): {e}")
            last_error = e
            continue

    raise RuntimeError(f"모든 모델 시도 실패. 마지막 에러: {last_error}")


def main():
    print("리포트 생성 중... (Gemini API 호출)")
    report = generate_report_with_llm()

    # 전체 리포트 출력
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # 파일 저장 (전체)
    kst = pytz.timezone("Asia/Seoul")
    today_file = datetime.now(kst).strftime("%Y%m%d")
    full_filename = f"report_{today_file}.txt"

    with open(full_filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n전체 리포트 저장 완료: {full_filename}")

    # 텔레그램용 분할
    chunks = split_for_telegram(report, max_length=4000)
    print(f"텔레그램용 메시지 분할 개수: {len(chunks)}개")

    for i, chunk in enumerate(chunks, 1):
        chunk_filename = f"report_{today_file}_part{i}.txt"
        with open(chunk_filename, "w", encoding="utf-8") as f:
            f.write(chunk)
        print(f"  → {chunk_filename} 저장 (길이: {len(chunk)}자)")

    print("\n모든 작업 완료.")


if __name__ == "__main__":
    main()
