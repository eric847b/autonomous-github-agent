import os,json,subprocess,time,random,requests
from pathlib import Path
from github import Github
import openai,google.generativeai as g,anthropic as A

gh=Github(os.getenv("GITHUB_TOKEN"));r=gh.get_repo(os.getenv("GITHUB_REPOSITORY"))
B=f"a-{os.urandom(4).hex()}";MI=8

def rc(c,w="."):
 try:
  x=subprocess.run(c,shell=True,cwd=w,capture_output=True,text=True,timeout=60);return f"O:{x.stdout}\nE:{x.stderr}"
 except Exception as e:return str(e)
def rf(p):
 try:return Path(p).read_text()
 except Exception as e:return str(e)
def ef(p,o,n):
 try:t=Path(p).read_text()
 except Exception as e:return str(e)
 if o not in t:return"NF"
 Path(p).write_text(t.replace(o,n,1));return"OK"

T={"run_command":rc,"read_file":rf,"edit_file":ef}
S=[
{"type":"function","function":{"name":"run_command","parameters":{"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string","default":"."}},"required":["command"]}}},
{"type":"function","function":{"name":"read_file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
{"type":"function","function":{"name":"edit_file","parameters":{"type":"object","properties":{"path":{"type":"string"},"old":{"type":"string"},"new":{"type":"string"}},"required":["path","old","new"]}}}
]

P=os.getenv("LLM_PROVIDER","openai").split(",")
openai.api_key=os.getenv("OPENAI_API_KEY")
g.configure(api_key=os.getenv("GEMINI_API_KEY"))
ac=A.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def oai(m,t):return openai.chat.completions.create(model="gpt-4o",messages=m,tools=t,tool_choice="auto")
def gem(m,t):
 x=g.GenerativeModel("gemini-1.5-pro").generate_content(m[-1]["content"])
 class M:pass
 y=M();y.content=x.text;y.tool_calls=[]
 class C:pass
 c=C();c.message=y
 class R:pass
 R=R();R.choices=[c];return R
def cla(m,t):
 x=ac.messages.create(model="claude-3-opus-20240229",messages=[{"role":i["role"],"content":i["content"]}for i in m if i["role"]!="tool"])
 class M:pass
 y=M();y.content=x.content[0].text;y.tool_calls=[]
 class C:pass
 c=C();c.message=y
 class R:pass
 R=R();R.choices=[c];return R
def orr(m,t):
 x=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},json={"model":"openai/gpt-4o","messages":m}).json()
 z=x["choices"][0]["message"]
 class M:pass
 y=M();y.content=z.get("content","");y.tool_calls=[]
 class C:pass
 c=C();c.message=y
 class R:pass
 R=R();R.choices=[c];return R
def hf(m,t):
 x=requests.post(f"https://api-inference.huggingface.co/models/{os.getenv('HF_MODEL')}",headers={"Authorization":f"Bearer {os.getenv('HF_API_KEY')}"},json={"inputs":m[-1]["content"]}).json()
 z=x[0]["generated_text"]if isinstance(x,list)else str(x)
 class M:pass
 y=M();y.content=z;y.tool_calls=[]
 class C:pass
 c=C();c.message=y
 class R:pass
 R=R();R.choices=[c];return R
def rep(m,t):
 x=requests.post("https://api.replicate.com/v1/chat/completions",headers={"Authorization":f"Bearer {os.getenv('REPLIT_API_KEY')}"},json={"model":"meta/llama-3-70b","messages":m}).json()
 z=x["choices"][0]["message"]
 class M:pass
 y=M();y.content=z.get("content","");y.tool_calls=[]
 class C:pass
 c=C();c.message=y
 class R:pass
 R=R();R.choices=[c];return R

C={"openai":oai,"gemini":gem,"anthropic":cla,"openrouter":orr,"huggingface":hf,"replit":rep}
W={"huggingface":1,"gemini":2,"replit":2,"openai":3,"openrouter":4,"anthropic":5}

def llm(m,t):
 O=[p for p in P if p in C]or["openai"]
 random.shuffle(O);O=sorted(O,key=lambda x:W.get(x,9))
 for p in O:
  f=C[p]
  for a in range(3):
   try:return f(m,t)
   except:time.sleep(1+a)
 raise Exception("LLM_FAIL")

def agent(x):
 M=[{"role":"system","content":f"Autonomous engineer for {r.full_name}. Use tools. Safe. Branch. Draft PR."},{"role":"user","content":x}]
 b=False
 for _ in range(MI):
  R=llm(M,S);m=R.choices[0].message;tc=getattr(m,"tool_calls",[])
  M.append({"role":"assistant","content":m.content or "","tool_calls":tc})
  if not tc:print(m.content or "");break
  for c in tc:
   n=c.function.name;A=json.loads(c.function.arguments or "{}")
   if n=="run_command":
    cmd=A.get("command","");cwd=A.get("cwd",".")
    if not b and cmd.startswith("git "):rc(f"git checkout -b {B}");b=True
    o=rc(cmd,cwd)
   elif n=="read_file":o=rf(A.get("path",""))
   elif n=="edit_file":
    if not b:rc(f"git checkout -b {B}");b=True
    o=ef(A.get("path",""),A.get("old",""),A.get("new",""))
   else:o="BAD"
   M.append({"role":"tool","tool_call_id":c.id,"content":str(o)})
 if b:
  rc("git add .");rc('git commit -m a || echo nc');rc(f"git push origin {B} || echo np")
  p=r.create_pull(title=f"🤖 {x[:60]}",body=f"T:{x}\nI:{MI}",head=B,base=r.default_branch,draft=True)
  print(p.html_url)

if __name__=="__main__":agent(os.getenv("TASK","Review repo"))
