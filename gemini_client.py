# gemini_client.py
import os
import time
import random
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv()

class SafeGeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(".env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
        
        # 모델이 응답 없이 멈춰도 다음 모델로 넘어가도록 호출 제한 시간(ms)을 둔다
        self.client = genai.Client(api_key=self.api_key, http_options={"timeout": 20_000})
        
        # 1순위 및 백업 모델 순서
        self.model_chain = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            # gemini-2.5-flash는 확인 결과 응답 없이 멈춰(제공 중단 계열) 확인된 모델로 교체
            "gemini-3.6-flash"
        ]

    def generate_content_with_retry(self, contents, config=None, max_retries=3):
        """503 과부하 에러 시 자동 재시도 및 모델 전환 수행"""
        last_error = None

        for model_name in self.model_chain:
            for attempt in range(1, max_retries + 1):
                try:
                    kwargs = {"model": model_name, "contents": contents}
                    if config:
                        kwargs["config"] = config
                        
                    response = self.client.models.generate_content(**kwargs)
                    return response

                except APIError as e:
                    error_str = str(e).lower()
                    if e.code in (429, 404):
                        # 429(할당량 초과)는 기다려도 바로 풀리지 않고, 404(제공 중단)는 영영 풀리지 않으므로
                        # 같은 모델로 재시도하지 않고 다음 모델로 넘어간다 (이전에는 예외로 앱 전체가 실패했음)
                        print(f"⚠️ [{model_name}] {e.code} 응답. 재시도 없이 다음 모델로 우회합니다.")
                        last_error = e
                        break
                    if any(k in error_str for k in ["503", "high demand", "overloaded", "unavailable"]):
                        wait_seconds = round(1.0 + (attempt * 0.5) + random.uniform(0.1, 0.5), 2)
                        print(f"⚠️ [{model_name}] 서버 트래픽 밀림 ({attempt}/{max_retries}). {wait_seconds}초 대기...")
                        time.sleep(wait_seconds)
                        last_error = e
                    else:
                        raise e
                except Exception as e:
                    # 호출 제한 시간 초과는 다음 모델로, 그 외 오류는 그대로 올린다
                    if "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower():
                        print(f"⚠️ [{model_name}] 응답 시간 초과. 다음 모델로 우회합니다.")
                        last_error = e
                        break
                    raise

            print(f"🔄 [{model_name}] 재시도 한도 초과. 다음 모델로 우회합니다.")

        raise Exception(f"모든 Gemini 모델 호출 실패: {last_error}")