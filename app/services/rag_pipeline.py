"""
RAG pipeline: conversational rewrite -> hybrid retrieve -> rerank -> generate -> persist.
"""
from __future__ import annotations
from collections import defaultdict
import json
import time

from app.core.config import get_settings
from app.schemas.schemas import QueryRequest, QueryResponse, SourceChunk
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import RetrievedChunk, get_qdrant_service
from app.services.reranker_service import get_reranker_service
from app.services.llm_service import get_llm_service
from app.db import chat_db

settings = get_settings()


def _diversify_ranked_results(ranked: list[tuple], top_k: int) -> list[tuple]:
    """Keep the final context from being dominated by one document."""
    per_doc_counts = defaultdict(int)
    diversified = []

    for point, score in ranked:
        doc_id = str(point.payload.get("doc_id", ""))
        if per_doc_counts[doc_id] >= settings.reranker_max_chunks_per_doc:
            continue
        diversified.append((point, score))
        per_doc_counts[doc_id] += 1
        if len(diversified) >= top_k:
            break

    return diversified


def _filter_ranked_results_by_score(ranked: list[tuple], min_score: float) -> list[tuple]:
    return [(point, score) for point, score in ranked if float(score) >= min_score]


def _filter_ranked_results_by_top_window(ranked: list[tuple], window: float) -> list[tuple]:
    if not ranked:
        return []
    top_score = float(ranked[0][1])
    min_allowed = top_score - window
    return [(point, score) for point, score in ranked if float(score) >= min_allowed]


def _build_conversation_history(messages: list, max_turns: int) -> list[dict]:
    recent = messages[-max_turns:] if max_turns > 0 else []
    return [{"role": msg.role, "content": msg.content} for msg in recent]


def _hybrid_merge(vector_hits: list[RetrievedChunk], lexical_hits: list[RetrievedChunk]) -> list[RetrievedChunk]:
    merged: dict[str, RetrievedChunk] = {}
    rrf_k = settings.rag_hybrid_rrf_k

    for rank, item in enumerate(vector_hits, start=1):
        existing = merged.get(item.id)
        contribution = 1.0 / (rrf_k + rank)
        if existing is None:
            item.hybrid_score = contribution
            item.retrieval_methods = {"vector"}
            merged[item.id] = item
        else:
            existing.vector_score = item.vector_score
            existing.hybrid_score = (existing.hybrid_score or 0.0) + contribution
            existing.retrieval_methods.add("vector")

    for rank, item in enumerate(lexical_hits, start=1):
        existing = merged.get(item.id)
        contribution = 1.0 / (rrf_k + rank)
        if existing is None:
            item.hybrid_score = contribution
            item.retrieval_methods = {"lexical"}
            merged[item.id] = item
        else:
            existing.lexical_score = item.lexical_score
            existing.hybrid_score = (existing.hybrid_score or 0.0) + contribution
            existing.retrieval_methods.add("lexical")

    merged_hits = list(merged.values())
    for item in merged_hits:
        item.score = float(item.hybrid_score or 0.0)
        if item.retrieval_methods == {"vector", "lexical"}:
            item.retrieval_method = "hybrid"
        elif "lexical" in item.retrieval_methods:
            item.retrieval_method = "lexical"
        else:
            item.retrieval_method = "vector"

    merged_hits.sort(key=lambda item: item.hybrid_score or 0.0, reverse=True)
    return merged_hits


