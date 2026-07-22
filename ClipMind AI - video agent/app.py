"""
app.py  -  ClipMind AI web UI (built with Flask)
================================================
Run it:   python app.py       then open http://127.0.0.1:5000

Routes:
  - GET  "/"      serves the single-page UI below.
  - POST "/run"   runs the full agent, returns JSON  {"result": ...}.
  - POST "/ask"   runs the RAG tool,   returns JSON  {"result": ...}.

Chat history + "New chat" live entirely in the browser (localStorage), so the
server stays simple and stateless - the same idea Claude's UI uses.
"""

from flask import Flask, request, jsonify, render_template_string

import agent   # our agent brain (run_agent)
import tools   # our tools (ask_knowledge_base)

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ClipMind AI</title>
<style>
  :root{
    --cream:#faf6ee; --sidebar:#f3ecdf; --card:#fffdf8;
    --ink:#3a342c; --muted:#8c8477; --line:#e7ddcb;
    --accent:#b4703f; --accent-dark:#98592d; --ring:rgba(180,112,63,.18);
    --userbubble:#f0e4d2;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0;display:flex;background:var(--cream);color:var(--ink);
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased;
  }

  /* ---------- sidebar ---------- */
  .sidebar{
    width:264px;flex:none;background:var(--sidebar);border-right:1px solid var(--line);
    display:flex;flex-direction:column;height:100vh;
  }
  .brand{display:flex;align-items:center;gap:10px;padding:20px 18px 14px}
  .mark{width:26px;height:26px;border-radius:7px;background:var(--accent);flex:none;
        display:flex;align-items:center;justify-content:center}
  .mark span{width:11px;height:11px;border:2.5px solid #fff;border-radius:50%}
  .brand b{font-size:17px;letter-spacing:-.01em}
  .brand small{color:var(--muted);font-weight:600;font-size:11px;letter-spacing:.14em}

  .newbtn{
    margin:6px 14px 12px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;
    background:var(--card);color:var(--ink);font-size:14px;font-weight:600;cursor:pointer;
    display:flex;align-items:center;gap:9px;transition:.15s;
  }
  .newbtn:hover{border-color:var(--accent);color:var(--accent)}
  .newbtn svg{flex:none}

  .histlabel{padding:6px 20px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.1em}
  .history{flex:1;overflow-y:auto;padding:2px 10px 16px}
  .hitem{
    padding:10px 12px;border-radius:9px;font-size:13.5px;color:var(--ink);cursor:pointer;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:.12s;
  }
  .hitem:hover{background:#ece2d1}
  .hitem.active{background:#e6d8c1;font-weight:600}
  .empty-hist{padding:10px 20px;color:var(--muted);font-size:13px}

  /* ---------- main ---------- */
  .main{flex:1;display:flex;flex-direction:column;height:100vh}
  .messages{flex:1;overflow-y:auto;padding:34px 0}
  .inner{max-width:720px;margin:0 auto;padding:0 24px}

  .welcome{max-width:720px;margin:0 auto;padding:64px 24px;text-align:center}
  .welcome h1{font-size:28px;letter-spacing:-.02em;margin:0 0 8px}
  .welcome p{color:var(--muted);font-size:15px;margin:0}

  .msg{display:flex;margin-bottom:22px}
  .msg.user{justify-content:flex-end}
  .bubble{padding:13px 16px;border-radius:14px;line-height:1.6;font-size:15px;white-space:pre-wrap;max-width:88%}
  .msg.user .bubble{background:var(--userbubble);border:1px solid var(--line);border-bottom-right-radius:5px}
  .msg.bot  .bubble{background:var(--card);border:1px solid var(--line);border-bottom-left-radius:5px;width:100%}

  .loader{display:flex;align-items:center;gap:13px;color:var(--muted);font-size:14px}
  .spinner{width:24px;height:24px;border-radius:50%;
    border:3px solid #efe6d5;border-top-color:var(--accent);animation:spin .8s linear infinite;flex:none}
  @keyframes spin{to{transform:rotate(360deg)}}
  .dots::after{content:"";animation:dots 1.4s steps(4,end) infinite}
  @keyframes dots{0%{content:""}25%{content:"."}50%{content:".."}75%{content:"..."}}

  /* ---------- composer ---------- */
  .composer{border-top:1px solid var(--line);background:var(--cream);padding:14px 0 22px}
  .cwrap{max-width:720px;margin:0 auto;padding:0 24px}
  .tabs{display:inline-flex;background:#efe6d5;border-radius:9px;padding:3px;margin-bottom:12px}
  .tab{border:0;background:transparent;color:var(--muted);cursor:pointer;
    padding:7px 14px;border-radius:7px;font-size:13px;font-weight:600;transition:.15s}
  .tab.active{background:var(--card);color:var(--ink);box-shadow:0 1px 2px rgba(58,52,44,.12)}

  .searchrow{display:flex;gap:10px;align-items:stretch}
  .field{position:relative;flex:1}
  .field svg{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--muted)}
  input[type=text]{width:100%;padding:14px 14px 14px 42px;font-size:15px;color:var(--ink);
    background:#fff;border:1px solid var(--line);border-radius:12px;outline:none;transition:.15s}
  input[type=text]::placeholder{color:#b7ae9e}
  input[type=text]:focus{border-color:var(--accent);box-shadow:0 0 0 4px var(--ring)}
  button.go{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;
    padding:14px 22px;font-size:15px;font-weight:600;color:#fff;cursor:pointer;
    background:var(--accent);border:0;border-radius:12px;transition:.15s}
  button.go:hover{background:var(--accent-dark)}
  button.go:disabled{opacity:.6;cursor:not-allowed}
  .hint{color:var(--muted);font-size:12.5px;margin-top:10px}
</style>
</head>
<body>
  <!-- SIDEBAR -->
  <aside class="sidebar">
    <div class="brand">
      <div class="mark"><span></span></div>
      <div>
        <b>ClipMind AI</b><br><small>VIDEO AGENT</small>
      </div>
    </div>
    <button class="newbtn" id="newchat">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      New chat
    </button>
    <div class="histlabel">HISTORY</div>
    <div class="history" id="history"></div>
  </aside>

  <!-- MAIN -->
  <main class="main">
    <div class="messages" id="messages"></div>

    <div class="composer">
      <div class="cwrap">
        <div class="tabs">
          <button class="tab active" data-mode="run">Find &amp; transcribe</button>
          <button class="tab" data-mode="ask">Ask saved videos</button>
        </div>
        <div class="searchrow">
          <div class="field">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path>
            </svg>
            <input id="q" type="text"
                   placeholder="Find and transcribe a video about how HTTP works">
          </div>
          <button id="go" class="go"><span id="golabel">Run agent</span></button>
        </div>
        <div class="hint" id="hint">The agent decides the steps itself: search &rarr; transcribe &rarr; save.</div>
      </div>
    </div>
  </main>

<script>
  const KEY = 'clipmind_chats';
  let chats = JSON.parse(localStorage.getItem(KEY) || '[]');
  let currentId = null;
  let mode = 'run';
  let busy = false;

  const $ = id => document.getElementById(id);
  const save = () => localStorage.setItem(KEY, JSON.stringify(chats));
  const current = () => chats.find(c => c.id === currentId);

  // ---- rendering ----
  function renderSidebar(){
    const h = $('history');
    if(!chats.length){ h.innerHTML = '<div class="empty-hist">No chats yet.</div>'; return; }
    h.innerHTML = '';
    chats.forEach(c => {
      const d = document.createElement('div');
      d.className = 'hitem' + (c.id === currentId ? ' active' : '');
      d.textContent = c.title;
      d.onclick = () => { currentId = c.id; renderSidebar(); renderMessages(); };
      h.appendChild(d);
    });
  }

  function bubble(role, text){
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + (role === 'user' ? 'user' : 'bot');
    const b = document.createElement('div');
    b.className = 'bubble';
    b.textContent = text;
    wrap.appendChild(b);
    return wrap;
  }

  function renderMessages(loadingText){
    const m = $('messages');
    const c = current();
    if(!c || (!c.messages.length && !loadingText)){
      m.innerHTML = '<div class="welcome"><h1>ClipMind AI</h1>' +
        '<p>Search a video, transcribe it with Whisper, and ask questions about what it said.</p></div>';
      return;
    }
    const inner = document.createElement('div');
    inner.className = 'inner';
    c.messages.forEach(msg => inner.appendChild(bubble(msg.role, msg.text)));
    if(loadingText){
      const w = document.createElement('div');
      w.className = 'msg bot';
      w.innerHTML = '<div class="bubble"><div class="loader"><div class="spinner"></div>' +
        '<span>' + loadingText + '<span class="dots"></span></span></div></div>';
      inner.appendChild(w);
    }
    m.innerHTML = '';
    m.appendChild(inner);
    m.scrollTop = m.scrollHeight;
  }

  // ---- actions ----
  $('newchat').onclick = () => { if(busy) return; currentId = null; renderSidebar(); renderMessages(); $('q').focus(); };

  document.querySelectorAll('.tab').forEach(t => {
    t.onclick = () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      mode = t.dataset.mode;
      if(mode === 'run'){
        $('golabel').textContent = 'Run agent';
        $('q').placeholder = 'Find and transcribe a video about how HTTP works';
        $('hint').innerHTML = 'The agent decides the steps itself: search &rarr; transcribe &rarr; save.';
      } else {
        $('golabel').textContent = 'Ask';
        $('q').placeholder = 'What is an API key used for?';
        $('hint').textContent = 'Answered only from transcripts already saved in the knowledge base.';
      }
    };
  });

  async function submit(){
    if(busy) return;
    const text = $('q').value.trim();
    if(!text){ $('q').focus(); return; }

    // start a new chat lazily on the first message
    if(!current()){
      const chat = { id: Date.now().toString(), title: text.slice(0,38), messages: [] };
      chats.unshift(chat);
      currentId = chat.id;
    }
    current().messages.push({ role:'user', text, mode });
    save(); renderSidebar();
    $('q').value = '';

    busy = true; $('go').disabled = true;
    const working = mode === 'run'
      ? 'Searching, transcribing and saving' : 'Reading your saved transcripts';
    renderMessages(working);

    try{
      const url = mode === 'run' ? '/run' : '/ask';
      const body = mode === 'run' ? {goal:text} : {question:text};
      const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const data = await res.json();
      current().messages.push({ role:'bot', text: data.result || data.error || 'No response.' });
    }catch(e){
      current().messages.push({ role:'bot', text: 'Something went wrong: ' + e });
    }finally{
      busy = false; $('go').disabled = false;
      save(); renderMessages();
    }
  }

  $('go').onclick = submit;
  $('q').addEventListener('keydown', e => { if(e.key === 'Enter') submit(); });

  // first paint
  renderSidebar();
  renderMessages();
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(PAGE)


@app.route("/run", methods=["POST"])
def run():
    goal = (request.json or {}).get("goal", "").strip()
    if not goal:
        return jsonify(error="Please type what you want the agent to do."), 400
    try:
        return jsonify(result=agent.run_agent(goal))
    except Exception as error:
        return jsonify(error=f"Agent error: {error}"), 500


@app.route("/ask", methods=["POST"])
def ask():
    question = (request.json or {}).get("question", "").strip()
    if not question:
        return jsonify(error="Please type a question."), 400
    try:
        return jsonify(result=tools.ask_knowledge_base(question))
    except Exception as error:
        return jsonify(error=f"Error: {error}"), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
