# app.py
import streamlit as st
from PIL import Image
import datetime

# 백엔드 모듈 임포트
from closet_db import ClosetDB, ClothingItem
from vision_tagging import ClothingAutoTagger
from weather_tpo import WeatherService, ScheduleTPO
from recommendation import OOTDRecommender

# 1. 페이지 레이아웃 및 타이틀 설정
st.set_page_config(
    page_title="Personal AI OOTD Stylist",
    page_icon="👗",
    layout="wide"
)

# 2. DB 및 백엔드 서비스 객체 싱글톤 초기화
@st.cache_resource
def get_db():
    return ClosetDB("closet.db")

db = get_db()
tagger = ClothingAutoTagger(db)
recommender = OOTDRecommender(db)

# 3. Streamlit 세션 상태(Session State) 초기화
if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "user_closet" not in st.session_state:
    st.session_state["user_closet"] = []


# =====================================================================
# 화면 1: 미인증 사용자 - 회원가입 및 로그인 화면
# =====================================================================
if not st.session_state["is_logged_in"]:
    st.title("👗 Personal AI OOTD Stylist")
    st.markdown("나만의 맞춤형 AI 옷장 분석 및 날씨/TPO 기반 OOTD 추천 서비스")
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔑 로그인")
        login_id = st.text_input("아이디", key="login_id")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인 실행", use_container_width=True):
            success, msg = db.authenticate_user(login_id, login_pw)
            if success:
                st.session_state["is_logged_in"] = True
                st.session_state["user_id"] = login_id
                st.session_state["user_closet"] = db.fetch_user_items(login_id)
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with col2:
        st.subheader("📝 회원가입")
        reg_id = st.text_input("신규 아이디", key="reg_id")
        reg_pw = st.text_input("신규 비밀번호", type="password", key="reg_pw")
        if st.button("회원가입 신청", use_container_width=True):
            success, msg = db.register_user(reg_id, reg_pw)
            if success:
                st.success(msg)
            else:
                st.error(msg)

