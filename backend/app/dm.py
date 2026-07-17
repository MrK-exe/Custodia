"""Direct messages with seeded personas, and sharing an article into a thread.

No auth and no LLM, both by decision. The personas do not reply: a persona that
answered would either need an LLM (out of scope for 1.0) or would be putting words
in a fictional analyst's mouth, which is exactly the kind of fabricated content this
project already removed once. They are seeded colleagues you can send research to,
and the UI badges the whole surface as sample data so nobody mistakes them for real
users.

Sharing is the point: search finds the document, DM is how it reaches a colleague.
A shared message stores only doc_id, so the rendered card always reflects the
document as it is now rather than a copy that silently goes stale.
"""
import time

from .storage import db

PERSONAS = [
    {
        "id": "sara",
        "name_ar": "سارة الغامدي",
        "name_en": "Sara Alghamdi",
        "role_ar": "محللة قطاع الطاقة",
        "role_en": "Energy sector analyst",
    },
    {
        "id": "khalid",
        "name_ar": "خالد العتيبي",
        "name_en": "Khalid Alotaibi",
        "role_ar": "مدير محفظة",
        "role_en": "Portfolio manager",
    },
    {
        "id": "noura",
        "name_ar": "نورة القحطاني",
        "name_en": "Noura Alqahtani",
        "role_ar": "محللة قطاع البنوك",
        "role_en": "Banking sector analyst",
    },
]

# Opening lines only, so a thread is not an empty box on screen. Deliberately about
# what to look at, never a view on a security: an assistant that appears to give
# investment advice changes the product's regulatory category (CMA "Advising").
_SEED_MESSAGES = {
    "sara": "لو لقيت شيء جديد عن عقود الغاز غير التقليدي، ابعثه لي هنا.",
    "khalid": "أتابع نتائج الربع الثاني. شاركني أي إفصاح مهم.",
    "noura": "أي خبر عن رأس مال البنوك يهمني.",
}


def ensure_seeded() -> None:
    """Idempotent. Safe to call on every startup."""
    with db.connect() as conn:
        for persona in PERSONAS:
            conn.execute(
                """INSERT OR IGNORE INTO dm_personas
                   (id, name_ar, name_en, role_ar, role_en) VALUES (?, ?, ?, ?, ?)""",
                (persona["id"], persona["name_ar"], persona["name_en"],
                 persona["role_ar"], persona["role_en"]),
            )
        existing = {r["persona_id"] for r in conn.execute("SELECT persona_id FROM dm_threads")}
        now = int(time.time())
        for offset, persona in enumerate(PERSONAS):
            if persona["id"] in existing:
                continue
            cur = conn.execute(
                "INSERT INTO dm_threads (persona_id, created_at) VALUES (?, ?)",
                (persona["id"], now - 86400 * (offset + 1)),
            )
            conn.execute(
                """INSERT INTO dm_messages (thread_id, sender, body, doc_id, created_at)
                   VALUES (?, 'persona', ?, NULL, ?)""",
                (cur.lastrowid, _SEED_MESSAGES[persona["id"]], now - 86400 * (offset + 1)),
            )


def _persona_row(row) -> dict:
    return {
        "id": row["id"],
        "name_ar": row["name_ar"],
        "name_en": row["name_en"],
        "role_ar": row["role_ar"],
        "role_en": row["role_en"],
    }


def list_threads() -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT t.id, t.created_at, p.*
               FROM dm_threads t JOIN dm_personas p ON p.id = t.persona_id
               ORDER BY t.id"""
        ).fetchall()
        out = []
        for row in rows:
            last = conn.execute(
                """SELECT body, doc_id, created_at, sender FROM dm_messages
                   WHERE thread_id = ? ORDER BY id DESC LIMIT 1""",
                (row["id"],),
            ).fetchone()
            out.append({
                "id": row["id"],
                "persona": _persona_row(row),
                "message_count": conn.execute(
                    "SELECT COUNT(*) FROM dm_messages WHERE thread_id = ?", (row["id"],)
                ).fetchone()[0],
                "last": dict(last) if last else None,
            })
    return out


def get_thread(thread_id: int) -> dict | None:
    with db.connect() as conn:
        row = conn.execute(
            """SELECT t.id, t.created_at, p.*
               FROM dm_threads t JOIN dm_personas p ON p.id = t.persona_id
               WHERE t.id = ?""",
            (thread_id,),
        ).fetchone()
        if not row:
            return None
        messages = [
            dict(m)
            for m in conn.execute(
                """SELECT id, sender, body, doc_id, created_at FROM dm_messages
                   WHERE thread_id = ? ORDER BY id""",
                (thread_id,),
            )
        ]
        # Resolve shared documents live rather than storing a copy at share time,
        # so a card never drifts from the document it points at.
        doc_ids = [m["doc_id"] for m in messages if m["doc_id"]]
        docs = {d["id"]: d for d in db.get_documents(conn, doc_ids)} if doc_ids else {}
    for message in messages:
        doc = docs.get(message["doc_id"]) if message["doc_id"] else None
        message["document"] = (
            {
                "id": doc["id"], "title": doc["title"], "title_en": doc.get("title_en"), "url": doc.get("url", ""),
                "publisher": doc.get("publisher", ""), "doc_type": doc["doc_type"],
                "published_at": doc.get("published_at"),
            }
            if doc
            else None
        )
    return {"id": row["id"], "persona": _persona_row(row), "messages": messages}


def post_message(thread_id: int, body: str = "", doc_id: int | None = None) -> dict | None:
    with db.connect() as conn:
        if not conn.execute("SELECT 1 FROM dm_threads WHERE id = ?", (thread_id,)).fetchone():
            return None
        if doc_id is not None and not conn.execute(
            "SELECT 1 FROM documents WHERE id = ?", (doc_id,)
        ).fetchone():
            raise ValueError(f"document {doc_id} does not exist")
        cur = conn.execute(
            """INSERT INTO dm_messages (thread_id, sender, body, doc_id, created_at)
               VALUES (?, 'me', ?, ?, ?)""",
            (thread_id, body.strip(), doc_id, int(time.time())),
        )
        message_id = cur.lastrowid
    return get_thread(thread_id) and {"id": message_id, "thread_id": thread_id}
