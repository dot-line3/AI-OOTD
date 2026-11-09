# phase2_vision_tagging.py
import os
import uuid
from typing import List, Union
from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google.genai import types

# 기존 DB 매니저 및 새로 생성한 안전한 Gemini 클라이언트 모듈 임포트
from closet_db import ClosetDB, ClothingItem
from gemini_client import SafeGeminiClient

load_dotenv()

def compress_image(image: Image.Image, max_size=(1024, 1024)) -> Image.Image:
    """이미지 해상도를 1024x1024 이하로 축소하여 API 전송 속도 향상"""
    img = image.copy()
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img

# 1. Pydantic 구조화된 스키마 정의
class ClothingTagSchema(BaseModel):
    name: str = Field(description="옷의 특징을 포함한 직관적인 이름")
    category: str = Field(description="카테고리: 상의, 하의, 아우터, 신발, 악세사리 중 하나")
    sub_category: str = Field(description="세부 분류 (예: 슬랙스, 후드티, 라이더 재킷 등)")
    color: List[str] = Field(description="주요 색상 리스트 (영어 소문자 단어)")
    season: List[str] = Field(description="착용 가능한 계절 리스트")
    style: List[str] = Field(description="어울리는 무드/스타일")
    description: str = Field(description="상세 설명 1~2문장")

# 2. 비전 태깅 및 DB 자동 등록 서비스 클래스
class ClothingAutoTagger:
    def __init__(self, db: ClosetDB):
        self.db = db
        # 503 과부하 방어 로직이 적용된 공통 Gemini 클라이언트 객체 사용
        self.gemini_safe = SafeGeminiClient()

    def analyze_and_register(
        self, 
        image_input: Union[str, Image.Image], 
        user_id: str
    ) -> ClothingItem:
        """
        이미지(파일 경로 또는 PIL.Image 객체)를 받아 압축 후 
        Gemini Vision 분석을 거쳐 지정된 유저의 DB에 자동 등록합니다.
        """
        # 3-1. 이미지 입력 타입 검증 및 PIL 객체 변환
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_input}")
            raw_image = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            raw_image = image_input
        else:
            raise ValueError("image_input은 파일 경로(str) 또는 PIL.Image 객체여야 합니다.")

        # 3-2. API 전송 전 이미지 압축 수행 (처리 속도 대폭 개선)
        compressed_img = compress_image(raw_image, max_size=(1024, 1024))

        # 3-3. 프롬프트 및 호출 설정 구성
        prompt = """
        이 이미지에 있는 의류/패션 아이템을 정밀 분석하여 지정된 JSON 스키마에 맞추어 태깅하세요.
        단일 아이템 위주로 분석하며, 명확하고 표준화된 한국어 용어를 사용하세요.
        """

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClothingTagSchema,
            temperature=0.1
        )

        # 3-4. 503 방어 백오프가 적용된 Gemini API 호출
        response = self.gemini_safe.generate_content_with_retry(
            contents=[compressed_img, prompt],
            config=config
        )

        # 3-5. JSON 구조 검증 및 데이터 객체 파싱
        parsed_data = ClothingTagSchema.model_validate_json(response.text)

        # 3-6. DB 저장용 ClothingItem Dataclass 인스턴스 생성
        clothing_item = ClothingItem(
            id=f"item_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            name=parsed_data.name,
            category=parsed_data.category,
            sub_category=parsed_data.sub_category,
            color=parsed_data.color,
            season=parsed_data.season,
            style=parsed_data.style,
            description=parsed_data.description
        )

        # 3-7. SQLite DB 저장
        if self.db.insert_item(clothing_item):
            return clothing_item
        else:
            raise Exception("DB 저장 처리에 실패했습니다.")


# 3. 단독 실행 테스트부
if __name__ == "__main__":
    print("=== [Vision Tagging Module] 단독 테스트 시작 ===")

    # DB 및 테스트 계정 세팅
    db = ClosetDB("closet.db")
    test_user = "developer_01"
    db.register_user(test_user, "testpass123")

    tagger = ClothingAutoTagger(db)
    test_image_path = "sample_jacket.jpg"

    if not os.path.exists(test_image_path):
        print(f"\n[!] 테스트를 위해 프로젝트 루트에 '{test_image_path}' 이미지를 놓아주세요.")
    else:
        print(f"\n[1] '{test_image_path}' 이미지 리사이징 및 AI 분석 시작...")
        registered_item = tagger.analyze_and_register(test_image_path, user_id=test_user)

        print("\n[2] 태깅 성공 및 DB 저장 완료!")
        print(f"- 아이템 ID: {registered_item.id}")
        print(f"- 소유자 ID: {registered_item.user_id}")
        print(f"- 이름: {registered_item.name}")
        print(f"- 카테고리: {registered_item.category} ({registered_item.sub_category})")
        print(f"- 색상: {registered_item.color}")
        print(f"- 계절: {registered_item.season}")
        print(f"- 스타일: {registered_item.style}")
        print(f"- 설명: {registered_item.description}")