# TB2 Ch.4 Tool Use — 실습 코드

*Building Applications with AI Agents* 4장(p.71–88)의 예제를 실행하고 보완한 실험 모음입니다.
기본 LLM은 로컬 Ollama 모델(`qwen2.5:7b`)이라 API 비용이 들지 않습니다.

## 준비

```powershell
# 1) Ollama 설치 후 모델 받기
ollama pull qwen2.5:7b
# 2) .env 확인 (.env.example 참고)
#    LLM_PROVIDER=ollama | openai, LLM_MODEL=..., OPENAI_API_KEY=(openai일 때만)
# 3) 확인
.venv\Scripts\python.exe repro\check_llm.py
```

가상환경 패키지 버전은 `requirements.lock.txt`에 있습니다. `third_party/book-repo`는 책 저장소
(github.com/michaelalbada/BuildingApplicationsWithAIAgents, commit eeb325a)의 얕은 복제본입니다.

## 실험

| 파일 | 책 위치 | 내용 | LLM 없이 실행되는 부분 |
|---|---|---|---|
| `repro/r3_book_mcp_handshake.py` | p.81–84 | 책의 MCP 서버에 공식 MCP 클라이언트로 접속 | 전부 |
| `demos/d1_tool_selection.py` | p.73 | 도구 수(6/15/30) × 메타데이터(좋음/나쁨) → tool recall·precision·parameter accuracy | `--dry-run`만 |
| `demos/d2_api_tools.py` | p.75–78 | 책의 Wikipedia·주가 도구 재현, timeout·백오프·백업·캐시로 보강 | Part A, B |
| `demos/d3_mcp.py` | p.81–84 | 책의 두 서버 MCP 예제를 FastMCP로 재구현, 키워드 라우팅 vs LLM 라우팅 | Part A, B |
| `demos/d4_stateful_sqlite.py` | p.84–85 | 임의 SQL / DROP·ALTER 차단 / 범위 축소+최소 권한 비교 | 공격 호출 배터리, 계층 검사 |
| `demos/d5_tool_choice.py` | p.87–88 | tool_choice 네이티브 vs 코드 강제, 검증·재시도·대체·근거 검사·로그 | 스크립트 사례 |

`--llm` 옵션을 붙이면 LLM 단계까지 실행합니다. 결과는 `results/*.json`(D5의 단계 로그는
`results/d5_events.jsonl`)에 저장됩니다. `results/d2_api_tools_run1_offline.json`은 Wikimedia가
요청을 차단하기 전의 첫 실행 기록입니다.

## 결과 해석의 한계

- 로컬 7B 모델 하나, temperature 0, 대부분 1회 실행. 경향 확인용이며 모델 일반으로 일반화하지 않습니다.
- D5의 "스크립트" 사례는 분기를 결정적으로 보이려고 모델 응답을 고정한 것이며 실제 모델 결과가 아닙니다.
- D2의 주가 제공자는 127.0.0.1의 모의 HTTP 서버입니다. 실제 시세가 아닙니다.
