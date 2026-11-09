# 👗 Personal AI OOTD Stylist

사용자의 디지털 옷장, 방문 날짜의 날씨 예보, 일정·장소·드레스코드(TPO)를 함께 분석해 **실제로 가진 옷만으로** 코디를 추천하는 Streamlit 기반 멀티모달 AI 서비스입니다.

## ✨ 주요 기능
- **옷 사진 자동 태깅**: Gemini Vision + Pydantic 스키마로 카테고리·색상·계절·스타일 추출 후 DB 저장
- **이미지 전처리**: API 전송 전 1024px 이내로 비율 유지 축소 (Pillow)
- **날씨·TPO 기반 추천**: Open-Meteo로 선택한 날짜(최대 15일 후)의 예보를 받아 4단계 추론(CoT) 프롬프트로 코디 생성. API 실패 시 기본값임을 화면과 AI에 명시
- **환각 방지 (Grounding)**: 추천 결과의 item_id가 실제 옷장에 있는지 검증
- **계정 보안**: PBKDF2-SHA256(랜덤 솔트, 10만 회) 비밀번호 해싱, 모든 쿼리에 user_id 조건 적용
- **안정성**: 503 과부하 시 지터를 더한 재시도 + 3단계 모델 우회 체인 (`gemini-3.5-flash-lite → gemini-3.1-flash-lite → gemini-2.5-flash`)

## 📊 벤치마크 결과 (2026-11-09 측정, `benchmark_test.py`)

| 지표 | 결과 |
|---|---|
| 이미지 용량 | 475.1 KB → 176.07 KB (**62.9% 감축**, 전처리 0.1초, JPEG 저장 기준) |
| 옷 자동 태깅 응답 | 3.36초 |
| 코디 추천 응답 | 평균 **2.21초** (최대 2.62초) |
| 추천 ID 환각률 | **0%** (38개 ID 중 무효 0) |
| 카테고리 정확도 | **100%** (상의 칸에 상의, 하의 칸에 하의 등) |

측정 조건: 고정 테스트 옷장 13벌(상의 4·하의 3·아우터 3·신발 3), 날씨·TPO 시나리오 5개 × 2회

## 🔧 개발 중 해결한 문제
- **무의미한 접지 검증**: 테스트 옷장에 아우터만 있어 재킷이 상의 칸에 들어가도 통과하던 문제 → 고정 테스트 옷장과 카테고리 일치 검사 추가
- **옷 삭제 버튼 오류**: 존재하지 않는 `delete_item()` 호출 → 본인 소유 아이템만 삭제하는 메서드 구현
- **날짜 미반영**: 방문 날짜를 골라도 항상 오늘 날씨를 쓰던 문제 → 선택 날짜 예보 조회

## 🚀 실행 방법

```bash
python -m venv ootd-venv
ootd-venv\Scripts\activate        # macOS/Linux: source ootd-venv/bin/activate
pip install -r requirements.txt
```

`.env` 파일 생성:
```
GEMINI_API_KEY=your_gemini_api_key
```

```bash
streamlit run app.py         # 앱 실행
python benchmark_test.py     # 성능 측정 (Gemini 약 11회 호출)
```

## ⚠️ 알려진 한계
- 15일 이후 날짜는 예보가 없어 기본값 사용
- SQLite 로컬 DB 구조 (다중 서버 확장 시 PostgreSQL 등으로 전환 필요)
