import json

from config.config_file import WRITE_MODEL_NAME
from src.utils import rewrite_section, score_resume

tools = [
    {
        "type": "function",
        "function": {
            "name": "score_resume",
            "description": "Scores the resume against the job description (0-10).",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string"},
                    "job_text": {"type": "string"},
                },
                "required": ["resume_text", "job_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rewrite_section",
            "description": "Rewrites the resume based on feedback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string"},
                    "job_text": {"type": "string"},
                    "grader_feedback": {"type": "string"},
                },
                "required": ["resume_text", "job_text", "grader_feedback"],
            },
        },
    },
]


def run_agent(client, resume_text, job_description):
    messages = [
        {
            "role": "system",
            "content": "You are an AI agent. Use your tools to fix the resume. Keep scoring and rewriting until the score is 8 or higher. Then, output the final resume text to the user.",
        },
        {
            "role": "user",
            "content": f"Fix my resume.\nJob Description: {job_description}\nMy Resume: {resume_text}",
        },
    ]

    while True:
        response = client.chat.completions.create(
            model=WRITE_MODEL_NAME, messages=messages, tools=tools, tool_choice="auto"
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            args = json.loads(tool_call.function.arguments)

            if tool_call.function.name == "score_resume":
                result = score_resume(
                    client,
                    args["resume_text"],
                    args["job_text"],
                )
            elif tool_call.function.name == "rewrite_section":
                result = rewrite_section(
                    client,
                    args["resume_text"],
                    args["job_text"],
                    args["grader_feedback"],
                )
            else:
                # Defensive: return an error if the model requested an unknown tool
                result = json.dumps(
                    {"error": f"unknown tool {tool_call.function.name}"}
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
