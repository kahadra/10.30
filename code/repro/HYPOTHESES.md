# 책 4장 예제: 목적 달성과 가설 검증

생성: `repro/report_hypotheses.py` (결과 JSON에서 자동 작성). LLM은 모두 `qwen2.5:7b`(Ollama). 원본의 `gpt-4o`는 유료 API 모델이라 모델 이름 한 줄만 바꿨고, 다른 모델에 gpt-4o라는 이름을 붙이지 않았습니다.

## 1. 예제별 목적과 결과

| 예제 | 목적 (성공 기준) | L0 원본 · 책 환경 | L0 원본 · 현재 환경 | L1 최소 수정 | 목적 달성 |
|---|---|---|---|---|---|
| 계산기 p.74 | 모델이 도구·인자를 골라 실행하고 결과로 정답 | 실패 — field required (type=value_error.missing) | 동작 | 동작 (현재 환경: 모델 이름 외 수정 없음 · 책 환경용 1줄 추가) | **달성** (원본 그대로, 현재 환경) |
| Wikipedia p.76 | 검색으로 관련 문서를 가져와 그 내용으로 답 | 실패 — ImportError: Could not import wikipedia python package. Please install it with 'pip instal | 실패 — requests.exceptions.JSONDecodeError: Expecting value: line 1 column 1 (char 0) | 실행되나 오답 (원본 3줄 수정: User-Agent 등) — H-W2~W4 | **달성** — 최선 조건 “title-only description, 1 round” 성공 83% |
| 주가 p.77 | 외부 API에서 실시간 데이터를 받아 답 | 실패 — field required (type=value_error.missing) | 실패 — requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.example.com', port=443) | 동작 (원본 6줄 수정) | **달성** (L1: 실제 시세 API) |
| MCP p.82–83 | 두 MCP 서버(stdio·HTTP)의 도구로 질의를 올바르게 보내 답 | 실패 — ModuleNotFoundError: No module named 'langchain_mcp_adapters' | 실패 — ModuleNotFoundError: No module named 'langchain' | 동작 (원본 10줄 수정) | **달성** — “math .strip() + weather server accepts bare city” + 모델 라우팅: 종단 정답 100% (책 서버·키워드 라우터 25%) |
| 상태 도구 p.84–85 | 좁은 도구·최소 권한이 파괴적 행동을 막음 | 책에 코드 없음 | – | – | **달성** (`demos/d4`) |
| 설정 p.87–88 | tool_choice로 제어, 검증·재시도·대체로 복구 | 책에 코드 없음 | – | – | **부분 달성**: Ollama는 tool_choice를 무시 → 코드로 강제 (`demos/d5`) |

## 2. 가설 검증

### H-W1 · Wikipedia 원본 실패(HTTP 429)

- 가설: 라이브러리의 공용 기본 User-Agent가 호출 제한을 받는다(코드 결함 아님)
- 예측: 같은 요청을 번갈아 보내면 기본 UA는 대부분 429, 식별 UA는 대부분 200
- 결과: 기본 UA 429 4/6, 식별 UA 429 0/6
- 판정: **supported**
- 비고: first computed with a stricter threshold (default ok-rate <= 0.2) than the stated prediction ('default mostly 429'); recomputed with default ok-rate < 0.5

### H-W2 · Wikipedia 최소 수정판의 오답

- 가설: 모델이 만든 검색어가 엉뚱한 1순위 문서를 끌어온다
- 예측: 인물 이름만 넣으면 맞는 문서, 모델의 검색어로는 다른 문서
- 결과: “Buzz Aldrin most impressive thing” → ['Bart Sibrel']; “Buzz Aldrin” → ['Buzz Aldrin']
- 판정: **supported**

### H-W3 · 책의 1회 루프와 top_k=1

- 가설: ① 도구 호출을 한 번만 허용하는 루프가 잘못된 검색을 회복하지 못한다 ② 검색 결과 1개는 취약하다
- 예측: 여러 단계 루프, top_k=3에서 성공률 상승 (인물 6명 질의)
- 결과: book: 1 round, top_k=1: 성공 0%, 맞는 문서 검색 0%; multi-step (<=3), top_k=1: 성공 0%, 맞는 문서 검색 0%; 1 round, top_k=3: 성공 0%, 맞는 문서 검색 0%; multi-step (<=3), top_k=3: 성공 0%, 맞는 문서 검색 0%
- 판정: **① not supported · ② not supported**
- 비고: 성공 = 맞는 문서를 가져왔고 답이 그 문서의 핵심 사실을 언급. 여러 단계를 허용해도 모델이 같은 검색어를 반복함. 429는 Retry-After를 지켜 재시도(실험 장치, 기록됨)

