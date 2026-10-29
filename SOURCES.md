# 출처와 수치 기록 — 2026.10.30 AI 에이전트의 개념과 구현 조건 세미나

## 원문

- Michael Albada, *Building Applications with AI Agents: Designing and Implementing Multiagent Systems*, O'Reilly.
  쪽 번호는 인쇄본 기준. 4–7장과 12–18장 슬라이드는 서문, 각 장 도입부·결론과 표기한 절을 발표자가 요약한 것입니다. 쪽 번호가 없는 항목은 절 이름으로 표기했습니다.
- 책 저장소: github.com/michaelalbada/BuildingApplicationsWithAIAgents, commit `eeb325a`
  (`ch4-tool-use/third_party/book-repo`에 얕은 복제).
- Model Context Protocol 공식 Python SDK `mcp` 1.30.0 (FastMCP, stdio·streamable HTTP).
- langchain-ollama 1.1.0 `ChatOllama.bind_tools` 문서 문자열: tool_choice "is currently ignored as it is not supported by Ollama".
- Wikimedia API 응답: User-Agent 없는 요청은 HTTP 403 "Please set a user-agent and respect our robot policy https://w.wiki/4wJS",
  반복 요청 시 HTTP 429 "You are making too many requests to the API" (2026-10-26 관측).

## 슬라이드별 근거

| 장 | 내용 | 근거 |
|---|---|---|
| 3 | 멀티에이전트 시대의 질문, 현장의 질문 | 서문 p.xiii–xiv, Ch.1 “Defining AI Agents”·“The Pretraining Revolution” |
| 4 | 에이전트의 정의, 자율성의 스펙트럼, agentic system | Ch.1 p.1–2 |
| 5 | 코드 · 워크플로 · 챗봇/RAG · 에이전트의 선택 기준과 책의 예 | Ch.1 “Workflows and Agents” p.8–11 |
| 6 | 첫 에이전트(주문 취소), 구성 요소, UX | Ch.1 “Model Selection”, Ch.2 “Our First Agent System”·“Core Components” |
| 7 | 구현 조건 여섯 가지와 “없으면” | 서문 장 소개, Ch.4–13 (발표자 정리) |
| 8 | 도구 호출 다섯 단계 | Ch.4 p.72–75, `code/results/r1_book_calculator.json` |
| 9 | 메타데이터와 도구 수, 검색어 설명 | Ch.4 p.73, `d1_tool_selection.json`, `h_w_desc.json`. 지표 정의는 Ch.9 |
| 10 | API 장애 처리, 최종 답 검사, tool_choice | Ch.4 p.75–78·87–88, `d2_api_tools.json` (`part_b`), `d5_tool_choice.json` (`part_a`, `part_b_llm`) |
| 11 | 사고 사례, 최소 권한, 세 설계 비교, 모델 3회 | Ch.4 p.84–85, `d4_stateful_sqlite.json` (`battery`, `llm`) |
| 12 | 에이전트 유형, 도구 선택, 컨텍스트 엔지니어링 | Ch.5 “Agent Types”·“Tool Selection”·“Context Engineering”·결론 |
| 13 | 지식과 메모리, 메모리 방식, 학습 | Ch.6 도입부·결론, Ch.7 도입부·결론 |
| 14 | 출시 전 검증, 머그컵 환불 사례 | Ch.9 “Measuring Agentic Systems”·“Component Evaluation”·“Consistency” |
| 15 | 감시 질문, 회귀 테스트, 개선 루프 | Ch.10 도입부·“Regression Trace Collection”, Ch.11 결론 |
| 16 | 단일→멀티에이전트, 공급망 예, 추가 원칙 | Ch.8 “How Many Agents Do I Need?”·“Principles for Adding Agents”, `d1_tool_selection.json` |
| 17 | MCP, A2A Agent Card, MCP 선택 정확도 | Ch.4 p.78–84, Ch.8 “Agent-to-Agent Protocol”, `h_mcp_fix.json`, `d3_mcp.json` (질의 12개, 정답 라벨은 발표자 지정) |
| 18 | 고유 위험, 사례, 처방, 사람의 역할 | Ch.12 도입부·“The Unique Risks”·결론, Ch.13 “The Changing Role of Humans”, Ch.3 결론 |
| 19 | 정리 | 발표 요약 |
| 20–26 | 부록: 도구 선택 전체 수치, tool_choice, 도구 종류, 책 예제 원본 실행, 가설 검증, 실행 환경, 출처 | 각 슬라이드 하단 표기 |

## 수치의 조건과 한계

실험 이름과 슬라이드: R1 = 8장, D1 = 9·16장, D2·D5 = 10장(D5 상세는 부록 21장), D4 = 11장, R3·D3 = 17장.

- **모델**: `ollama:qwen2.5:7b`, temperature 0, RTX 3050 6GB. 다른 모델로 일반화하지 않습니다.
- **D1**: 질의 24개 × 조건 6개, 반복 1회. 첫 응답만 채점하고 도구는 실행하지 않습니다. 입력 토큰은 Ollama가 보고한 값입니다.
  "나쁜 메타데이터"는 이름과 설명만 바꾼 조건이며 스키마는 같습니다.
- **D2**: 주가 제공자는 127.0.0.1의 모의 HTTP 서버이고, 장애는 의도적으로 주입했습니다. 가격은 실제 시세가 아닙니다.
  Wikipedia 도구는 첫 실행에서 성공했고, 이후 실행에서는 Wikimedia의 403/429로 실패했습니다. 두 기록을 모두 보존했습니다.
- **D3**: 라우팅 질의 12개의 정답(math/weather/none)은 발표자가 정했습니다. 책의 서버는 MCP 핸드셰이크에 실패하므로,
  같은 동작의 FastMCP 서버(`demos/mcp_*_server.py`)로 실험했습니다.
- **D4**: 공격 호출 5종은 발표자가 구성했습니다. 모델 실험의 요청 문장은 삭제를 암시하므로, 결과는 "모델의 잘못"이 아니라
  "되돌릴 수 없는 작업이 확인 없이 가능했는가"로 해석합니다. 삭제 행 수(115/200)는 합성 데이터의 날짜 분포에서 나온 값입니다.
- **D5**: 질의 8개(산술 4 + 일반 4). "스크립트" 사례는 모델 응답을 미리 정한 것으로 실제 모델 결과가 아닙니다.
  "모델" 사례 중 B1은 첫 호출 인자를 의도적으로 망가뜨린 조건입니다. 근거 검사는 숫자 일치와 실패한 호출의 미해결 여부만
  보는 간단한 규칙이며, 자연어 답의 모든 오류를 잡지는 못합니다.
- 책 코드 정오표의 인쇄 오류 항목은 인쇄본 텍스트 추출본과 저장소 코드를 대조한 결과입니다.
