"""
agent/query_engine.py  — v2: hardened tenant isolation + compliance analysis

Security changes from v1:
  - customer_id is ALWAYS the outermost filter — never optional
  - _get_collection() validates collection name before access
  - TenantViolationError raised on any cross-tenant attempt
  - All filters built with customer_id as mandatory AND condition

New: ComplianceAnalysis mode
  - Accepts structured design parameters OR free-text spec excerpt
  - Runs a checklist against pinned standards
  - Returns per-item PASS / FAIL / NEEDS-REVIEW with citations
"""

import re
import json
import time
from dataclasses import dataclass, field
from enum import Enum

import anthropic
import chromadb
from openai import OpenAI


# ── Security ──────────────────────────────────────────────────────────────────

class TenantViolationError(Exception):
    """Raised when a query attempts to cross customer boundaries."""


SAFE_COLLECTION_RE = re.compile(r'^customer_[a-z0-9_]{1,55}$')


# ── Shared models ─────────────────────────────────────────────────────────────

@dataclass
class Citation:
    standard_name: str
    edition_year: int
    section_number: str
    section_title: str
    page_number: int
    relevant_excerpt: str
    doc_type: str = "standard"   # "standard" | "design_guide" | "proprietary"


@dataclass
class ProjectContext:
    customer_id: str
    project_id: str
    project_name: str
    pinned_standards: list[dict]   # [{"standard_name": ..., "edition_year": ...}, ...]


# ── Query answer ──────────────────────────────────────────────────────────────

@dataclass
class CitedAnswer:
    answer_text: str
    citations: list[Citation]
    standards_consulted: list[str]
    retrieved_chunk_count: int
    latency_ms: int
    warning: str = ""


# ── Compliance analysis models ────────────────────────────────────────────────

class ComplianceStatus(str, Enum):
    PASS         = "PASS"
    FAIL         = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_FOUND    = "NOT_FOUND"    # standard doesn't address this item


@dataclass
class ComplianceItem:
    requirement: str          # what was checked
    status: ComplianceStatus
    finding: str              # one-sentence explanation
    citations: list[Citation]
    calculated_value: str = ""   # e.g. "Required OA = 220 CFM"
    design_value: str = ""       # e.g. "Provided OA = 800 CFM"


@dataclass
class ComplianceReport:
    project_name: str
    standards_consulted: list[str]
    items: list[ComplianceItem]
    summary: str              # overall narrative
    latency_ms: int
    warning: str = ""

    @property
    def pass_count(self):   return sum(1 for i in self.items if i.status == ComplianceStatus.PASS)
    @property
    def fail_count(self):   return sum(1 for i in self.items if i.status == ComplianceStatus.FAIL)
    @property
    def review_count(self): return sum(1 for i in self.items if i.status == ComplianceStatus.NEEDS_REVIEW)


# ── System prompts ────────────────────────────────────────────────────────────

QUERY_SYSTEM_PROMPT = """You are a precise HVAC code and standards compliance assistant.

Answer using ONLY the document sections provided. Engineers verify your citations themselves.

RULES:
1. Only cite sections present in the retrieved context. Never use general knowledge.
2. If context is insufficient, say so — do not guess.
3. Every claim must include: standard name, edition year, section number.
4. Use exact section numbers from the source text.
5. When editions conflict, explicitly note the difference.
6. Do not interpret beyond what is explicitly stated.

FORMAT:
- Direct answer (2-3 sentences)
- Section-by-section breakdown
- End with: "Verify at: [Standard] [Year] § [Section]"

TONE: Professional, precise."""


ANALYSIS_SYSTEM_PROMPT = """You are an HVAC code compliance analyst. 

Given design parameters and retrieved code sections, produce a structured compliance checklist.

For each item you check, respond ONLY with a JSON array. No preamble, no markdown fences.

Each item must have:
{
  "requirement": "short description of what was checked",
  "status": "PASS" | "FAIL" | "NEEDS_REVIEW" | "NOT_FOUND",
  "finding": "one sentence explanation with numbers where applicable",
  "calculated_value": "the code-required value (or empty string)",
  "design_value": "the designer's provided value (or empty string)",
  "source_indices": [1, 3]   // which [Source N] items support this finding
}

RULES:
- PASS: design clearly meets the requirement
- FAIL: design clearly does not meet the requirement  
- NEEDS_REVIEW: requirement found but insufficient design data to determine compliance
- NOT_FOUND: the retrieved sections don't address this item at all
- Always include specific numbers from both the code and the design
- Never invent requirements not present in the retrieved sections
- Add a final item: {"requirement": "SUMMARY", "status": "NEEDS_REVIEW", 
  "finding": "Overall narrative of the compliance review", ...}"""


# ── Engine ─────────────────────────────────────────────────────────────────────

