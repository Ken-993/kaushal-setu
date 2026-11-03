"""Resume reader: turns an uploaded resume into skills + years of experience.

Privacy: the file is read from memory and never written to disk or sent anywhere.

Steps
  1. extract_text   PDF (pypdf), Word .docx (python-docx) or plain .txt  ->  one long string
  2. find_skills    look for every skill the models know (the vocabulary learned from the
                    Analytics postings) as a whole word/phrase in the text
  3. find_years     "5 years", "3+ yrs" ... or, failing that, date ranges like "2019 - Present"
The matching is keyword based, so it only finds skills written the way job postings write them.
"""
import io
import re
from datetime import date

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED = {".pdf", ".docx", ".txt"}

# Very short vocabulary words that are also ordinary English or initials; matched only in
# UPPER CASE as a stand-alone word (so "R" counts but "r" inside "for" or "a r" does not).
SHORT_CASE_SENSITIVE = {"r", "c", "go", "ai", "ml", "bi", "qa", "hr", "it", "ui", "ux"}
# Vocabulary entries that are too generic to count as a skill on a resume.
IGNORE = {"analytics", "analytical", "analysis", "analyst", "learning", "operations", "research", "it", "outsourcing", "management",
          "consulting", "strategy", "communication", "data", "business", "development"}

# Common resume spellings -> the token used in job postings
ALIASES = {
    "scikit-learn": "machine learning", "sklearn": "machine learning", "pytorch": "deep learning",
    "tensorflow": "deep learning", "keras": "deep learning", "powerbi": "power bi", "ms excel": "excel",
    "microsoft excel": "excel", "natural language processing": "nlp", "postgresql": "sql", "mysql": "mysql",
    "pyspark": "spark", "apache spark": "spark", "statistics": "statistics", "a/b testing": "statistics",
}


class ResumeError(ValueError):
    """Raised with a message the user can act on (shown on the website)."""


def extract_text(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    ext = name[name.rfind("."):] if "." in name else ""
    if ext not in ALLOWED:
        raise ResumeError(f"Upload a .pdf, .docx or .txt file (got '{ext or filename}'). "
                          "Old .doc files: open in Word and save as .docx.")
    if len(content) > MAX_BYTES:
        raise ResumeError("The file is larger than 5 MB. Upload a smaller copy of your resume.")
    if ext == ".txt":
        return content.decode("utf-8", errors="ignore")
    if ext == ".docx":
        from docx import Document
        try:
            doc = Document(io.BytesIO(content))
        except Exception:
            raise ResumeError("This .docx file could not be opened. Re-save it from Word and try again.")
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:  # many resume templates put skills in tables
            for row in table.rows:
                parts.extend(cell.text for cell in row.cells)
        return "\n".join(parts)
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        raise ResumeError("This PDF could not be read. Export it again as PDF, or upload the .docx version.")


def _pattern(token: str) -> re.Pattern:
    if token in SHORT_CASE_SENSITIVE:
        return re.compile(rf"(?<![\w&/.-]){re.escape(token.upper())}(?![\w&/-])")
    body = r"[\s\-_/]*".join(re.escape(w) for w in token.split())  # "power bi" also matches "Power-BI"
    return re.compile(rf"(?<![\w]){body}(?![\w])", re.I)


_cache: dict = {}


def find_skills(text: str, vocabulary: list[str]) -> list[str]:
    key = id(vocabulary)
    if key not in _cache:
        tokens = sorted((t for t in vocabulary if t not in IGNORE), key=len, reverse=True)
        _cache[key] = [(t, _pattern(t)) for t in tokens]
    # longest phrases first; each match is blanked out so its words are not matched again on their
    # own ("machine learning" must not also produce "learning", but a separate "SQL" still counts)
    work, found = text, set()
    for t, rx in _cache[key]:
        if rx.search(work):
            found.add(t)
            work = rx.sub(lambda m: " " * len(m.group(0)), work)
    low = text.lower()
    for alias, token in ALIASES.items():
        if alias in low and token in vocabulary:
            found.add(token)
    return sorted(found)


YEARS_RX = re.compile(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+\w+){0,3}\s+experience|"
                      r"experience\s*(?:of|:)?\s*(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", re.I)
EDU_RX = re.compile(r"b\.?\s?tech|b\.?\s?sc|b\.?\s?e\b|b\.?\s?com|bca|mca|m\.?\s?tech|m\.?\s?sc|mba|bachelor|master|"
                    r"university|college|school|degree|diploma|class (?:x|xii|10|12)|cgpa|gpa", re.I)
RANGE_RX = re.compile(r"((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current|now|till date|date)", re.I)


def find_years(text: str) -> dict:
    hits = [float(a or b) for a, b in YEARS_RX.findall(text)]
    hits = [h for h in hits if 0 <= h <= 45]
    if hits:
        return {"years": max(hits), "source": "stated in the resume (e.g. '5 years of experience')"}
    this_year = date.today().year
    spans = []
    work_lines = "\n".join(l for l in text.splitlines() if not EDU_RX.search(l))
    for start, end in RANGE_RX.findall(work_lines):
        s = int(start)
        e = this_year if not end[0].isdigit() else int(end)
        if 1970 <= s <= e <= this_year:
            spans.append((s, e))
    if spans:
        # merge overlapping ranges so two parallel jobs are not counted twice
        spans.sort()
        merged = [list(spans[0])]
        for s, e in spans[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        total = sum(e - s for s, e in merged)
        return {"years": float(min(total, 45)),
                "source": "added up from job date ranges (lines about education are skipped; check it)"}
    return {"years": 0.0, "source": "not found, assumed 0 (fresher); change it on the page if wrong"}
