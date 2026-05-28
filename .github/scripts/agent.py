import os
import json
import subprocess
from pathlib import Path
from github import Github
from openai import OpenAI

# --- Clients ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
g = Github(os.getenv("GITHUB_TOKEN"))
repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))

MAX_ITERATIONS = 8
WORKING_BRANCH = f"agent-task-{os.urandom(4).hex()}"


# --- Tools ---
def run_command(cmd: str, cwd: str = ".") -> str:
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30)
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"


def read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading {path}: {e}"


def edit_file(path: str, old_str: str, new_str: str) -> str:
    try:
        content = Path(path).read_text(encoding="utf-8")
        if old_str in content:
            content = content.replace(old_str, new_str, 1)
            Path(path).write_text(content, encoding="utf-8")
            return f"✅ Successfully edited {path}"
        return f"❌ Old string not found in {path}"
    except Exception as e:
        return f"❌ Edit failed: {e}"


tool_functions = {
    "run_command": run_command,
    "read_file": read_file,
    "edit_file": edit_file
}


# --- Tool Schemas (Corrected) ---
tool_specs = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Call the {name} tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg": {"type": "string", "description": "Argument for the tool"}
                },
                "required": ["arg"]
            }
        }
    }
    for name in tool_functions.keys()
]


def agent_loop(task: str):
    messages = [{
        "role": "system",
        "content": f"""You are an expert autonomous software engineer for {repo.full_name}.
You must be careful, thorough, and safe. 
- Always create changes on a new branch and open a **DRAFT PR**.
- Never push directly to main.
- Run tests before proposing changes.
- Explain your reasoning clearly.""".strip()
    },
    {
        "role": "user",
        "content": f"Task: {task}"
    }]

    branch_created = False

    for i in range(MAX_ITERATIONS):
        print(f"\n🔄 Iteration {i+1}/{MAX_ITERATIONS}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tool_specs,
            tool_choice="auto",
            temperature=0.3
        )

        msg = response.choices[0].message
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})

        if not msg.tool_calls:
            print("✅ Agent finished reasoning.")
            if msg.content:
                print(msg.content)
            break

        # Execute tools
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")
            arg = args.get("arg", "")

            print(f"🔧 Calling {name}({arg[:80]}...)")

            result = tool_functions[name](arg)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

            if not branch_created and "git" in arg.lower():
                run_command(f"git checkout -b {WORKING_BRANCH}")
                branch_created = True

    # Final step: Create Draft PR if changes were made
    if branch_created:
        run_command("git add .")
        run_command('git commit -m "🤖 Autonomous Agent changes" || echo "No changes to commit"')
        run_command(f"git push origin {WORKING_BRANCH} || echo 'Push failed'")

        try:
            pr = repo.create_pull(
                title=f"🤖 Agent: {task[:60]}...",
                body=f"Autonomous changes.\n\nTask: {task}\n\nIterations: {MAX_ITERATIONS}",
                head=WORKING_BRANCH,
                base=repo.default_branch,
                draft=True
            )
            print(f"✅ Draft PR created: {pr.html_url}")
        except Exception as e:
            print(f"PR creation failed: {e}")


if __name__ == "__main__":
    task = os.getenv("TASK", "Review repository and fix issues")
    agent_loop(task)