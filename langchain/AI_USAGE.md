# AI 사용 기록

허용 범위는 개념 질문과 자신이 작성한 코드의 디버깅입니다. 과제 함수의 정답이나 전체 구현을 대신 생성하게 해서는 안 됩니다. 먼저 현재 단계 검사를 실행하세요.

사용하지 않았다면 아래에 사용하지 않았다고 적습니다. 사용했다면 질문마다 기록합니다. API 키, 개인 이메일, 실제 회사 데이터는 입력하지 않습니다.

| 구분 | 질문 요약 | 공유한 자기 코드와 오류 범위 | 이해한 내용 | 직접 수정하고 검증한 결과 |
|---|---|---|---|---|
| 개념 | `RunnablePassthrough.assign`으로 기존 입력을 유지하며 결과를 추가하는 방식 | `build_primary_chain`의 `finish` 부분 | 기존 입력을 그대로 두고 `parsed` 같은 새 키를 추가해, 다음 단계에서 원래 데이터와 새 결과를 함께 쓸 수 있음 | `finish`에서 `parsed`와 `documents`로 출처 검사 작성. `check chain` 통과 |
| 개념 | `PydanticOutputParser`에서 형식 안내와 실제 검증이 어떻게 연결되는지 | `build_prompt_and_parser` | `format_instructions`로 출력 형식을 안내하고, 파서가 응답을 객체로 바꾸며 형식이 틀리면 예외를 냄. 형식 요청과 형식 검사는 별개 단계 | 파서와 `MessagesPlaceholder` 작성. `check chain` 통과 |
| 개념 | `with_retry`와 `with_fallbacks`의 순서와 복구 대상 오류 | `build_resilient_chain` | 재시도 후에도 실패하면 대체 실행으로 넘어감. 복구 가능한 오류만 지정하고 인증 오류나 코드 결함은 숨기지 않아야 함 | `support.RECOVERABLE`만 대상으로 재시도 2회와 fallback 연결. `check recovery` 통과 |
| 개념 | 스트리밍 중 일부 텍스트를 보낸 뒤 검증에 실패하면 어떻게 처리하는지 | `stream_answer` | `delta`는 검증 전 중간 출력, `reset`은 보낸 중간 출력 취소 신호, `final`은 검증을 통과한 최종 답. 이미 보냈다면 재시도 결과와 섞이지 않게 처리 | delta, reset, final 이벤트 작성. 직접 실행: 정상은 delta 7개 후 primary, midstream 실패는 delta 1개 후 reset과 fallback. `check stream` 통과 |

도구와 모델 이름: Claude

AI의 설명이 틀렸거나 그대로 적용하지 않은 부분: 없음.

최종 코드와 설명을 스스로 설명할 수 있는지 확인: 확인.
