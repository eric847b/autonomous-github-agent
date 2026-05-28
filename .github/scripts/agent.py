import os,json,subprocess
from pathlib import Path
from github import Github
from openai import OpenAI

client=OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gh=Github(os.getenv("GITHUB_TOKEN"))
repo=gh.get_repo(os.getenv("GITHUB_REPOSITORY"))
MAX_ITER=8
BR=f"agent-{os.urandom(4).hex()}"

def run_command(c,w="."):
    try:
        r=subprocess.run(c,shell=True,cwd=w,capture_output=True,text=True,timeout=60)
        return f"CMD:{c}\nOUT:{r.stdout}\nERR:{r.stderr}"
    except Exception as e:
        return str(e)

def read_file(p):
    try:return Path(p).read_text(encoding="utf-8")
    except Exception as e:return str(e)

def edit_file(p,o,n):
    try:
        t=Path(p).read_text(encoding="utf-8")
        if o not in t:return "not found"
        Path(p).write_text(t.replace(o,n,1),encoding="utf-8")
        return "edited"
    except Exception as e:return str(e)

tools={
    "run_command":run_command,
    "read_file":read_file,
    "edit_file":edit_file
}

specs=[
    {"type":"function","function":{
        "name":"run_command",
        "parameters":{"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string","default":"."}},"required":["command"]}
    }},
    {"type":"function","function":{
        "name":"read_file",
        "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}
    }},
    {"type":"function","function":{
        "name":"edit_file",
        "parameters":{"type":"object","properties":{"path":{"type":"string"},"old":{"type":"string"},"new":{"type":"string"}},"required":["path","old","new"]}
    }}
]

def agent_loop(task):
    msgs=[
        {"role":"system","content":f"You modify {repo.full_name} safely. Always use a new branch and draft PR."},
        {"role":"user","content":task}
    ]
    branched=False

    for _ in range(MAX_ITER):
        r=client.chat.completions.create(model="gpt-4o",messages=msgs,tools=specs,tool_choice="auto")
        m=r.choices[0].message
        msgs.append(m)
        if not m.tool_calls:
            print("DONE");print(m.content or "")
            break

        for call in m.tool_calls:
            name=call.function.name
            args=json.loads(call.function.arguments or "{}")
            if name=="run_command":
                res=run_command(args.get("command",""),args.get("cwd","."))
                if not branched and args.get("command","").startswith("git "):
                    run_command(f"git checkout -b {BR}")
                    branched=True
            elif name=="read_file":
                res=read_file(args.get("path",""))
            elif name=="edit_file":
                if not branched:
                    run_command(f"git checkout -b {BR}")
                    branched=True
                res=edit_file(args.get("path",""),args.get("old",""),args.get("new",""))
            else:
                res="unknown tool"

            msgs.append({"role":"tool","tool_call_id":call.id,"content":str(res)})

    if branched:
        run_command("git add .")
        run_command('git commit -m "agent changes" || echo nochange')
        run_command(f"git push origin {BR} || echo pushfail")
        pr=repo.create_pull(
            title=f"🤖 Agent: {task[:60]}",
            body=f"Task: {task}\nIterations:{MAX_ITER}",
            head=BR,
            base=repo.default_branch,
            draft=True
        )
        print("PR:",pr.html_url)

if __name__=="__main__":
    agent_loop(os.getenv("TASK","Review repository"))
