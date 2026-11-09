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
        
        self.client = genai.Client(api_key=self.api_key)
        
        # 1순위 및 백업 모델 순서
        self.model_chain = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash"
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
                    if any(k in error_str for k in ["503", "high demand", "overloaded", "unavailable"]):
                        wait_seconds = round(1.0 + (attempt * 0.5) + random.uniform(0.1, 0.5), 2)
                        print(f"⚠️ [{model_name}] 서버 트래픽 밀림 ({attempt}/{max_retries}). {wait_seconds}초 대기...")
                        time.sleep(wait_seconds)
                        last_error = e
                    else:
                        raise e

            print(f"🔄 [{model_name}] 재시도 한도 초과. 다음 모델로 우회합니다.")

        raise Exception(f"모든 Gemini 모델 서버 과부하 상태: {last_error}")