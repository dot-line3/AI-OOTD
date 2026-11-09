# benchmark_test.py
import os
import io
import time
from PIL import Image

# 기존 구현 모듈 임포트
from closet_db import ClosetDB, ClothingItem
from vision_tagging import compress_image, ClothingAutoTagger
from weather_tpo import WeatherData, ScheduleTPO
from recommendation import OOTDRecommender


# 추천 검증용 고정 테스트 옷장 (상의 4 / 하의 3 / 아우터 3 / 신발 3)
FIXED_CLOSET = [
    dict(id="bm_top_01", name="화이트 옥스퍼드 셔츠", category="상의", sub_category="셔츠", color=["white"], season=["봄", "가을"], style=["비즈니스 캐주얼", "포멀"], description="깔끔한 화이트 셔츠"),
    dict(id="bm_top_02", name="네이비 반팔 티셔츠", category="상의", sub_category="티셔츠", color=["navy"], season=["여름"], style=["캐주얼"], description="면 소재 기본 반팔"),
    dict(id="bm_top_03", name="그레이 울 니트", category="상의", sub_category="니트", color=["gray"], season=["가을", "겨울"], style=["모던", "캐주얼"], description="두께감 있는 울 니트"),
    dict(id="bm_top_04", name="블랙 터틀넥", category="상의", sub_category="터틀넥", color=["black"], season=["겨울"], style=["모던", "포멀"], description="얇은 히트텍 소재 터틀넥"),
    dict(id="bm_bottom_01", name="차콜 슬랙스", category="하의", sub_category="슬랙스", color=["charcoal"], season=["봄", "가을", "겨울"], style=["비즈니스 캐주얼", "포멀"], description="정장핏 슬랙스"),
    dict(id="bm_bottom_02", name="베이지 치노 쇼츠", category="하의", sub_category="반바지", color=["beige"], season=["여름"], style=["캐주얼"], description="무릎 위 기장 반바지"),
    dict(id="bm_bottom_03", name="인디고 데님 팬츠", category="하의", sub_category="청바지", color=["indigo"], season=["봄", "가을", "겨울"], style=["캐주얼"], description="스트레이트핏 청바지"),
    dict(id="bm_outer_01", name="네이비 싱글 블레이저", category="아우터", sub_category="블레이저", color=["navy"], season=["봄", "가을"], style=["비즈니스 캐주얼", "포멀"], description="단정한 블레이저"),
    dict(id="bm_outer_02", name="블랙 롱 패딩", category="아우터", sub_category="패딩", color=["black"], season=["겨울"], style=["캐주얼"], description="무릎 기장 구스 패딩"),
    dict(id="bm_outer_03", name="베이지 트렌치코트", category="아우터", sub_category="코트", color=["beige"], season=["봄", "가을"], style=["모던", "포멀"], description="방수 코팅 트렌치코트"),
    dict(id="bm_shoes_01", name="블랙 더비 슈즈", category="신발", sub_category="구두", color=["black"], season=["봄", "가을", "겨울"], style=["포멀"], description="가죽 더비 슈즈"),
    dict(id="bm_shoes_02", name="화이트 스니커즈", category="신발", sub_category="스니커즈", color=["white"], season=["봄", "여름", "가을"], style=["캐주얼"], description="기본 화이트 스니커즈"),
    dict(id="bm_shoes_03", name="브라운 레인부츠", category="신발", sub_category="부츠", color=["brown"], season=["가을", "겨울"], style=["캐주얼"], description="방수 고무 부츠"),
]


