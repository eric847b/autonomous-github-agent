import os
import json
import subprocess
from pathlib import Path
from github import Github
from openai import OpenAI

client = OpenAI()
g = Github(os.getenv("GITHUB_TOKEN"))
repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))

MAX_ITERATIONS = 8
WORKING_BRANCH = f"agent-task-{os.urandom(4).hex()}"

def run_command(cmd: str, cwd: str = ".") -> str:
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30)
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"

def read_file(path: str) -> str:
    try:
        return Path(path).read_text()
    except Exception as e:
        return f"Error reading {path}: {e}"

def edit_file(path: str, old_str: str, new_str: str) -> str:
    try:
        content = Path(path).read_text()
        if old_str in content:
            content = content.replace(old_str, new_str, 1)
            Path(path).write_text(content)
            return f"Successfully edited {path}"
        return "Old string not found"
    except Exception as e:
        return f"Edit failed: {e}"

tools = {
    "run_command": run_command,
    "read_file": read_file,
    "edit_file": edit_file
}

def agent_loop(task: str):
    messages = [{
        "role": "system",
        "content": f"""You are an expert autonomous software engineer for {repo.full_name}.
You must be careful, thorough, and safe. 
- Always create changes on a new branch and open a DRAFT PR.
- Never push directly to main.
- Run tests before proposing changes.
- Explain your reasoning clearly.""".strip()
    }]

    branch_created = False

    for i in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=[{
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {{"type": "object", "properties": {{"__arg": {{"type": "string"}}}}, "required": ["__arg"]}}
                }
            }} for name in tools.keys()],
            tool_choice="auto"
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            final_plan = msg.content
            print("✅ Agent finished reasoning.")
            break

        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            arg = json.loads(tool_call.function.arguments).get("__arg", "")
            
            print(f"🔧 Calling {func_name}({arg[:100]}...)")
            result = tools[func_name](arg)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

            if not branch_created and "git" in arg.lower():
                run_command(f"git checkout -b {WORKING_BRANCH}")
                branch_created = True

    if branch_created:
        run_command("git add .")
        run_command('git commit -m "🤖 Autonomous Agent changes" || echo "No changes to commit"')
        run_command(f"git push origin {WORKING_BRANCH}")

        pr = repo.create_pull(
            title=f"🤖 Agent: {task[:60]}...",
            body=f"Autonomous changes by agent.\n\nTask: {task}\n\nIteration limit: {MAX_ITERATIONS}",
            head=WORKING_BRANCH,
            base=repo.default_branch,
            draft=True
        )
        print(f"✅ Draft PR created: {pr.html_url}")

if __name__ == "__main__":
    task = os.getenv("TASK", "Review repository and fix issues")
    agent_loop(task)
