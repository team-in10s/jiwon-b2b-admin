# 개발 환경 설정

## Streamlit Secrets 설정

1. `.streamlit/secrets.toml` 파일을 생성하세요:
```toml
# PostgreSQL 연결 문자열 형식:
# postgresql://username:password@host:port/database_name
DATABASE_URL = "postgresql://username:password@host:port/database_name"

# OpenAI API 키
OPENAI_API_KEY = "sk-..."

# Webhook URL
WEBHOOK_URL = "https://your-webhook-url.com/endpoint"

# 관리자 비밀번호
ADMIN_PASSWORD = "in10sco1!"
```

2. 실제 값으로 교체하세요:
   - DATABASE_URL: PostgreSQL 데이터베이스 연결 정보
   - OPENAI_API_KEY: OpenAI API 키
   - WEBHOOK_URL: Webhook 엔드포인트 URL
   - ADMIN_PASSWORD: 관리자 비밀번호

## 환경 변수 설정

또는 다음 환경 변수를 설정할 수 있습니다:
```bash
# PostgreSQL 연결 문자열
export DATABASE_URL="postgresql://username:password@host:port/database_name"

# OpenAI API 키
export OPENAI_API_KEY="sk-..."

# Webhook URL
export WEBHOOK_URL="https://your-webhook-url.com/endpoint"

# 관리자 비밀번호
export ADMIN_PASSWORD="in10sco1!"
```

## 개발 서버 실행

```bash
cd src
streamlit run main.py
```

## 데이터베이스 연결 문자열 형식

PostgreSQL 연결 문자열은 다음 형식을 따릅니다:
- `postgresql://username:password@host:port/database_name`

예시:
- `postgresql://myuser:mypassword@localhost:5432/mydb`
- `postgresql://admin:secret@database.example.com:5432/production_db` 