async def run_rag_pipeline(request: QueryRequest, user_id: str) -> QueryResponse:
    emb_svc = get_embedding_service()
    qdrant = get_qdrant_service()
    reranker = get_reranker_service()
    llm = get_llm_service()

    history_messages = await chat_db.get_messages(user_id, request.conversation_id)
    conversation_history = _build_conversation_history(history_messages, settings.rag_conversation_history_turns)
    search_query = await llm.rewrite_query_for_retrieval(request.query, conversation_history)

    t0 = time.perf_counter()
    query_vector = await emb_svc.embed_query(search_query)
    vector_hits = await qdrant.vector_search(
        query_vector=query_vector,
        top_k=settings.rag_retrieval_top_k,
        conversation_id=request.conversation_id,
    )
    lexical_hits = await qdrant.lexical_search(
        query=search_query,
        top_k=settings.rag_retrieval_top_k,
        conversation_id=request.conversation_id,
    )
    candidates = _hybrid_merge(vector_hits, lexical_hits)
    t_retrieval = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    requested_top_k = request.top_k or settings.reranker_top_k
    ranked = await reranker.rerank(
        query=search_query,
        candidates=candidates,
        text_fn=lambda c: c.payload.get("text", ""),
        top_k=max(requested_top_k * 3, settings.reranker_top_k),
    )
    ranked = _filter_ranked_results_by_score(ranked, settings.reranker_min_score)
    ranked = _filter_ranked_results_by_top_window(ranked, settings.reranker_score_window)
    ranked = _diversify_ranked_results(ranked, requested_top_k)
    t_rerank = (time.perf_counter() - t1) * 1000

    if ranked:
        context_chunks = [
            {
                "text": point.payload.get("text", ""),
                "title": point.payload.get("title", ""),
                "filename": point.payload.get("filename", ""),
                "doc_id": point.payload.get("doc_id", ""),
                "chunk_index": point.payload.get("chunk_index", 0),
                "page_number": point.payload.get("page_number"),
                "score": float(score),
                "retrieval_method": getattr(point, "retrieval_method", "hybrid"),
            }
            for point, score in ranked
        ]
        no_results = False
    elif candidates:
        # Fallback for broad prompts (e.g., "summarize these documents"):
        # if reranker filters out everything, still pass top retrieved chunks to the LLM.
        fallback_hits = candidates[:requested_top_k]
        context_chunks = [
            {
                "text": item.payload.get("text", ""),
                "title": item.payload.get("title", ""),
                "filename": item.payload.get("filename", ""),
                "doc_id": item.payload.get("doc_id", ""),
                "chunk_index": item.payload.get("chunk_index", 0),
                "page_number": item.payload.get("page_number"),
                "score": float(item.score or 0.0),
                "retrieval_method": getattr(item, "retrieval_method", "hybrid"),
            }
            for item in fallback_hits
        ]
        no_results = False
    else:
        context_chunks = []
        no_results = True

    t2 = time.perf_counter()
    if no_results:
        answer = (
            "I couldn't find relevant information in the knowledge base "
            "to answer your question. Please ensure relevant medical documents "
            "have been uploaded, or rephrase your question."
        )
    else:
        answer = await llm.generate_answer(request.query, context_chunks)
    t_gen = (time.perf_counter() - t2) * 1000

    sources = [
        SourceChunk(
            doc_id=c["doc_id"],
            filename=c["filename"],
            title=c["title"],
            chunk_index=c["chunk_index"],
            page_number=c.get("page_number"),
            text=c["text"],
            score=round(c["score"], 4),
            retrieval_method=c.get("retrieval_method"),
        )
        for c in context_chunks
    ]

    await chat_db.add_message(
        user_id=user_id,
        conv_id=request.conversation_id,
        role="user",
        content=request.query,
    )

    sources_json = json.dumps([s.model_dump() for s in sources])
    meta_json = json.dumps({
        "model": settings.llm_model,
        "search_query": search_query,
        "retrieval_strategy": "conversational-hybrid-rag+rerank",
        "conversation_turns_used": len(conversation_history),
        "retrieval_ms": round(t_retrieval, 2),
        "rerank_ms": round(t_rerank, 2),
        "generation_ms": round(t_gen, 2),
        "source_count": len(sources),
        "vector_candidates": len(vector_hits),
        "lexical_candidates": len(lexical_hits),
        "reranker_min_score": settings.reranker_min_score,
        "reranker_score_window": settings.reranker_score_window,
    })
    asst_msg = await chat_db.add_message(
        user_id=user_id,
        conv_id=request.conversation_id,
        role="assistant",
        content=answer,
        sources_json=sources_json,
        meta_json=meta_json,
    )

    messages = await chat_db.get_messages(user_id, request.conversation_id)
    if len(messages) <= 2:
        await chat_db.auto_title_conversation(user_id, request.conversation_id, request.query)

    return QueryResponse(
        message_id=asst_msg.id,
        conversation_id=request.conversation_id,
        query=request.query,
        search_query=search_query,
        answer=answer,
        sources=sources,
        model=settings.llm_model,
        retrieval_strategy="conversational-hybrid-rag+rerank",
        conversation_turns_used=len(conversation_history),
        retrieval_ms=round(t_retrieval, 2),
        rerank_ms=round(t_rerank, 2),
        generation_ms=round(t_gen, 2),
    )
