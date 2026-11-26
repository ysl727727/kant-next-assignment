"""KANT NEXT DevDesk RAG. 이 파일의 빈칸만 작성하세요."""
from qdrant_client import models

import support


def todo(message):
    raise NotImplementedError(message)


# 필수 1. 문서를 저장하고 현행 자료만 검색하기
def prepare_chunks(documents):
    chunks = []
    for document in documents:
        seen = set()
        number = 0
        for paragraph in document["paragraphs"]:
            text = " ".join(paragraph.split()) # paragraph는 support.py의 load_documents()보면 됨.
            if not text or text == "KANT NEXT | 내부 문서" or text in seen:
                continue
            seen.add(text)
            chunk = {
                "document_id" : document["document_id"],
                "title" : document["title"],
                "category" : document["category"],
                "status" : document["status"],
                "source" : document["source"],
                "chunk_id" : f"{document["document_id"]}:{number}",
                "text" : text,
            }
            chunks.append(chunk)
            number += 1
    # 이유: 문단을 유지하는 이유와 보존해야 할 메타데이터를 한두 줄로 적으세요.
    # 예를들어 data/raw/vpn.txt를 보면 문단이 짧고 규칙과 절차를 같이 설명하기 때문에
    #  문단을 유지해야하고 출처를 쉽게 찾기위해 보존해야 할 메타데이터는 document_id, title, category, status, source이다.
    return chunks


def build_index(chunks, embedder):
    texts = ["passage: " + row["title"] + "\n" + row["text"] for row in chunks]
    vectors = embedder.encode(texts, normalize_embeddings=True)
    #("texts를 정규화된 문서 벡터로 바꾸세요.")
    client = support.empty_store(len(vectors[0]))
    points = []
    for i, (row, vector) in enumerate(zip(chunks, vectors, strict=True)):
        point = models.PointStruct(
            id=i,
            vector=list(vector),
            payload=row,
        )
        #("i, vector, row를 Qdrant PointStruct에 연결하세요.")
        points.append(point)
    client.upsert(collection_name="devdesk", points=points, wait=True)
    return client


def search(client, embedder, question, category, top_k=2):
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise ValueError("top_k는 1~5의 정수여야 합니다.")
    vector = embedder.encode(["query: " + question], normalize_embeddings=True)[0]
    scope = models.Filter(
        must=[
            models.FieldCondition(
                key="status",
                match=models.MatchValue(value="current"),
            ),
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value=category)
            )
        ]
    )
    #("현행 문서이면서 지정한 category인 Qdrant 필터를 만드세요.")
    hits = client.query_points(collection_name="devdesk", query=list(vector),
                               query_filter=scope, limit=top_k, with_payload=True).points
    return [{**hit.payload, "score": hit.score} for hit in hits]


# 필수 2. 별칭 검색을 개선하고 답변을 비교하기
def rewrite_query(question, aliases):
    rewritten = question
    for alias, formal_name in aliases.items():
        rewritten = rewritten.replace(alias, formal_name)
        #("현재 문자열에서 alias를 formal_name으로 바꾸세요.")
    return rewritten


def answer_question(question, rows, generate):
    if not rows:
        return {"answer": "확인할 문서가 없습니다.", "citations": [], "needs_human": True}
    context = "\n\n".join(
        f"[{row['chunk_id']}] {row['text']}"
        for row in rows
    )
    #("각 검색 결과를 [chunk_id] 본문으로 묶고 빈 줄로 연결하세요.")
    reply = support.validate_shape(generate(question, context))
    allowed = {row["chunk_id"] for row in rows}
    if any(citation not in allowed for citation in reply["citations"]): 
    #("검색 결과에 없는 출처가 하나라도 있는지 검사하세요."):
        raise ValueError("검색하지 않은 출처가 있습니다.")
    if reply["needs_human"] == bool(reply["citations"]):
        raise ValueError("답변에는 출처가 필요하며 담당자 확인에는 출처를 비웁니다.")
    return reply


def make_golden():
    return [
        {
            "question_id": "custom-token-expiry",
            "question": "임시열쇠의 기본 만료 기간은 며칠인가요?",
            "category": "access",
            "reference_answer": "API 토큰의 기본 만료 기간은 30일입니다.",
            "relevant_document_ids": ["token"],
            "required_terms": ["30일"],
        },
        {
            "question_id": "custom-overseas-vpn",
            "question": "해외 지사의 VPN 승인 담당자는 누구인가요?",
            "category": "overseas",
            "reference_answer": "해외 지사의 VPN 승인 담당자를 확인할 자료가 없습니다.",
            "relevant_document_ids": [],
            "required_terms": [],
        },
    ]
# ("답이 있는 사례와 자료가 없는 사례를 하나씩 작성하세요.")


def measure(case, rows, reply):
    expected = set(case["relevant_document_ids"])
    found = {row["document_id"] for row in rows}
    recall = len(expected & found) / len(expected) if expected else None
    #("필요한 문서 중 찾은 비율을 계산하세요. 필요한 문서가 없으면 None입니다.")
    answer_ok = (all(term in reply["answer"] for term in case["required_terms"])
                 and not reply["needs_human"]) if expected else reply["needs_human"]
    failure = "없음"
    if expected and recall < 1:
        failure = "검색 누락"
    elif not answer_ok:
        failure = "답변 확인 필요" if expected else "보류 실패"

    # 별칭 변환 후 토큰 발급처·만료 기간 질문의 검색 점수가 올랐다.
    # 문서 Recall과 답변 확인은 전후 모두 1.0이었고, 개선·악화된 질문은 없었다.
    # 적용 이유: 임시열쇠를 문서의 정식 명칭인 API 토큰으로 바꾸니 발급처와 만료 기간 질문의 검색 점수가 올랐다.
    # 한계: 변환 전에도 같은 근거가 1위였고 답변도 같아서, 이번 평가에서는 Recall이나 답변 품질 개선을 확인하지 못했다.

    return {"document_recall": recall, "answer_check": bool(answer_ok), "failure": failure}


# 선택 심화 1. 두 검색 순위를 합쳐 근거를 모으기
def fuse_rankings(rankings, top_k=2):
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise ValueError("top_k는 1~5의 정수여야 합니다.")

    merged = {}

    for ranking in rankings:
        seen = set()
        rank = 0

        for row in ranking:
            chunk_id = row["chunk_id"]

            if chunk_id in seen:
                continue

            seen.add(chunk_id)
            rank = rank + 1

            if chunk_id not in merged:
                merged[chunk_id] = row.copy()
                merged[chunk_id]["score"] = 0.0

            score = 1 / (60 + rank)
            merged[chunk_id]["score"] = merged[chunk_id]["score"] + score

    def sort_key(row):
        return (-row["score"], row["chunk_id"])

    result = sorted(merged.values(), key=sort_key)

    # 두 검색에서 같은 청크의 순위 점수를 합쳐 한 번만 남겼다.
    # 두 검색에서 모두 1위였던 VPN 승인 근거(vpn:0)가 최종 1위를 유지했다.

    return result[:top_k]


if __name__ == "__main__":
    support.cli(globals())