class OOTDBenchmarkTester:
    def __init__(self, db_path: str = "closet.db", user_id: str = "benchmark_user"):
        self.db = ClosetDB(db_path)
        self.user_id = user_id
        self.db.register_user(self.user_id, "testpass123")
        
        self.tagger = ClothingAutoTagger(self.db)
        self.recommender = OOTDRecommender(self.db)

    def test_image_compression(self, image_path: str) -> dict:
        """1. 이미지 압축 처리 속도 및 용량 감축률 측정"""
        if not os.path.exists(image_path):
            return {"error": f"파일 없음: {image_path}"}

        # 원본 파일 크기 측정
        original_size_bytes = os.path.getsize(image_path)
        original_size_kb = original_size_bytes / 1024

        # 리사이징 및 압축 수행 시간 측정
        start_time = time.perf_counter()
        raw_img = Image.open(image_path)
        compressed_img = compress_image(raw_img, max_size=(1024, 1024))
        
        # 메모리(BytesIO) 상의 압축 파일 크기 측정
        buffer = io.BytesIO()
        compressed_img.save(buffer, format="JPEG", quality=85)
        compressed_size_bytes = buffer.tell()
        compressed_size_kb = compressed_size_bytes / 1024
        
        elapsed_time_sec = time.perf_counter() - start_time

        reduction_rate = ((original_size_bytes - compressed_size_bytes) / original_size_bytes) * 100

        return {
            "original_size_kb": round(original_size_kb, 2),
            "compressed_size_kb": round(compressed_size_kb, 2),
            "reduction_rate": round(reduction_rate, 2),
            "compression_time_sec": round(elapsed_time_sec, 4)
        }

    def test_vision_tagging_performance(self, image_path: str) -> dict:
        """2. 비전 태깅 API 응답 속도 및 데이터 저장 검증"""
        start_time = time.perf_counter()
        
        try:
            item = self.tagger.analyze_and_register(image_path, user_id=self.user_id)
            elapsed_time_sec = time.perf_counter() - start_time
            return {
                "success": True,
                "latency_sec": round(elapsed_time_sec, 2),
                "item_id": item.id,
                "item_name": item.name
            }
        except Exception as e:
            elapsed_time_sec = time.perf_counter() - start_time
            return {
                "success": False,
                "latency_sec": round(elapsed_time_sec, 2),
                "error": str(e)
            }

    def seed_fixed_closet(self, user_id: str = "benchmark_closet") -> list:
        """추천 검증용 고정 테스트 옷장 (상의/하의/아우터/신발 고루 구성, 실행마다 동일)"""
        self.db.register_user(user_id, "testpass123")
        existing = {item.id for item in self.db.fetch_user_items(user_id)}
        for item in FIXED_CLOSET:
            if item["id"] not in existing:
                self.db.insert_item(ClothingItem(user_id=user_id, **item))
        return self.db.fetch_user_items(user_id)

    def test_recommendation_performance(self, scenarios: list, closet_user: str = "benchmark_closet", runs_per_scenario: int = 2) -> dict:
        """
        3. OOTD 추천 Latency 및 Grounding 검증
        - ID 유효성: 반환된 item_id가 실제 옷장에 존재하는가 (환각 여부)
        - 카테고리 일치: top_id는 상의, bottom_id는 하의 등 슬롯에 맞는 옷을 골랐는가
        """
        user_items = self.seed_fixed_closet(closet_user)
        id_to_category = {item.id: item.category for item in user_items}
        slot_category = {"outer_id": "아우터", "top_id": "상의", "bottom_id": "하의", "shoes_id": "신발"}

        latencies = []
        total_runs = 0
        failed_runs = 0
        passed_runs = 0             # 모든 ID 유효 + 모든 카테고리 일치
        total_ids = 0
        invalid_ids = 0             # 옷장에 없는 ID (환각)
        category_mismatches = 0     # 존재하지만 슬롯과 카테고리가 다른 ID

        for s_idx, (weather, tpo) in enumerate(scenarios, 1):
            for r in range(1, runs_per_scenario + 1):
                total_runs += 1
                start_time = time.perf_counter()
                try:
                    result = self.recommender.recommend(closet_user, weather, tpo)
                except Exception as e:
                    print(f"   [S{s_idx}-{r}] 호출 실패: {e}")
                    failed_runs += 1
                    continue
                elapsed = time.perf_counter() - start_time
                if not result:
                    failed_runs += 1
                    continue
                latencies.append(elapsed)

                run_invalid, run_mismatch = 0, 0
                for slot, expected in slot_category.items():
                    item_id = (result.get(slot) or "").strip()
                    if not item_id:
                        continue
                    total_ids += 1
                    if item_id not in id_to_category:
                        run_invalid += 1
                    elif id_to_category[item_id] != expected:
                        run_mismatch += 1
                invalid_ids += run_invalid
                category_mismatches += run_mismatch
                if run_invalid == 0 and run_mismatch == 0:
                    passed_runs += 1
                print(f"   [S{s_idx}-{r}] {elapsed:.2f}초 | 무효 ID {run_invalid} | 카테고리 불일치 {run_mismatch} | {result.get('overall_style', '')}")

        completed = total_runs - failed_runs
        if completed == 0:
            return {"success": False, "error": "추천 결과를 한 번도 생성하지 못함"}

        return {
            "success": True,
            "total_runs": total_runs,
            "completed_runs": completed,
            "scenario_count": len(scenarios),
            "closet_size": len(user_items),
            "avg_latency_sec": round(sum(latencies) / len(latencies), 2),
            "max_latency_sec": round(max(latencies), 2),
            "pass_rate": round(passed_runs / completed * 100, 1),
            "total_ids": total_ids,
            "invalid_ids": invalid_ids,
            "category_mismatches": category_mismatches,
            "hallucination_rate": round(invalid_ids / total_ids * 100, 1) if total_ids else 0.0,
            "category_accuracy": round((total_ids - invalid_ids - category_mismatches) / total_ids * 100, 1) if total_ids else 0.0,
        }


