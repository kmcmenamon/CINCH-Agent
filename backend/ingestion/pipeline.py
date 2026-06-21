"""
ingestion/pipeline.py  — v3: Uses pdfplumber instead of fitz to avoid Windows DLL issues

Changes from v2:
  - Replaced fitz (PyMuPDF) with pdfplumber
  - pdfplumber is pure Python, no compilation needed
  - Works identically on Windows, Mac, Linux
"""

import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
import chromadb
from openai import OpenAI


@dataclass
class StandardChunk:
    text: str
    standard_name: str
    edition_year: int
    section_number: str
    section_title: str
    page_number: int
    customer_id: str
    project_id: str
    doc_hash: str
    doc_type: str = "standard"
    chunk_id: str = field(init=False)

    def __post_init__(self):
        raw = f"{self.doc_hash}:{self.section_number}:{self.text[:100]}"
        self.chunk_id = hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass
class IngestionResult:
    standard_name: str
    edition_year: int
    total_chunks: int
    total_pages: int
    doc_hash: str
    skipped_chunks: int = 0
    errors: list[str] = field(default_factory=list)


SECTION_PATTERN = re.compile(
    r'^(?:'
    r'\d+\.\d[\d.]*'
    r'|[A-Z][1-9]\d*\.\d+'
    r'|(?:Section|SECTION)\s+\d+'
    r'|(?:Chapter|CHAPTER)\s+\d+'
    r'|(?:Appendix|APPENDIX)\s+[A-Z\d]+'
    r')',
    re.MULTILINE,
)

MIN_CHUNK_CHARS = 150
MAX_CHUNK_CHARS = 2000

SAFE_COLLECTION_RE = re.compile(r'^customer_[a-z0-9_]{1,55}$')


class IngestionPipeline:
    def __init__(self, db_path: str = "./chroma_db"):
        self.chroma = chromadb.PersistentClient(path=db_path)
        self.openai = OpenAI()

    async def ingest(
        self,
        pdf_path: str,
        standard_name: str,
        edition_year: int,
        customer_id: str,
        project_id: str = "global",
        doc_type: str = "standard",
    ) -> IngestionResult:
        path     = Path(pdf_path)
        doc_hash = self._hash_file(path)

        raw_chunks = self._extract_chunks(
            path, standard_name, edition_year,
            customer_id, project_id, doc_hash, doc_type
        )
        valid   = [c for c in raw_chunks if len(c.text) >= MIN_CHUNK_CHARS]
        skipped = len(raw_chunks) - len(valid)
        errors  = self._upsert_to_chroma(valid, customer_id) if valid else []

        return IngestionResult(
            standard_name=standard_name,
            edition_year=edition_year,
            total_chunks=len(valid),
            total_pages=self._page_count(path),
            doc_hash=doc_hash,
            skipped_chunks=skipped,
            errors=errors,
        )

    def _extract_chunks(self, path, standard_name, edition_year,
                        customer_id, project_id, doc_hash, doc_type):
        """
        Extract text from PDF using pdfplumber.
        pdfplumber extracts text page by page and preserves structure.
        """
        chunks = []
        cur_sec_num   = "Preamble"
        cur_sec_title = ""
        cur_parts     = []
        cur_page      = 1

        try:
            with pdfplumber.open(str(path)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text from page
                    text = page.extract_text()
                    if not text:
                        continue

                    # Split by lines and process
                    for line in text.split('\n'):
                        line = line.strip()
                        if not line:
                            continue

                        # Detect if this line is a section heading
                        detected = self._detect_heading(line)
                        if detected:
                            # Save current accumulation as a chunk
                            if cur_parts:
                                full = " ".join(cur_parts).strip()
                                for sub in self._split_if_long(full):
                                    chunks.append(StandardChunk(
                                        text=sub, standard_name=standard_name,
                                        edition_year=edition_year,
                                        section_number=cur_sec_num,
                                        section_title=cur_sec_title,
                                        page_number=cur_page,
                                        customer_id=customer_id,
                                        project_id=project_id,
                                        doc_hash=doc_hash,
                                        doc_type=doc_type,
                                    ))
                            # Start new section
                            cur_sec_num, cur_sec_title = detected
                            cur_parts = []
                            cur_page  = page_num
                        else:
                            cur_parts.append(line)

            # Don't forget the last section
            if cur_parts:
                full = " ".join(cur_parts).strip()
                for sub in self._split_if_long(full):
                    chunks.append(StandardChunk(
                        text=sub, standard_name=standard_name,
                        edition_year=edition_year,
                        section_number=cur_sec_num, section_title=cur_sec_title,
                        page_number=cur_page, customer_id=customer_id,
                        project_id=project_id, doc_hash=doc_hash, doc_type=doc_type,
                    ))
        except Exception as e:
            # If PDF extraction fails, return empty list (caller will handle)
            print(f"Error extracting PDF: {e}")
            return chunks

        return chunks

    def _detect_heading(self, text: str) -> Optional[tuple[str, str]]:
        """Detect if a line is a section heading (e.g., '6.2.1', 'Section 5')."""
        first = text.split('\n')[0].strip()
        m = SECTION_PATTERN.match(first)
        if not m:
            return None
        sec_num   = m.group(0).strip()
        sec_title = first[len(sec_num):].strip(" .-–")
        return sec_num, sec_title

    def _split_if_long(self, text: str) -> list[str]:
        """Split oversized chunks at paragraph boundaries."""
        if len(text) <= MAX_CHUNK_CHARS:
            return [text]
        chunks, cur = [], ""
        for para in text.split('\n\n'):
            if len(cur) + len(para) > MAX_CHUNK_CHARS and cur:
                chunks.append(cur.strip())
                cur = para
            else:
                cur += "\n\n" + para
        if cur.strip():
            chunks.append(cur.strip())
        return chunks or [text]

    def _upsert_to_chroma(self, chunks: list[StandardChunk], customer_id: str) -> list[str]:
        """Store chunks in ChromaDB with metadata."""
        # Validate collection name
        safe_id = re.sub(r'[^a-z0-9]', '_', customer_id.lower())
        collection_name = f"customer_{safe_id}"[:63]
        if not SAFE_COLLECTION_RE.match(collection_name):
            return [f"Invalid customer_id: {customer_id}"]

        collection = self.chroma.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        errors = []
        BATCH  = 100
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i+BATCH]
            try:
                texts = [c.text for c in batch]
                resp  = self.openai.embeddings.create(
                    model="text-embedding-3-small", input=texts
                )
                collection.upsert(
                    ids=[c.chunk_id for c in batch],
                    embeddings=[e.embedding for e in resp.data],
                    documents=texts,
                    metadatas=[{
                        "standard_name":  c.standard_name,
                        "edition_year":   c.edition_year,
                        "section_number": c.section_number,
                        "section_title":  c.section_title,
                        "page_number":    c.page_number,
                        "project_id":     c.project_id,
                        "doc_hash":       c.doc_hash,
                        "doc_type":       c.doc_type,
                        "customer_id":    c.customer_id,
                    } for c in batch],
                )
            except Exception as e:
                errors.append(f"Batch {i//BATCH}: {e}")
        return errors

    @staticmethod
    def _hash_file(path: Path) -> str:
        """SHA-256 hash of file for deduplication."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _page_count(path: Path) -> int:
        """Count pages in PDF."""
        try:
            with pdfplumber.open(str(path)) as pdf:
                return len(pdf.pages)
        except Exception:
            return 0
