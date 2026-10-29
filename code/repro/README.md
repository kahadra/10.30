# 책 예제 재현 단계

책 4장의 코드 예제를 세 단계로 실행합니다. 단계마다 무엇을 바꿨는지가 diff 파일로 남습니다.

| 단계 | 스크립트 | 바꾸는 것 | 결과 파일 |
|---|---|---|---|
| L0 원본 | `r0_book_originals.py` | 모델 이름 한 줄만: `model_name="gpt-4o"` → `"qwen2.5:7b"` (gpt-4o는 유료 API 모델). MCP 클라이언트는 무수정 | `results/r0_book_originals.json`, `book_runs/*.diff` |
| L1 최소 수정 | `r0b_book_minimal.py` | 실행을 막는 부분만, 이유와 함께 (`FIXES`). 책의 로직·프롬프트·라우팅 규칙은 유지, 책의 권고(재시도·대체·검증)는 넣지 않음 | `results/r0b_book_minimal.json`, `book_min/*.diff` |
| L2 권고 적용 | `../demos/d2_*.py`, `d3_*.py` 등 | 책 본문의 권고를 구현한 실험 | `results/d*_*.json` |

## 실행 환경 두 가지

- **book**: `.venv-book` — Python 3.11 + 책 저장소 `requirements.txt` 그대로 (langchain 0.1.20, langchain-openai 0.1.4, langgraph 0.0.28).
  책 4장 예제가 쓰는 `wikipedia`, `langchain-mcp-adapters`, `mcp`, `fastapi`, `uvicorn`은 이 목록에 없습니다.
  `langchain==0.1.20`과 `langchain-mcp-adapters`는 어떤 버전 조합으로도 함께 설치되지 않습니다(uv 의존성 해석 결과).
- **current**: `.venv` — Python 3.14 + `../requirements.lock.txt`.

## 모델

모든 단계에서 LLM은 로컬 Ollama의 `qwen2.5:7b`입니다. 원본의 `ChatOpenAI` 클래스는 그대로 두고,
`OPENAI_API_BASE`/`OPENAI_BASE_URL`을 Ollama의 OpenAI 호환 주소(`http://127.0.0.1:11434/v1`)로 지정합니다.
다른 모델에 `gpt-4o` 같은 이름을 붙여 부르지 않습니다. 결과는 qwen2.5:7b의 결과로만 보고합니다.

## 그 밖의 재현

- `r1_book_calculator.py`: 계산기 루프를 저장소 버전과 인쇄본 들여쓰기 버전으로 비교.
- `r3_book_mcp_handshake.py`: 책 저장소의 MCP 수학 서버에 공식 MCP 클라이언트로 핸드셰이크.
- `check_llm.py`: `.env`에 설정한 LLM의 연결과 도구 호출 확인.

## 목적 달성과 가설 검증

목표는 원본 코드를 그대로 돌리는 것이 아니라, 각 예제가 **보여 주려던 목적**을 달성하는 것입니다.
실패하면 원인을 가설로 세우고, 실행 전에 예측을 적은 뒤 검증합니다.

- `hypotheses.py` — 가설별 실험 (`w_ua`, `w_query`, `w_loop`, `w_desc`, `mcp`, `mcp_fix`, `tc`, `err`, `ver`). 결과: `results/h_*.json`
- `report_hypotheses.py` → `HYPOTHESES.md` — 예제별 목적·성공 기준·상태와 가설별 예측·결과·판정 요약
- `book_min_h/` — 가설 검증용 서버 변형 (수학 서버 `.strip()`, 날씨 서버 설명/도시 이름 허용)
