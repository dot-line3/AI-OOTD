# phase4_recommendation.py
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from google.genai import types

# 기존 구축 모듈 불러오기
from closet_db import ClosetDB, ClothingItem
from gemini_client import SafeGeminiClient
from weather_tpo import WeatherData, ScheduleTPO, ContextBuilder


# 1. Pydantic을 이용한 AI OOTD 추천 결과 출력 규격 정의
class OOTDRecommendationSchema(BaseModel):
    cot_reasoning: str = Field(description="1단계(날씨)~4단계(스타일 매칭)까지의 생각의 사슬(CoT) 추론 과정 요약")
    outer_id: Optional[str] = Field(default=None, description="선택된 아우터의 item_id (아우터가 불필요하거나 없으면 null)")
    top_id: str = Field(description="선택된 상의의 item_id")
    bottom_id: str = Field(description="선택된 하의의 item_id")
    shoes_id: Optional[str] = Field(default=None, description="선택된 신발의 item_id (없으면 null)")
    overall_style: str = Field(description="추천 코디의 종합 무드/스타일 (예: 비즈니스 캐주얼)")
    recommendation_reason: str = Field(description="해당 날씨와 TPO 상황에 이 코디를 추천하는 핵심 이유 (2~3문장)")
    styling_tips: str = Field(description="접어 입기, 레이어드, 핏 조절 등 추가 패션 팁")


# 2. AI OOTD 추천 엔진 클래스
class OOTDRecommender:
    def __init__(self, db: ClosetDB):
        self.db = db
        self.gemini_safe = SafeGeminiClient()

    def recommend(self, user_id: str, weather: WeatherData, tpo: ScheduleTPO) -> Optional[dict]:
        """
        사용자의 옷장 데이터 + 날씨 + TPO 컨텍스트를 조합하여 AI OOTD 코디를 추천
        """
        # 1. DB에서 현재 로그인한 사용자의 옷 목록 가져오기
        user_items = self.db.fetch_user_items(user_id)
        if not user_items:
            print(f"⚠️ 사용자({user_id})의 옷장에 등록된 옷이 없습니다.")
            return None

        # 2. 옷장 데이터를 Gemini에 넘겨줄 표준 JSON 리스트 형태로 변환
        closet_data = [item.to_dict() for item in user_items]

        # 3. 날씨 + TPO 융합 컨텍스트 생성
        context_str = ContextBuilder.build_recommendation_context(weather, tpo)

        # 4. System Instruction (페르소나, Grounding, CoT 규칙)
        system_instruction = """
너는 전문 AI OOTD 패션 스타일리스트이다.
제공된 [날씨/TPO 컨텍스트]와 [사용자 옷장 데이터]를 분석하여 최적의 착장을 추천하라.

[접지(Grounding) 제약 규칙]
1. 반드시 입력된 [사용자 옷장 데이터]에 있는 item_id만 선택해야 한다.
2. 옷장에 없는 의류나 소품은 절대로 추천하거나 언급하지 말 것.
3. 상의(top_id)와 하의(bottom_id)는 필수 요소이며, 아우터와 신발은 날씨/TPO 및 옷장 재고 상황에 맞춰 선택(없으면 null)한다.

[추론 단계 (Chain of Thought, CoT)]
답변을 생성하기 전 다음 4단계를 내부적으로 거쳐 cot_reasoning 항목에 명시할 것:
- 1단계 (날씨 평가): 기온 및 날씨에 따른 옷 두께, 아우터 필요성 파악
- 2단계 (TPO 평가): 방문 장소 및 일정 목적에 부합하는 무드/스타일 확정
- 3단계 (후보 스크리닝): 옷장에서 1, 2단계를 만족하는 카테고리별 item_id 추출
- 4단계 (조합 및 검증): 상/하의/아우터 간 색상 조화와 핏을 고려해 최종 룩 확정
"""

        # 5. User Prompt 구성
        user_prompt = f"""
### [환경 및 일정 컨텍스트]
{context_str}

### [사용자 옷장 데이터 (JSON)]
{json.dumps(closet_data, ensure_ascii=False, indent=2)}
"""

        # 6. Gemini 호출 설정
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=OOTDRecommendationSchema,
            temperature=0.2  # 일관성과 정확성을 위해 낮은 온도 사용
        )

        # 7. SafeGeminiClient를 이용해 503 방어 연동 호출
        response = self.gemini_safe.generate_content_with_retry(
            contents=user_prompt,
            config=config
        )

        # 8. Pydantic 결과 파싱 및 딕셔너리 반환
        result_schema = OOTDRecommendationSchema.model_validate_json(response.text)
        result_dict = result_schema.model_dump()

        # 8-1. DB 아이템 ID 매핑 테이블 생성 (공백 제거 방어 처리)
        id_to_item = {str(item.id).strip(): item for item in user_items}

        # 8-2. AI가 반환한 ID의 공백/Null 예외를 처리하는 안전 조회 함수
        def safe_get_item(item_id):
            if not item_id:
                return None
            return id_to_item.get(str(item_id).strip())

        # 8-3. 안전한 조회를 통해 딕셔너리에 매핑
        result_dict["outer_item"] = safe_get_item(result_dict.get("outer_id"))
        result_dict["top_item"] = safe_get_item(result_dict.get("top_id"))
        result_dict["bottom_item"] = safe_get_item(result_dict.get("bottom_id"))
        result_dict["shoes_item"] = safe_get_item(result_dict.get("shoes_id"))

        return result_dict


