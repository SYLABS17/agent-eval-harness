"""The two tools the HR agent can call, and the schemas that describe them to the model.

Access control lives here, in code, not in the prompt:
  * search_policies decides what the model may see from the session's role.
  * get_leave_balance takes no arguments from the model at all, so it can only
    ever look up the person who is asking.
"""

import json
import re
from pathlib import Path

from config import TOP_K

DATA_DIR = Path(__file__).parent / "data"
DOCS = json.loads((DATA_DIR / "docs.json").read_text(encoding="utf-8"))
EMPLOYEES = {
    e["employee_id"]: e
    for e in json.loads((DATA_DIR / "employees.json").read_text(encoding="utf-8"))
}

# Set to True by `run_evals.py --seed-leak` to switch the access filter off on purpose,
# proving that the harness catches a leak when one exists.
SEED_LEAK = False

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "your", "our", "can", "with",
    "this", "that", "from", "have", "has", "had", "was", "were", "will", "would",
    "should", "could", "may", "might", "must", "does", "did", "about", "what",
    "when", "where", "which", "who", "why", "how", "any", "all", "each", "per",
    "into", "than", "then", "them", "they", "their", "there", "these", "those",
    "also", "been", "being", "get", "got", "some", "such", "only", "other", "out",
    "over", "under", "more", "most", "much", "many", "very", "just", "its", "one",
    "two", "own", "off", "after", "before", "during", "between", "because", "while",
    "until", "again", "here", "both", "few", "now", "too", "use", "used", "using",
    "like", "make", "made", "take", "let", "say", "said", "see", "tell", "told",
}


def tokenize(text):
    """Lowercase words, dropping common stopwords and anything under 3 characters,
    unless the short token contains a digit (so "L4", "L5" and "E005" survive)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if (len(w) >= 3 or any(ch.isdigit() for ch in w)) and w not in STOPWORDS}


def search_policies(query, session):
    """Keyword search over the policy corpus, filtered by what the session may see.

    Score = number of distinct query words that appear in the document (title + text).
    Returns the top TOP_K documents with a score above zero, best first.
    """
    query_words = tokenize(query)
    scored = []
    for doc in DOCS:
        visible = doc["access"] == "all" or session["role"] == "hr" or SEED_LEAK
        if not visible:
            continue
        score = len(query_words & tokenize(doc["title"] + " " + doc["text"]))
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda pair: pair[0], reverse=True)  # stable: ties keep corpus order
    return [
        {"doc_id": doc["doc_id"], "title": doc["title"], "text": doc["text"]}
        for _, doc in scored[:TOP_K]
    ]


def get_leave_balance(session):
    """Return the leave balance of the employee in the session, and nobody else's."""
    employee = EMPLOYEES[session["employee_id"]]
    return {
        "employee_id": employee["employee_id"],
        "name": employee["name"],
        "leave_balance": employee["leave_balance"],
    }


# What the model sees. Note get_leave_balance has an empty properties object:
# the model cannot pass an employee_id even if it wants to.
TOOLS = [
    {
        "name": "search_policies",
        "description": (
            "Search Acme Corp HR policy documents by keyword. Returns the most relevant "
            "documents, each with a doc_id, title and full text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords describing the policy topic to look up.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_leave_balance",
        "description": (
            "Return the leave balance (in days) of the employee who is asking. Takes no "
            "arguments: the caller's identity comes from the session, not from the model."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]