class QueryEngine:
    def __init__(self, db_path: str = "./chroma_db"):
        self.chroma    = chromadb.PersistentClient(path=db_path)
        self.oai       = OpenAI()
        self.ant       = anthropic.Anthropic()

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC: standard Q&A
    # ═══════════════════════════════════════════════════════════════════════════

    async def query(
        self,
        question: str,
        project_context: ProjectContext,
        top_k: int = 8,
    ) -> CitedAnswer:
        start = time.time()

        chunks = await self._retrieve(question, project_context, top_k)
        if chunks is None:
            return CitedAnswer(
                answer_text="No standards library found for your account.",
                citations=[], standards_consulted=[], retrieved_chunk_count=0,
                latency_ms=0, warning="Upload standards first.",
            )
        if not chunks:
            return CitedAnswer(
                answer_text="No relevant sections found in this project's standards.",
                citations=[], standards_consulted=[], retrieved_chunk_count=0,
                latency_ms=int((time.time()-start)*1000),
                warning="Check that the relevant standard is uploaded and pinned to this project.",
            )

        context_block = self._format_context(chunks)
        response = self.ant.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=QUERY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content":
                f"PROJECT: {project_context.project_name}\n\n"
                f"RETRIEVED SECTIONS:\n{context_block}\n\n"
                f"QUESTION: {question}"
            }],
        )

        return CitedAnswer(
            answer_text=response.content[0].text,
            citations=self._to_citations(chunks),
            standards_consulted=sorted({f"{c['standard_name']} {c['edition_year']}" for c in chunks}),
            retrieved_chunk_count=len(chunks),
            latency_ms=int((time.time()-start)*1000),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC: compliance analysis
    # ═══════════════════════════════════════════════════════════════════════════

    async def analyze(
        self,
        design_input: str,
        project_context: ProjectContext,
        top_k: int = 12,
    ) -> ComplianceReport:
        """
        Accepts either:
          - Structured params: "Space: open office, Area: 2000 sf, Occupancy: 20 people,
                                Supply CFM: 800, System: VAV with CO2 reset"
          - Pasted spec text: any excerpt from a design narrative or equipment schedule
          - Mixed: parameters + notes

        Returns a ComplianceReport with per-item PASS/FAIL/NEEDS_REVIEW.
        """
        start = time.time()

        # Use a broader search — compliance checks touch many sections
        search_query = f"HVAC compliance requirements for: {design_input[:500]}"
        chunks = await self._retrieve(search_query, project_context, top_k)

        if not chunks:
            return ComplianceReport(
                project_name=project_context.project_name,
                standards_consulted=[],
                items=[ComplianceItem(
                    requirement="Document retrieval",
                    status=ComplianceStatus.NOT_FOUND,
                    finding="No relevant standards sections found. Ensure standards are uploaded and pinned to this project.",
                    citations=[],
                )],
                summary="Analysis could not be completed — no matching standard sections retrieved.",
                latency_ms=int((time.time()-start)*1000),
                warning="Upload and pin relevant standards to this project first.",
            )

        context_block = self._format_context(chunks)
        response = self.ant.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content":
                f"PROJECT: {project_context.project_name}\n\n"
                f"RETRIEVED CODE SECTIONS:\n{context_block}\n\n"
                f"DESIGN INPUT TO ANALYZE:\n{design_input}"
            }],
        )

        raw = response.content[0].text.strip()
        items, summary, warning = self._parse_analysis(raw, chunks)

        standards_consulted = sorted({
            f"{c['standard_name']} {c['edition_year']}" for c in chunks
        })

        return ComplianceReport(
            project_name=project_context.project_name,
            standards_consulted=standards_consulted,
            items=items,
            summary=summary,
            latency_ms=int((time.time()-start)*1000),
            warning=warning,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE: retrieval (all tenant isolation lives here)
    # ═══════════════════════════════════════════════════════════════════════════

    async def _retrieve(
        self,
        text: str,
        ctx: ProjectContext,
        top_k: int,
    ) -> list[dict] | None:
        """
        Returns chunks or None (collection not found).
        customer_id is ALWAYS enforced as the outer AND condition.
        """
        collection = self._get_collection(ctx.customer_id)
        if collection is None:
            return None

        count = collection.count()
        if count == 0:
            return []

        embedding = self._embed(text)

        # ── SECURITY: customer_id is the mandatory outer filter ───────────────
        # Even if pinned_standards is empty, we NEVER drop the customer lock.
        standards_filter = self._build_standards_filter(ctx)

        where: dict
        if standards_filter:
            where = {"$and": [
                {"customer_id": {"$eq": ctx.customer_id}},   # ← hard lock, always present
                standards_filter,
            ]}
        else:
            # No standards pinned — search all of this customer's documents
            where = {"customer_id": {"$eq": ctx.customer_id}}

        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return self._parse_results(results)

    def _get_collection(self, customer_id: str):
        """
        Validates collection name before access.
        Returns None if collection doesn't exist yet (not an error).
        Raises TenantViolationError if customer_id looks malformed.
        """
        # Sanitise
        safe_id = re.sub(r'[^a-z0-9]', '_', customer_id.lower())
        collection_name = f"customer_{safe_id}"[:63]

        if not SAFE_COLLECTION_RE.match(collection_name):
            raise TenantViolationError(
                f"Invalid customer_id produces unsafe collection name: {collection_name!r}"
            )

        try:
            return self.chroma.get_collection(collection_name)
        except Exception:
            return None   # doesn't exist yet — caller handles

    def _build_standards_filter(self, ctx: ProjectContext) -> dict | None:
        """
        Returns the standards-version filter (WITHOUT customer_id —
        that's added as the outer AND in _retrieve).
        Returns None if no standards are pinned (caller searches all customer docs).
        """
        if not ctx.pinned_standards:
            return None

        conditions = []
        for std in ctx.pinned_standards:
            conditions.append({"$and": [
                {"standard_name": {"$eq": std["standard_name"]}},
                {"edition_year":  {"$eq": std["edition_year"]}},
                {"project_id":    {"$in": [ctx.project_id, "global"]}},
            ]})

        return conditions[0] if len(conditions) == 1 else {"$or": conditions}

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE: utilities
    # ═══════════════════════════════════════════════════════════════════════════

    def _embed(self, text: str) -> list[float]:
        r = self.oai.embeddings.create(model="text-embedding-3-small", input=text)
        return r.data[0].embedding

    def _parse_results(self, results: dict) -> list[dict]:
        chunks = []
        if not results["documents"] or not results["documents"][0]:
            return chunks
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            if dist > 0.72:   # cosine distance threshold
                continue
            chunks.append({
                "text":           text,
                "standard_name":  meta.get("standard_name", "Unknown"),
                "edition_year":   meta.get("edition_year", 0),
                "section_number": meta.get("section_number", "—"),
                "section_title":  meta.get("section_title", ""),
                "page_number":    meta.get("page_number", 0),
                "doc_type":       meta.get("doc_type", "standard"),
                "relevance":      round(1 - dist, 3),
            })
        return chunks

    def _format_context(self, chunks: list[dict]) -> str:
        parts = []
        for i, c in enumerate(chunks, 1):
            hdr = f"[Source {i}] {c['standard_name']} {c['edition_year']} § {c['section_number']}"
            if c["section_title"]:
                hdr += f" — {c['section_title']}"
            hdr += f" (Page {c['page_number']})"
            parts.append(f"{hdr}\n{c['text']}")
        return "\n\n---\n\n".join(parts)

    def _to_citations(self, chunks: list[dict]) -> list[Citation]:
        return [
            Citation(
                standard_name=c["standard_name"],
                edition_year=c["edition_year"],
                section_number=c["section_number"],
                section_title=c["section_title"],
                page_number=c["page_number"],
                relevant_excerpt=c["text"][:400] + ("…" if len(c["text"]) > 400 else ""),
                doc_type=c.get("doc_type", "standard"),
            )
            for c in chunks
        ]

    def _parse_analysis(
        self, raw: str, chunks: list[dict]
    ) -> tuple[list[ComplianceItem], str, str]:
        """Parse Claude's JSON response into ComplianceItem list."""
        warning = ""
        try:
            clean = re.sub(r"```(?:json)?|```", "", raw).strip()
            data: list[dict] = json.loads(clean)
        except json.JSONDecodeError:
            warning = "Analysis response could not be parsed as JSON — showing raw output."
            fallback = ComplianceItem(
                requirement="Raw analysis",
                status=ComplianceStatus.NEEDS_REVIEW,
                finding=raw[:1000],
                citations=[],
            )
            return [fallback], raw[:500], warning

        items: list[ComplianceItem] = []
        summary = ""

        for entry in data:
            req = entry.get("requirement", "")
            if req == "SUMMARY":
                summary = entry.get("finding", "")
                continue

            # Map source indices back to real citations
            source_indices = entry.get("source_indices", [])
            item_citations = []
            for idx in source_indices:
                chunk_idx = idx - 1   # source indices are 1-based
                if 0 <= chunk_idx < len(chunks):
                    c = chunks[chunk_idx]
                    item_citations.append(Citation(
                        standard_name=c["standard_name"],
                        edition_year=c["edition_year"],
                        section_number=c["section_number"],
                        section_title=c["section_title"],
                        page_number=c["page_number"],
                        relevant_excerpt=c["text"][:300],
                        doc_type=c.get("doc_type", "standard"),
                    ))

            try:
                status = ComplianceStatus(entry.get("status", "NEEDS_REVIEW"))
            except ValueError:
                status = ComplianceStatus.NEEDS_REVIEW

            items.append(ComplianceItem(
                requirement=req,
                status=status,
                finding=entry.get("finding", ""),
                calculated_value=entry.get("calculated_value", ""),
                design_value=entry.get("design_value", ""),
                citations=item_citations,
            ))

        return items, summary, warning