# 3. Phase 4 단독 실행 테스트부
if __name__ == "__main__":
    print("=== [Phase 4] AI OOTD 코디 추천 엔진 실행 테스트 ===")

    db = ClosetDB("closet.db")
    test_user = "developer_01"
    db.register_user(test_user, "testpass123")

    # 테스트를 위한 기본 샘플 옷 데이터 몇 개 등록 (없는 경우에만 저장)
    existing_items = db.fetch_user_items(test_user)
    if not existing_items:
        print("\n[!] 테스트용 옷장 데이터를 DB에 등록합니다...")
        db.insert_item(ClothingItem(
            id="top_101", user_id=test_user, name="화이트 옥스퍼드 셔츠",
            category="상의", sub_category="셔츠", color=["white"], season=["봄", "가을"],
            style=["비즈니스 캐주얼", "포멀"], description="깔끔한 화이트 드레스 셔츠"
        ))
        db.insert_item(ClothingItem(
            id="bottom_101", user_id=test_user, name="다크그레이 와이드 슬랙스",
            category="하의", sub_category="슬랙스", color=["gray"], season=["봄", "가을", "겨울"],
            style=["비즈니스 캐주얼", "모던"], description="찰랑거리는 핏의 슬랙스"
        ))
        db.insert_item(ClothingItem(
            id="outer_101", user_id=test_user, name="네이비 싱글 블레이저",
            category="아우터", sub_category="재킷", color=["navy"], season=["봄", "가을"],
            style=["비즈니스 캐주얼", "포멀"], description="단정한 네이비 재킷"
        ))

    # 테스트용 날씨 및 TPO 생성
    mock_weather = WeatherData(
        location_name="서울시 강남구",
        temperature_current=16.5,
        temperature_min=11.0,
        temperature_max=20.0,
        precipitation_probability=10,
        weather_condition="대체로 맑음",
        wind_speed=2.5
    )

    mock_tpo = ScheduleTPO(
        date="2026-05-20",
        location="테헤란로 공유오피스",
        occasion="중요 투자자 대상 사업 발표회(IR)",
        dress_code="신뢰감을 주는 비즈니스 캐주얼"
    )

    # 추천 엔진 실행
    recommender = OOTDRecommender(db)
    print("\n[1] Gemini AI 코디 추론 진행 중...")
    recommendation = recommender.recommend(test_user, mock_weather, mock_tpo)

    if recommendation:
        print("\n=== [2] AI OOTD 추천 결과 ===")
        print(f"📌 종합 무드: {recommendation.get('overall_style', '기본')}")
        
        print("\n[선택된 착장 조합]")
        
        # 각 아이템별로 None 체크 후 안전하게 출력
        outer = recommendation.get('outer_item')
        top = recommendation.get('top_item')
        bottom = recommendation.get('bottom_item')
        shoes = recommendation.get('shoes_item')

        if outer:
            print(f"- 아우터: [{outer.id}] {outer.name}")
        elif recommendation.get('outer_id'):
            print(f"- 아우터: [ID 미매칭: {recommendation.get('outer_id')}]")

        if top:
            print(f"- 상의: [{top.id}] {top.name}")
        else:
            print(f"- 상의: [ID 미매칭 또는 없음 (AI 추천 ID: {recommendation.get('top_id')})]")

        if bottom:
            print(f"- 하의: [{bottom.id}] {bottom.name}")
        else:
            print(f"- 하의: [ID 미매칭 또는 없음 (AI 추천 ID: {recommendation.get('bottom_id')})]")

        if shoes:
            print(f"- 신발: [{shoes.id}] {shoes.name}")
        elif recommendation.get('shoes_id'):
            print(f"- 신발: [ID 미매칭: {recommendation.get('shoes_id')}]")

        print(f"\n💡 추천 이유:\n{recommendation.get('recommendation_reason', '')}")
        print(f"\n✨ 스타일링 팁:\n{recommendation.get('styling_tips', '')}")
        print(f"\n🧠 추론 과정(CoT):\n{recommendation.get('cot_reasoning', '')}")