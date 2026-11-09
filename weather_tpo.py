# phase3_weather_tpo.py
import datetime
import requests
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

FORECAST_MAX_DAYS = 15  # Open-Meteo 무료 예보 제공 범위 (오늘 ~ 15일 후)

# 1. WMO(세계기상기구) 날씨 해석 코드 - 한국어 매핑 테이블
WMO_WEATHER_CODES: Dict[int, str] = {
    0: "맑음",
    1: "대체로 맑음",
    2: "구름 조금",
    3: "흐림",
    45: "안개",
    48: "짙은 안개",
    51: "약한 이슬비",
    53: "보통 이슬비",
    55: "강한 이슬비",
    56: "약한 어는 이슬비",
    57: "강한 어는 이슬비",
    61: "약한 비",
    63: "보통 비",
    65: "강한 비",
    66: "약한 어는 비",
    67: "강한 어는 비",
    71: "약한 눈",
    73: "보통 눈",
    75: "강한 눈",
    77: "싸락눈",
    80: "약한 소나기",
    81: "보통 소나기",
    82: "강한 소나기",
    85: "약한 소낙눈",
    86: "강한 소낙눈",
    95: "뇌우",
    96: "약한 우박을 동반한 뇌우",
    99: "강한 우박을 동반한 뇌우"
}


# 2. 날씨 데이터 규격 정의
@dataclass
class WeatherData:
    location_name: str
    temperature_current: float
    temperature_min: float
    temperature_max: float
    precipitation_probability: int
    weather_condition: str
    wind_speed: float
    forecast_date: str = ""     # 예보 기준 날짜 (YYYY-MM-DD)
    is_fallback: bool = False   # True면 실제 예보가 아닌 기본값 (API 실패 또는 예보 범위 밖)
    notice: str = ""            # 사용자/AI에게 알릴 안내 문구

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 3. TPO(Time, Place, Occasion) 데이터 규격 정의
@dataclass
class ScheduleTPO:
    date: str                  # 날짜 (예: 2026-05-15)
    location: str              # 방문 장소 (예: 서울 강남, 제주도 야외)
    occasion: str              # 일정/목적 (예: 결혼식 하객, 카페 카공, 비즈니스 미팅)
    dress_code: Optional[str] = "자유" # 드레스코드/선호 스타일 (예: 깔끔함, 포멀, 편안함)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 4. Open-Meteo 기반 날씨 연동 서비스
