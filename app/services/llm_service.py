"""
LLM service — Groq API with Llama 4 Scout 17B.
"""
from __future__ import annotations
from functools import lru_cache
from typing import List

from groq import AsyncGroq
from loguru import logger

from app.core.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are HealthMind, an expert medical knowledge assistant.
You must answer accurately, conservatively, and only from the provided context.

Rules:
- Ground every factual claim in the provided sources only.
- If the context is incomplete or conflicting, say so plainly.
- Synthesize across multiple sources when possible instead of relying on one excerpt.
- Prefer clear, clinically useful wording over vague summaries.
- Keep the answer short by default: 2-4 sentences for ordinary questions.
- Use bullets only when the user asks for a list or when brevity would be worse.
- Do not mention internal retrieval labels like "Source 1" or "Source 2" in the answer.
- Cite source titles inline only when needed for an important claim or ambiguity.
- Never invent guidelines, dosages, diagnoses, or recommendations not supported by context.
- Do not add a generic safety disclaimer unless the answer includes urgent-risk advice, diagnosis, treatment guidance, or the context specifically calls for it.

Style:
- Start with the direct answer immediately.
- Avoid headings like "Direct answer", "Key details", or "Source-backed notes".
- Avoid bracketed citations and source-number references in the prose.
- Avoid padded phrasing and repetition.
- If the user asks a simple definition, respond in one short paragraph."""


class LLMService:
    def __init__(self) -> None:
        self._client = AsyncGroq(api_key=settings.groq_api_key)

    def _build_context(self, chunks: List[dict]) -> str:
        parts = []
        for i, c in enumerate(chunks, 1):
            page_label = f" | page {c.get('page_number')}" if c.get("page_number") else ""
            parts.append(
                f"[Document {i}: {c['title']} | {c['filename']}{page_label} | chunk {c.get('chunk_index', 0)}]\n"
                f"{c['text']}"
            )
        return "\n\n---\n\n".join(parts)

    async def rewrite_query_for_retrieval(self, query: str, conversation_history: List[dict]) -> str:
        if not conversation_history:
            return query

        history_text = "\n".join(
            f"{item['role']}: {item['content']}" for item in conversation_history if item.get("content")
        )
        response = await self._client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite the user's latest question into a standalone medical search query. "
                        "Preserve key medical entities, symptoms, conditions, tests, and follow-up references. "
                        "Return only the rewritten search query."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Conversation:\n{history_text}\n\nLatest user question:\n{query}",
                },
            ],
            max_tokens=96,
            temperature=0.0,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        return rewritten or query

    async def generate_answer(self, query: str, context_chunks: List[dict]) -> str:
        context = self._build_context(context_chunks)
        try:
            response = await self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Question:\n{query}\n\n"
                            f"Retrieved medical context:\n{context}\n\n"
                            "Answer the question using only the retrieved context. Keep it concise unless the user explicitly asks for more detail."
                        ),
                    },
                ],
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
            answer = (response.choices[0].message.content or "").strip()
            if not answer:
                raise RuntimeError("LLM returned an empty answer")
            return answer
        except Exception as e:
            logger.error(f"Error generating RAG answer: {e}")
            raise

    async def generate_simple_response(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """
        Generates a simple response without RAG context.
        """
        try:
            response = await self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            return f"Error: {e}"

    async def health(self) -> str:
        try:
            r = await self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return "ok"
        except Exception as exc:
            return f"error: {exc}"

    async def check_if_medical_document(self, text: str) -> bool:
        """
        Validates if the provided text chunk belongs to a medical-related document.
        Returns True if medical, False otherwise.
        """
        prompt = (
            "You are an automated medical document classifier. "
            "Determine if the following text is from a medical-related document "
            "(e.g., medical research, clinical guidelines, patient records, health articles, anatomy, etc.). "
            "Respond strictly with 'YES' or 'NO' and no other text.\n\n"
            f"Text snippet:\n{text[:3000]}"
        )
        try:
            response = await self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0,
            )
            answer = (response.choices[0].message.content or "").strip().upper()
            if "YES" in answer:
                return True
            return False
        except Exception as e:
            logger.error(f"Error validating medical document: {e}")
            # In case of LLM error, default to True so we don't accidentally drop valid documents
            return True


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return LLMService()
