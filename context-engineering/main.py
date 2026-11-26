"""main.py의 todo(...) 부분을 작성하세요. support.py와 checks.py는 그대로 사용합니다."""
import copy
import hashlib
import json
import sys

import support


def todo(message):
    raise NotImplementedError(message)


# 필수 1. 필요한 자료와 사용자 기억 관리하기
def select_context(items, user_id, now):
    kept = []
    for item in items:
        allowed = (
        item["user_id"] in ("public", user_id)
        and item["trusted"] is True
        and item["active"] is True
        and (
            item["expires_at"] is None
            or item["expires_at"] > now
        )
    )
        if allowed:
            kept.append(copy.deepcopy(item))

    # 이유: 높은 우선순위의 자료를 먼저 고르면 어떤 문제가 생기는지 적으세요.
    #우선순위가 높아도 기한이 지났거나 다른 사람의 개인 자료면 쓸 수 없다.
    return sorted(kept, key=lambda item: (-item["priority"], item["id"]))


def memory_action(records, user_id, action, name, value=None):
    support.validate_memory_input(user_id, action, name, value)
    key = f"{user_id}:{name}"
    if action == "read":
        return copy.deepcopy(records.get(key))
    #("현재 사용자의 기억 조회")
    if action == "create":
        if key in records:
            raise ValueError("이미 있는 기억입니다. update를 사용하세요.")
        records[key] = copy.deepcopy(value)
        #("새 기억 저장")
    elif action == "update":
        if key not in records:
            raise KeyError("수정할 기억이 없습니다.")
        records[key] = copy.deepcopy(value)
        #("기존 기억 수정")
    elif action == "delete":
        return records.pop(key, None)
    #("현재 사용자의 기억 삭제")
    return copy.deepcopy(records[key])


def build_messages(prefix, question, context, turns, summary):
    data = json.dumps({"reference_data": context, "summary": summary}, ensure_ascii=False)
    history = [message for turn in turns for message in turn["messages"]]
    # 이유: 장기 기억과 세션 상태의 차이, 자료와 지시를 나누는 이유를 적으세요.
    # 사용자 선호는 다음 세션에도 쓰도록 저장하고 현재 작업 메모는 세션이 끝나면 비우고
    # 문서나 조회 결과에 적힌 내용을 서비스 지시로 받아들이지 않도록 참고 자료와 지시를 구분한다.
    return [
        {"role": "developer", "content": prefix},
        {"role": "user", "content": data},
        *history,
        {"role": "user", "content": question},
    ]
#("고정 지시, 참고 자료, 대화, 현재 질문 순서의 메시지")


# 필수 2. 긴 대화를 줄이고 반복 입력 재사용하기
def summarize(turns):
    summary = {}
    for turn in turns:
        for name, value in support.fact_lines(turn["messages"][0]["content"]):
            summary[name] = {
                "value": value,
                "source_turn_id" : turn["id"],
            }
            #todo("최신 값과 출처 턴")
    return summary


def select_window(turns, limit, reserve, margin, make_messages, count):
    support.validate_budget(limit, reserve, margin)
    budget = limit - reserve - margin
    #todo("입력에 쓸 수 있는 예산")
    if budget <= 0 or count(make_messages([])) > budget:
        raise ValueError("고정 입력만으로 예산을 넘었습니다.")
    kept = []
    for turn in reversed(turns):
        candidate = [turn, *kept]
        if count(make_messages(candidate)) > budget:
        #todo("전체 후보 입력이 예산을 넘는지"):
            break
        kept = candidate
    # 관측: 압축 비교 후 토큰 수, 빠진 사실, 선택한 한도를 기록합니다.
    # 전체 대화는 1,999토큰, 최근 대화만 넣으면 1,744토큰이고 담당자·마감일·승인조건이 빠졌다.
    # 총 한도 2,300에서 요약과 최근 대화를 함께 넣으면 1,744토큰으로 세 사실이 모두 남아 이 방식을 선택했다.
    return kept


def cache_key(prefix, user_id):
    key_text = user_id + "\n" + prefix
    return hashlib.sha256(key_text.encode("utf-8")).hexdigest()
#("사용자와 고정 지시로 만드는 캐시 키")
    # 관측: 실제 캐시 읽기/쓰기와 비용을 확인하고 미관측이면 그대로 적습니다.
    # 고정 예제의 최종 입력에서 tainted-document와 unverified-tool이 빠진 것을 확인했다.
    # 실제 API를 호출하지 않아 캐시 읽기·쓰기 토큰과 비용은 측정하지 못했다.


# 선택 심화 1. 새 대화만 반영하고 변경 이력 남기기
def merge_summary(previous, turns):
    result = copy.deepcopy(previous)
    current = result["current"]
    changes = result["changes"]
    processed_ids = result["processed_ids"]

    for turn in turns:
        turn_id = turn["id"]

        if turn_id in processed_ids:
            continue

        new_facts = summarize([turn])
        for name, after in new_facts.items():
            before = current.get(name)

            if before is not None and before["value"] != after["value"]:
                changes.append({
                    "name": name,
                    "before": before,
                    "after": after,
                })

            current[name] = after

        processed_ids.append(turn_id)

    return result
#todo("선택 심화: 새 턴의 요약과 변경 이력")


if __name__ == "__main__":
    raise SystemExit(support.cli(sys.modules[__name__]))
