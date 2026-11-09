import sqlite3
import json
import hashlib
import secrets
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# 1. 옷장 데이터 구조
@dataclass
class ClothingItem:
    id: str
    user_id: str  # 소유자 사용자 ID 추가
    name: str
    category: str
    sub_category: str
    color: List[str]
    season: List[str]
    style: List[str]
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 2. 비밀번호 보안 해싱 함수
class PasswordManager:
    @staticmethod
    def hash_password(password: str) -> str:
        """비밀번호에 무작위 Salt를 부여하고 PBKDF2로 해싱"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 10만 회 키 스트레칭
        ).hex()
        return f"{salt}:{pwd_hash}"

    @staticmethod
    def verify_password(stored_password_hash: str, provided_password: str) -> bool:
        """입력받은 비밀번호가 DB에 저장된 해시와 일치하는지 검증"""
        try:
            salt, stored_hash = stored_password_hash.split(":")
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                provided_password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            ).hex()
            # 시간차 공격(Timing Attack) 방지를 위한 상수 시간 비교
            return secrets.compare_digest(stored_hash, pwd_hash)
        except Exception:
            return False


# 3. 다중 사용자 지원 데이터베이스 매니저
class ClosetDB:
    def __init__(self, db_path: str = "closet.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """테이블 초기화"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 사용자 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            # 옷장 테이블 (user_id 컬럼 포함)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS closet (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                sub_category TEXT,
                color TEXT,
                season TEXT,
                style TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """)
            conn.commit()

    # --- 사용자 인증 (Auth) 로직 ---
    def register_user(self, user_id: str, password: str) -> tuple[bool, str]:
        """회원가입"""
        if not user_id or not password:
            return False, "아이디와 비밀번호를 모두 입력해주세요."
        
        hashed_password = PasswordManager.hash_password(password)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (user_id, password_hash) VALUES (?, ?)",
                    (user_id, hashed_password)
                )
                conn.commit()
                return True, "회원가입이 완료되었습니다."
        except sqlite3.IntegrityError:
            return False, "이미 존재하는 아이디입니다."
        except Exception as e:
            return False, f"회원가입 오류: {str(e)}"

    def authenticate_user(self, user_id: str, password: str) -> tuple[bool, str]:
        """로그인 검증"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if not row:
                    return False, "존재하지 않는 아이디입니다."
                
                stored_hash = row[0]
                if PasswordManager.verify_password(stored_hash, password):
                    return True, "로그인 성공!"
                else:
                    return False, "비밀번호가 일치하지 않습니다."
        except Exception as e:
            return False, f"로그인 처리 중 오류: {str(e)}"

    # --- 사용자별 옷장 데이터 (CRUD) 로직 ---
    def insert_item(self, item: ClothingItem) -> bool:
        """옷 등록 (user_id와 함께 저장)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO closet (id, user_id, name, category, sub_category, color, season, style, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.id,
                    item.user_id,
                    item.name,
                    item.category,
                    item.sub_category,
                    json.dumps(item.color, ensure_ascii=False),
                    json.dumps(item.season, ensure_ascii=False),
                    json.dumps(item.style, ensure_ascii=False),
                    item.description
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"DB 저장 오류: {e}")
            return False

    def fetch_user_items(self, user_id: str) -> List[ClothingItem]:
        """특정 사용자의 옷장 데이터만 격리 조회"""
        items = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, user_id, name, category, sub_category, color, season, style, description FROM closet WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                )
                rows = cursor.fetchall()

                for row in rows:
                    items.append(ClothingItem(
                        id=row[0],
                        user_id=row[1],
                        name=row[2],
                        category=row[3],
                        sub_category=row[4] or "",
                        color=json.loads(row[5]) if row[5] else [],
                        season=json.loads(row[6]) if row[6] else [],
                        style=json.loads(row[7]) if row[7] else [],
                        description=row[8] or ""
                    ))
        except Exception as e:
            print(f"DB 조회 오류: {e}")
        return items

    def delete_item(self, item_id: str, user_id: str) -> bool:
        """옷 삭제 (user_id 조건으로 본인 소유 아이템만 삭제 가능)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM closet WHERE id = ? AND user_id = ?",
                    (item_id, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"DB 삭제 오류: {e}")
            return False


# 4. 기능 테스트 실행
if __name__ == "__main__":
    db = ClosetDB("closet.db")

    print("=== [1] 회원가입 및 로그인 보안 테스트 ===")
    # 1. 회원가입 테스트
    success, msg = db.register_user("user_a", "my_secret_pass123")
    print(f"회원가입 결과: {msg}")

    # 2. 비밀번호 검증 테스트
    is_valid, login_msg = db.authenticate_user("user_a", "my_secret_pass123")
    print(f"올바른 비밀번호 로그인: {login_msg}")

    is_valid_fail, login_msg_fail = db.authenticate_user("user_a", "wrong_password")
    print(f"틀린 비밀번호 로그인: {login_msg_fail}")

    print("\n=== [2] 사용자별 데이터 격리 저장 테스트 ===")
    # user_a의 옷 등록
    db.insert_item(ClothingItem(
        id="item_a1",
        user_id="user_a",
        name="user_a의 크림색 와이드 팬츠",
        category="하의",
        sub_category="슬랙스",
        color=["cream"],
        season=["봄", "가을"],
        style=["모던"]
    ))

    # user_a의 데이터만 조회되는지 확인
    user_a_closet = db.fetch_user_items("user_a")
    print(f"user_a의 옷장 개수: {len(user_a_closet)}개")
    for item in user_a_closet:
        print(f"   - [{item.user_id}] {item.name}")