class WeatherService:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    @staticmethod
    def _fallback(location_name: str, target_date: datetime.date, notice: str) -> WeatherData:
        """API 실패/예보 범위 밖일 때 앱 중단을 막는 기본값 (is_fallback=True로 명시)"""
        print(f"⚠️ {notice}")
        return WeatherData(
            location_name=location_name,
            temperature_current=18.0,
            temperature_min=14.0,
            temperature_max=22.0,
            precipitation_probability=0,
            weather_condition="정보 없음",
            wind_speed=2.0,
            forecast_date=target_date.isoformat(),
            is_fallback=True,
            notice=notice
        )

    @staticmethod
    def get_weather(
        lat: float,
        lon: float,
        location_name: str = "현재 위치",
        target_date: Optional[datetime.date] = None
    ) -> WeatherData:
        """
        위도/경도와 방문 날짜(target_date)를 기반으로 그날의 기온, 최고/최저기온, 강수확률, 날씨 상태를 파싱
        - 오늘: 현재 기온 + 오늘 예보
        - 미래(최대 15일 후): 해당 날짜의 일별 예보 (현재 기온 자리에 일 평균 기온 사용)
        """
        today = datetime.date.today()
        target_date = target_date or today
        days_ahead = (target_date - today).days

        if days_ahead < 0 or days_ahead > FORECAST_MAX_DAYS:
            return WeatherService._fallback(
                location_name, target_date,
                f"{target_date}은(는) 예보 제공 범위(오늘~{FORECAST_MAX_DAYS}일 후) 밖이라 실제 날씨가 아닌 기본값을 사용합니다."
            )

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": [
                "temperature_2m_max", "temperature_2m_min",
                "precipitation_probability_max", "weather_code", "wind_speed_10m_max"
            ],
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
            "wind_speed_unit": "ms",
            "timezone": "Asia/Seoul"
        }
        if days_ahead == 0:
            params["current"] = ["temperature_2m", "wind_speed_10m", "weather_code"]

        try:
            response = requests.get(WeatherService.BASE_URL, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            daily = data.get("daily", {})
            current = data.get("current", {})

            def first(key, default):
                values = daily.get(key) or [default]
                return values[0] if values[0] is not None else default

            temp_max = first("temperature_2m_max", 22.0)
            temp_min = first("temperature_2m_min", 14.0)
            precip_prob = first("precipitation_probability_max", 0)

            if days_ahead == 0 and current:
                curr_temp = current.get("temperature_2m", (temp_max + temp_min) / 2)
                wind_speed = current.get("wind_speed_10m", 0.0)
                wmo_code = current.get("weather_code", first("weather_code", 0))
            else:
                curr_temp = round((temp_max + temp_min) / 2, 1)  # 미래 날짜는 일 평균 기온
                wind_speed = first("wind_speed_10m_max", 0.0)
                wmo_code = first("weather_code", 0)

            return WeatherData(
                location_name=location_name,
                temperature_current=curr_temp,
                temperature_min=temp_min,
                temperature_max=temp_max,
                precipitation_probability=precip_prob,
                weather_condition=WMO_WEATHER_CODES.get(wmo_code, "정보 없음"),
                wind_speed=wind_speed,
                forecast_date=target_date.isoformat()
            )

        except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as e:
            # 네트워크/응답 형식 오류 시 기본값 반환 (사용자에게 실제 예보가 아님을 표시)
            return WeatherService._fallback(
                location_name, target_date,
                f"날씨 API 호출에 실패하여({type(e).__name__}) 실제 날씨가 아닌 기본값을 사용합니다."
            )


# 5. 추천 엔진에 넘겨줄 융합 컨텍스트 파서
class ContextBuilder:
    @staticmethod
    def build_recommendation_context(weather: WeatherData, tpo: ScheduleTPO) -> str:
        """날씨 데이터와 TPO 데이터를 AI 프롬프트용 텍스트 컨텍스트로 변환"""
        fallback_note = (
            "\n- ⚠️ 주의: 실제 예보를 받지 못해 기본값입니다. 기온 변화에 대비할 수 있는 레이어드 코디를 우선하세요."
            if weather.is_fallback else ""
        )
        return f"""
[날씨 및 환경 조건]{fallback_note}
- 위치: {weather.location_name}
- 기온: {weather.temperature_current}℃ (최저: {weather.temperature_min}℃ / 최고: {weather.temperature_max}℃)
- 강수 확률: {weather.precipitation_probability}%
- 날씨 상태: {weather.weather_condition}
- 풍속: {weather.wind_speed} m/s

[일정 및 TPO 맥락]
- 일자: {tpo.date}
- 방문 장소: {tpo.location}
- 일정 및 목적: {tpo.occasion}
- 요구 스타일 / 드레스코드: {tpo.dress_code}
""".strip()


# 6. Phase 3 단독 테스트 실행부
if __name__ == "__main__":
    print("=== [Phase 3] 날씨 API 연동 및 TPO 컨텍스트 구축 테스트 ===")

    # 6-1. 서울 지역 좌표 (위도 37.5665, 경도 126.9780) 테스트
    seoul_lat, seoul_lon = 37.5665, 126.9780
    
    print("\n[1] Open-Meteo API 날씨 정보 조회 중...")
    weather_info = WeatherService.get_weather(seoul_lat, seoul_lon, location_name="서울시 중구")
    
    print("조회 성공:")
    print(f"- 위치: {weather_info.location_name}")
    print(f"- 현재/최저/최고 기온: {weather_info.temperature_current}℃ / {weather_info.temperature_min}℃ / {weather_info.temperature_max}℃")
    print(f"- 강수 확률: {weather_info.precipitation_probability}%")
    print(f"- 날씨 상태: {weather_info.weather_condition}")

    # 6-2. TPO 객체 생성
    print("\n[2] TPO 사용자 일정 데이터 구성:")
    sample_tpo = ScheduleTPO(
        date="2026-05-20",
        location="강남 야외 웨딩홀",
        occasion="친한 직장 동료 결혼식 하객 참석",
        dress_code="깔끔한 댄디 / 비즈니스 캐주얼"
    )
    print(sample_tpo.to_dict())

    # 6-3. AI 전달용 최종 융합 컨텍스트 출력
    print("\n[3] AI OOTD 추천 프롬프트용 통합 컨텍스트:")
    final_context = ContextBuilder.build_recommendation_context(weather_info, sample_tpo)
    print("-" * 50)
    print(final_context)
    print("-" * 50)