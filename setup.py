import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from dotenv import load_dotenv
from google import genai

# 1. 환경변수(.env) 읽어오기
load_dotenv()

# 2. 옷장 데이터 구조 정의 (Data Schema)
@dataclass
class ClothingItem:
    id: str
    name: str
    category: str
    sub_category: str
    color: List[str]
    season: List[str]
    style: List[str]
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Dataclass 객체를 JSON 저장용 딕셔너리로 변환"""
        return asdict(self)


# 3. Gemini API 클라이언트 초기화 및 연결 테스트 클래스
class GeminiService:
    def __init__(self):
        # 환경변수에서 API 키 추출
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError(".env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
        
        # Google GenAI 클라이언트 생성
        self.client = genai.Client(api_key=self.api_key)
        # 추천 및 빠른 텍스트 처리에 적합한 기본 모델 설정
        self.model_name = "gemini-3.6-flash"

    def test_connection(self) -> str:
        """API 연동 및 기본 텍스트 응답 테스트"""
        try:
            prompt = "안녕하세요! AI OOTD 추천 서비스 아키텍처 연결 테스트입니다. 짧게 1줄로 응답해주세요."
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"API 연결 실패: {str(e)}"


# 4. Phase 1 검증 실행부
if __name__ == "__main__":
    print("=== [Phase 1] 데이터 구조 설계 및 API 연결 검증 ===")
    
    # 4-1. 데이터 구조 객체 생성 테스트
    sample_item = ClothingItem(
        id="item_001",
        name="크림색 와이드 슬랙스",
        category="하의",
        sub_category="슬랙스",
        color=["cream", "beige"],
        season=["봄", "여름", "가을"],
        style=["모던", "비즈니스 캐주얼"],
        description="찰랑거리는 소재의 밴딩 와이드 슬랙스"
    )
    
    print("\n[1] 데이터 구조 생성 성공:")
    print(sample_item.to_dict())
    
    # 4-2. Gemini API 연결 테스트
    print("\n[2] Gemini API 연결 테스트 중...")
    gemini = GeminiService()
    result = gemini.test_connection()
    
    print("\n[3] Gemini API 응답 결과:")
    print(result)