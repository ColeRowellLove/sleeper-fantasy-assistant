# Prompts

One file per task, named `<task>.v<N>.md`. Change a prompt by adding a new version, not by editing
an old one in place, so a stored answer can say which prompt wrote it. A prompt says who the model
is, what the FACTS JSON holds, the rules (use only the facts, quote only numbers that are in them,
never invent players), and the tone. The output schema is appended by `llm.ask`.
