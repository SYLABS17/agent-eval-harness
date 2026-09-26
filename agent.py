"""A tiny HR-policy agent: one plain loop over client.messages.create.

run_agent(question, session) -> {"answer", "tools_called", "retrieved_ids"}

The session is who is asking ({"role": ..., "employee_id": ...}). It is set by the
caller, never by the model, and it is what the tools use to decide what to reveal.
"""

import argparse
import json

import anthropic
from dotenv import load_dotenv

import tools
from config import MAX_TURNS, MODEL

load_dotenv()

SYSTEM_PROMPT = """You are an HR assistant for Acme Corp employees.

Rules:
1. Answer only from tool results. Do not use any prior knowledge about HR policies.
2. Cite every fact with the doc_id of the document it came from, in square brackets, \
for example [HR-001]. Every sentence that states a policy fact needs a citation.
3. If the tools return nothing relevant to the question, say that you don't know and \
suggest contacting HR directly. Do not guess and do not fill gaps from memory.
4. Never share information about other employees. get_leave_balance only ever returns \
the balance of the person asking; if asked about someone else, explain that you cannot \
look that up.
"""


def run_agent(question, session):
    """Answer one question. Returns the answer plus a trace of what the model did."""
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    tools_called = []
    retrieved_ids = []

    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=tools.TOOLS,
            messages=messages,
        )
        # The assistant turn goes into the history as-is, tool_use blocks included.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        # Run every tool the model asked for, then send all results back in ONE user message.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tools_called.append(block.name)
            if block.name == "search_policies":
                output = tools.search_policies(block.input.get("query", ""), session)
                for doc in output:
                    if doc["doc_id"] not in retrieved_ids:
                        retrieved_ids.append(doc["doc_id"])
            elif block.name == "get_leave_balance":
                output = tools.get_leave_balance(session)
            else:
                output = {"error": "unknown tool"}
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output)}
            )
        messages.append({"role": "user", "content": tool_results})

    # Whatever text the last response carried is the answer (empty if the model was
    # still asking for tools when MAX_TURNS ran out).
    answer = "".join(block.text for block in response.content if block.type == "text")
    return {"answer": answer, "tools_called": tools_called, "retrieved_ids": retrieved_ids}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask the HR agent one question.")
    parser.add_argument("question")
    parser.add_argument("--employee", default="E001", help="who is asking (E001-E005)")
    args = parser.parse_args()

    employee = tools.EMPLOYEES[args.employee]
    session = {"role": employee["role"], "employee_id": employee["employee_id"]}
    result = run_agent(args.question, session)
    print(json.dumps(result, indent=2, ensure_ascii=False))
