"""Settings shared by the agent and the eval harness."""

# Claude Haiku 4.5. Checked against Anthropic's models page on 2026-09-27: current.
MODEL = "claude-haiku-4-5-20251001"

# Hard cap on messages.create calls per question, so a confused model can't loop forever.
MAX_TURNS = 5

# How many documents search_policies hands back to the model.
TOP_K = 3