### H-W4 · 검색어를 만드는 것은 도구 설명

- 가설: 모델이 질문 문장을 검색어로 쓰는 것은 원래 설명(“Input should be a search query.”)이 허용하기 때문
- 예측: 설명에 ‘입력은 문서 제목(예: 인물 이름)이지 질문이 아니다’를 적으면 책의 1회 루프에서도 성공률 상승
- 결과: original description, 1 round: 성공 0%, 맞는 문서 0%; title-only description, 1 round: 성공 83%, 맞는 문서 83%; title-only description, multi-step (<=3): 성공 83%, 맞는 문서 100%
- 판정: **supported**
- 비고: 바꾼 것은 도구 설명 문자열 하나 — 4장 ‘메타데이터가 선택을 좌우한다’의 직접 사례

### H-M1 · MCP 예제의 병목

- 가설: 서버가 아니라 책의 키워드 라우터가 목적 달성을 막는다
- 예측: 같은 책 서버에서 모델 라우팅이 라우팅 정확도와 종단 정답률을 모두 높인다
- 결과: 키워드: 라우팅 42%, 종단 25% · 모델: 라우팅 100%, 종단 58%
- 판정: **supported**

### H-M2 · 책 수학 서버의 파싱 오류

- 가설: 책 서버가 질문에서 숫자·연산자만 남길 때 앞 공백이 남아 `unexpected indent`가 난다
- 예측: `.strip()` 한 줄 추가로 키워드가 수학으로 보낸 질의가 성공
- 결과: book servers (L1): 키워드 종단 25%; math .strip() + weather description: pass full question: 키워드 종단 42%; math .strip() + weather server accepts bare city: 키워드 종단 42%
- 판정: **supported**

### H-M3 · 날씨 실패

- 가설: 서버 파서는 ‘weather in <도시>’만 이해하는데 모델은 도시 이름만 넘긴다
- 예측: (a) 도구 설명에 ‘질문 전체를 넘겨라’ 또는 (b) 서버가 도시 이름도 받으면 모델 종단 정답률 상승
- 결과: book servers (L1): 모델 종단 58%; math .strip() + weather description: pass full question: 모델 종단 83%; math .strip() + weather server accepts bare city: 모델 종단 100%
- 판정: **(a) supported · (b) supported**
- 비고: (a)에서는 날씨는 모두 성공했지만, 같은 프롬프트 안의 수학 질의 2건에서 모델이 원문(“twelve times eight”)을 그대로 넘겨 실패 — 한 도구의 설명이 다른 도구의 인자 생성에도 영향

### H-C1 · tool_choice 무시

- 가설: LangChain의 Ollama 연동만 tool_choice를 버리고, Ollama의 OpenAI 호환 API는 지킨다
- 예측: /v1로 보내면 none은 0%, required는 100% 호출
- 결과: auto: 산술 100%, 일반 0%; none: 산술 100%, 일반 0%; required: 산술 100%, 일반 0%; multiply: 산술 100%, 일반 0% · 요청 본문에 tool_choice가 실려 간 것을 확인
- 판정: **반증 — 서버(Ollama)가 무시한다**
- 비고: 대응: 코드로 강제 (demos/d5 enforced)

### H-C2 · 도구 오류 후 답 지어내기

- 가설: 일반 오류 메시지만으로는 부족하고, 명시적 시스템 규칙이 지어내기를 줄인다
- 예측: 규칙을 넣으면 지어내기 비율 감소
- 결과: error ToolMessage only: 33%; error ToolMessage + system rule: 17%
- 판정: **supported (방향은 일치하나 6건 중 1건 차이 — 약한 근거)**
- 비고: ‘지어내기’에는 모델이 스스로 맞게 계산한 경우(17×23=391)도 포함. 규칙만으로 0이 되지 않으므로 최종 답 검사(demos/d5)가 여전히 필요

### H-V1 · 책 환경에서의 실패

- 가설: 책 코드는 고정 버전(langchain-core 0.1)보다 새 버전(≥0.2)을 기준으로 쓰였다
- 예측: 모델 이름만 바꾼 원본 계산기가 langchain-core 0.2에서 동작
- 결과: Python 3.11, langchain/core 0.2.16 0.2.43 → exit 0
- 판정: **supported**

