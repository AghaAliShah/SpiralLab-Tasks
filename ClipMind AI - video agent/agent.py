"""
agent.py
========
This is the BRAIN. It ties everything together.

The big idea (read this slowly):
--------------------------------
A normal script is dumb: YOU write "step 1, then step 2, then step 3".
An AGENT is different: you give it a GOAL + a list of TOOLS, and the language
model (here: Groq's Llama) itself DECIDES which tool to use and in what order.

The loop below is the heart of every AI agent in the world:

    1. We send the goal + tool list to the model.
    2. The model replies EITHER with:
         (a) a request to call one or more tools -> we run them, send results back
         (b) a final text answer                 -> we stop.
    3. Repeat until we get a final answer.

That's it. Understand this loop and you understand AI agents.
"""

import sys
import json

import tools  # our tools + the shared Groq client + retry helper (tools.chat)

# Windows consoles default to a limited encoding (cp1252) and crash when we
# print non-English text. Force UTF-8 so printing is safe.
sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# STEP A: Describe our tools to the model (the "menu" it can order from)
# ---------------------------------------------------------------------------
# The model does NOT see our Python code - only these JSON descriptions. This is
# the standard "function calling" format (the same one OpenAI/Groq use).
TOOL_MENU = [
    {
        "type": "function",
        "function": {
            "name": "search_youtube",
            "description": "Search YouTube and return the best matching video (title + url).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for on YouTube."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transcribe_and_save",
            "description": ("Transcribe a YouTube video (by url) and save its transcript to the "
                            "knowledge base. Returns a short status, not the full transcript."),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The YouTube video URL to transcribe."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_knowledge_base",
            "description": ("Answer a question using the transcripts already saved in the knowledge "
                            "base. Use this when the user asks about a video's content."),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to answer from saved transcripts."},
                },
                "required": ["question"],
            },
        },
    },
]

# STEP B: Map each tool NAME (that the model says) to the REAL python function.
TOOL_FUNCTIONS = {
    "search_youtube": tools.search_youtube,
    "transcribe_and_save": tools.transcribe_and_save,
    "ask_knowledge_base": tools.ask_knowledge_base,
}


def run_agent(goal: str) -> str:
    """
    Give the agent a goal in plain English and let it work.
    Returns the agent's final text answer.
    """
    # 'messages' is the running conversation. We keep adding to it every step:
    # the user goal, the model's tool requests, and the tool results.
    messages = [
        {"role": "system", "content":
            "You are a helpful agent that can search YouTube, transcribe videos, "
            "and answer questions from saved transcripts. Use the tools to reach "
            "the user's goal, then reply with a short final answer."},
        {"role": "user", "content": goal},
    ]

    # THE AGENT LOOP (safety cap of 10 steps so it can never loop forever)
    for step in range(10):
        # Go through tools.chat so the agent shares the same 429 retry safety net.
        message = tools.chat(messages, tools=TOOL_MENU)

        # No tool calls? Then this is the FINAL answer. We're done.
        if not message.tool_calls:
            return message.content

        # Record the model's request (with its tool calls) in the conversation.
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in message.tool_calls
            ],
        })

        # Run each requested tool and feed the result back to the model.
        for tc in message.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            print(f"  [agent step {step + 1}] wants to call: {name}({args})")

            try:
                result = TOOL_FUNCTIONS[name](**args)
            except Exception as error:
                result = f"Tool error: {error}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": str(result),
            })

    return "Stopped: the agent took too many steps."


# ---------------------------------------------------------------------------
# Run it:  python agent.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Notice: we NEVER tell it "first search, then transcribe, then save".
    # We only give it the GOAL. The agent figures out the steps itself.
    goal = (
        "Find a YouTube video that explains what an API is in simple terms, "
        "transcribe it and save it, then give me a 2-line summary of it."
    )

    print("GOAL:", goal, "\n")
    answer = run_agent(goal)
    print("\nFINAL ANSWER:\n", answer)
