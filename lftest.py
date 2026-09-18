import json, urllib.request, sys
cfg = json.load(open("C:/Users/student/.claude.json", encoding="utf-8"))
srv = cfg["projects"]["C:/Users/student/Documents/GitHub/my-story-marker"]["mcpServers"]["langfuse"]
url, hdrs = srv["url"], dict(srv.get("headers", {}))
hdrs.update({"Content-Type":"application/json","Accept":"application/json, text/event-stream"})

def call(payload, sid=None):
    h = dict(hdrs)
    if sid: h["Mcp-Session-Id"] = sid
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=h, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, r.headers.get("Mcp-Session-Id"), r.read().decode()[:4000]
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode()[:1000]
    except Exception as e:
        return "ERR", None, repr(e)

st, sid, body = call({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}})
print("INITIALIZE ->", st)
print(body[:1500])
if str(st).startswith("2"):
    st2, _, body2 = call({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}, sid)
    print("\nTOOLS/LIST ->", st2)
    print(body2[:3000])
