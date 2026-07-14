FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# npm이 audit·funding 조회로 네트워크를 더 쓰지 않게 한다. 이 단계가 빌드에서 제일 느리다.
ENV NPM_CONFIG_AUDIT=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_UPDATE_NOTIFIER=false

WORKDIR /app

# 첨부파일 텍스트 추출용 Node.js 20 + kordoc(한국 문서 파서) 설치.
# api·crawler가 이 이미지를 공유하며, 추출 잡은 crawler에서 subprocess로 kordoc을 호출한다.
#
# 이 레이어가 빌드 시간의 대부분을 차지한다(kordoc·pdfjs-dist는 의존성이 많다).
# 코드만 바뀌면 캐시가 살아 있어 다시 돌지 않지만, 베이스 이미지가 갱신되면 전부 다시 돈다.
# 그때 npm 레지스트리가 느리면 몇 분씩 멈춘 것처럼 보인다 — 실제로는 받는 중이다.
# fetch 재시도를 넉넉히 줘서 일시적인 네트워크 오류로 빌드가 죽지 않게 한다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm install -g --loglevel=warn kordoc pdfjs-dist \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* /root/.npm

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests/fixtures ./tests/fixtures

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