# =====================================================================
# 화면 2: 로그인 완료 - 메인 대시보드 (사이드바: 옷장 관리 / 메인: OOTD 추천)
# =====================================================================
else:
    user_id = st.session_state["user_id"]

    # -----------------------------------------------------------------
    # 사이드바: 프로필, 옷 등록 및 내 옷장 갤러리
    # -----------------------------------------------------------------
    with st.sidebar:
        st.title(f"👤 {user_id}님의 옷장")
        if st.button("로그아웃", type="secondary"):
            st.session_state["is_logged_in"] = False
            st.session_state["user_id"] = None
            st.session_state["user_closet"] = []
            st.rerun()

        st.divider()

        # [사이드바 1] AI 옷 등록 기능
        st.subheader("📸 새 옷 추가 (Gemini Auto-Tagging)")
        uploaded_file = st.file_uploader(
            "옷 사진을 업로드하세요", 
            type=["jpg", "png", "jpeg"]
        )

        if uploaded_file is not None:
            raw_img = Image.open(uploaded_file)
            st.image(raw_img, caption="업로드 이미지 미리보기", use_container_width=True)

            if st.button("✨ AI 분석 및 옷장 등록", use_container_width=True):
                with st.spinner("Gemini가 이미지를 압축 분석 중입니다..."):
                    try:
                        registered_item = tagger.analyze_and_register(raw_img, user_id=user_id)
                        st.success(f"'{registered_item.name}' 등록 완료!")
                        # 세션 및 옷장 DB 동기화
                        st.session_state["user_closet"] = db.fetch_user_items(user_id)
                        st.rerun()
                    except Exception as e:
                        st.error(f"등록 실패: {e}")

        st.divider()

        # [사이드바 2] 등록된 옷 목록 및 삭제
        st.subheader(f"🧺 보관된 옷 ({len(st.session_state['user_closet'])}개)")
        if not st.session_state["user_closet"]:
            st.info("등록된 옷이 없습니다. 사진을 업로드해보세요!")
        else:
            for item in st.session_state["user_closet"]:
                with st.expander(f"[{item.category}] {item.name}"):
                    st.write(f"**세부 분류:** {item.sub_category}")
                    st.write(f"**색상:** {', '.join(item.color)}")
                    st.write(f"**계절:** {', '.join(item.season)}")
                    st.write(f"**스타일:** {', '.join(item.style)}")
                    if item.description:
                        st.caption(item.description)
                    
                    if st.button("❌ 삭제", key=f"del_{item.id}"):
                        if db.delete_item(item.id, user_id):
                            st.session_state["user_closet"] = db.fetch_user_items(user_id)
                            st.rerun()

    # -----------------------------------------------------------------
    # 메인 화면: 날씨/TPO 입력 및 AI 코디 추천 결과 출력
    # -----------------------------------------------------------------
    st.title("✨ AI Personal OOTD Stylist")
    st.markdown("날씨 정보와 방문 장소/일정(TPO)을 기반으로 최고의 스타일을 조합합니다.")
    st.divider()

    # 1. TPO 및 날씨 조건 입력 폼
    col_input1, col_input2 = st.columns(2)

    with col_input1:
        st.subheader("1. 일정 및 TPO 설정")
        today = datetime.date.today()
        selected_date = st.date_input(
            "방문 날짜",
            today,
            min_value=today,
            max_value=today + datetime.timedelta(days=15),  # 날씨 예보 제공 범위
            help="날씨 예보는 오늘부터 15일 후까지 제공됩니다."
        )
        location_option = st.selectbox(
            "방문 지역 선택",
            options=["서울 (강남/명동)", "부산 (해운대)", "제주 (제주시)", "인천 (송도)", "대구 (동성로)"]
        )
        
        # 위도/경도 매핑 사전
        geo_coords = {
            "서울 (강남/명동)": (37.5665, 126.9780, "서울"),
            "부산 (해운대)": (35.1587, 129.1604, "부산"),
            "제주 (제주시)": (33.4996, 126.5312, "제주"),
            "인천 (송도)": (37.3828, 126.6572, "인천"),
            "대구 (동성로)": (35.8714, 128.6014, "대구")
        }

    with col_input2:
        st.subheader("2. 상세 목적 및 드레스코드")
        occasion_input = st.text_input(
            "방문 목적 / 일정", 
            value="중요한 비즈니스 미팅 및 저녁 식사"
        )
        style_input = st.text_input(
            "선호 스타일 / 드레스코드", 
            value="신뢰감을 주는 단정한 비즈니스 캐주얼"
        )

    st.divider()

    # 2. OOTD 추천 실행 버튼
    if st.button("💡 오늘 최적의 OOTD 추천받기", type="primary", use_container_width=True):
        if not st.session_state["user_closet"]:
            st.warning("⚠️ 옷장에 등록된 옷이 없습니다. 사이드바에서 사진을 먼저 등록해 주세요.")
        else:
            lat, lon, loc_name = geo_coords[location_option]

            with st.spinner("실시간 날씨 파싱 및 Gemini AI OOTD 추론 진행 중..."):
                # A. 날씨 정보 파싱
                weather_data = WeatherService.get_weather(
                    lat, lon, location_name=loc_name, target_date=selected_date
                )

                # B. TPO 객체 구성
                tpo_data = ScheduleTPO(
                    date=str(selected_date),
                    location=location_option,
                    occasion=occasion_input,
                    dress_code=style_input
                )

                # C. AI 추천 엔진 실행
                recommendation = recommender.recommend(user_id, weather_data, tpo_data)

            if recommendation:
                st.subheader(f"🌤️ 환경 및 날씨 정보 ({weather_data.forecast_date})")
                if weather_data.is_fallback:
                    st.warning(f"⚠️ {weather_data.notice}")
                w_col1, w_col2, w_col3, w_col4 = st.columns(4)
                w_col1.metric("위치 / 상태", f"{weather_data.location_name}", weather_data.weather_condition)
                temp_label = "현재 기온" if selected_date == datetime.date.today() else "평균 기온"
                w_col2.metric(temp_label, f"{weather_data.temperature_current} ℃")
                w_col3.metric("최저/최고 기온", f"{weather_data.temperature_min}℃ / {weather_data.temperature_max}℃")
                w_col4.metric("강수 확률", f"{weather_data.precipitation_probability} %")

                st.divider()

                st.subheader(f"👔 AI 추천 착장 조합 (무드: {recommendation.get('overall_style', '캐주얼')})")

                # 착장 카드를 4개 컬럼으로 시각화
                c_outer, c_top, c_bottom, c_shoes = st.columns(4)

                outer = recommendation.get('outer_item')
                top = recommendation.get('top_item')
                bottom = recommendation.get('bottom_item')
                shoes = recommendation.get('shoes_item')

                with c_outer:
                    st.markdown("### 🧥 아우터")
                    if outer:
                        st.success(f"**{outer.name}**\n\n- 색상: {', '.join(outer.color)}\n- 카테고리: {outer.sub_category}")
                    else:
                        st.info("아우터 없음 / 미선택")

                with c_top:
                    st.markdown("### 👕 상의")
                    if top:
                        st.success(f"**{top.name}**\n\n- 색상: {', '.join(top.color)}\n- 카테고리: {top.sub_category}")
                    else:
                        st.warning("선택 안 됨")

                with c_bottom:
                    st.markdown("### 👖 하의")
                    if bottom:
                        st.success(f"**{bottom.name}**\n\n- 색상: {', '.join(bottom.color)}\n- 카테고리: {bottom.sub_category}")
                    else:
                        st.warning("선택 안 됨")

                with c_shoes:
                    st.markdown("### 👟 신발")
                    if shoes:
                        st.success(f"**{shoes.name}**\n\n- 색상: {', '.join(shoes.color)}\n- 카테고리: {shoes.sub_category}")
                    else:
                        st.info("신발 없음 / 미선택")

                st.markdown("---")
                st.subheader("💡 코디 추천 이유")
                st.write(recommendation.get('recommendation_reason', ''))

                st.subheader("✨ 스타일링 팁")
                st.write(recommendation.get('styling_tips', ''))

                with st.expander("🧠 AI 추론 및 단계별 고려 과정 (Chain of Thought)"):
                    st.write(recommendation.get('cot_reasoning', ''))