# =====================================================================
# 실행 및 결과 리포트 출력부
# =====================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("🚀 [AI OOTD Application] 핵심 성과 측정(Benchmark Test) 시작")
    print("=" * 65)

    tester = OOTDBenchmarkTester()

    # 샘플 이미지 테스트 (루트 폴더 내 테스트 이미지 지정)
    sample_img = "sample_jacket.jpg"

    if not os.path.exists(sample_img):
        print(f"\n⚠️ 테스트를 위해 프로젝트 폴더에 '{sample_img}' 파일을 넣어주세요.")
    else:
        # 1. 이미지 압축 성능 측정
        print("\n[📊 Test 1. 이미지 압축 전처리 성능 측정]")
        comp_res = tester.test_image_compression(sample_img)
        print(f" - 원본 이미지 용량:  {comp_res['original_size_kb']} KB")
        print(f" - 압축 후 이미지 용량: {comp_res['compressed_size_kb']} KB")
        print(f" - 용량 감축률:        {comp_res['reduction_rate']} % 감축 달성")
        print(f" - 소요 시간:          {comp_res['compression_time_sec']} 초")

        # 2. 비전 분석 Latency 측정
        print("\n[📊 Test 2. Gemini Vision 자동 태깅 속도 측정]")
        tag_res = tester.test_vision_tagging_performance(sample_img)
        if tag_res["success"]:
            print(f" - 태깅 성공 여부: SUCCESS")
            print(f" - 응답 Latency:  {tag_res['latency_sec']} 초")
            print(f" - 등록된 아이템:  [{tag_res['item_id']}] {tag_res['item_name']}")
        else:
            print(f" - 태깅 실패: {tag_res['error']}")

    # 3. 추천 엔진 Latency & Grounding 검증 (고정 테스트 옷장 + 5개 날씨/TPO 시나리오 x 2회)
    print("\n[📊 Test 3. OOTD 코디 추천 엔진 & 데이터 Grounding 검증]")

    def W(name, cur, lo, hi, rain, cond, wind):
        return WeatherData(location_name=name, temperature_current=cur, temperature_min=lo, temperature_max=hi,
                           precipitation_probability=rain, weather_condition=cond, wind_speed=wind)

    scenarios = [
        (W("서울시 강남구", 17.0, 12.0, 21.0, 0, "맑음", 1.5),
         ScheduleTPO("2026-05-20", "강남역 컨퍼런스룸", "IT 기술 세미나 발표", "비즈니스 캐주얼")),
        (W("서울시 마포구", 31.0, 25.0, 33.0, 10, "맑음", 2.0),
         ScheduleTPO("2026-08-05", "한강공원", "친구들과 피크닉", "편안한 캐주얼")),
        (W("서울시 종로구", -3.0, -7.0, 1.0, 20, "흐림", 4.5),
         ScheduleTPO("2026-01-15", "광화문 오피스", "출근 및 팀 회의", "단정한 오피스룩")),
        (W("서울시 성동구", 12.0, 9.0, 14.0, 80, "보통 비", 5.0),
         ScheduleTPO("2026-10-10", "성수동 카페", "주말 카페 데이트", "깔끔한 데이트룩")),
        (W("서울시 서초구", 22.0, 16.0, 24.0, 0, "구름 조금", 1.0),
         ScheduleTPO("2026-06-13", "야외 웨딩홀", "지인 결혼식 하객", "포멀 하객룩")),
    ]

    rec_res = tester.test_recommendation_performance(scenarios, runs_per_scenario=2)
    if rec_res["success"]:
        print(f" - 측정 조건:            고정 옷장 {rec_res['closet_size']}벌 · 시나리오 {rec_res['scenario_count']}개 · 총 {rec_res['total_runs']}회 ({rec_res['completed_runs']}회 성공)")
        print(f" - 평균 추론 Latency:     {rec_res['avg_latency_sec']} 초 (최대 {rec_res['max_latency_sec']} 초)")
        print(f" - 완전 통과율:          {rec_res['pass_rate']} % (모든 ID 실재 + 카테고리 일치한 회차 비율)")
        print(f" - ID 환각률:            {rec_res['hallucination_rate']} % ({rec_res['invalid_ids']}/{rec_res['total_ids']}개 옷장에 없음)")
        print(f" - 카테고리 정확도:       {rec_res['category_accuracy']} % (불일치 {rec_res['category_mismatches']}개)")
    else:
        print(f" - 추천 처리 실패: {rec_res['error']}")

    print("\n" + "=" * 65)
    print("🎉 벤치마크 테스트 완료! 위 수치를 포트폴리오 문서에 기록하세요.")
    print("=" * 65)