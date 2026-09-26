import re

with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix literal '${API_BASE}' with single quotes back to backticks
content = content.replace("fetch('${API_BASE}", "fetch(`${API_BASE}")
content = content.replace("fetch(\"${API_BASE}", "fetch(`${API_BASE}")
content = content.replace("fetch(`${API_BASE}/api/indices');", "fetch(`${API_BASE}/api/indices`);")
content = content.replace("fetch(`${API_BASE}/api/portfolio/summary');", "fetch(`${API_BASE}/api/portfolio/summary`);")
content = content.replace("fetch(`${API_BASE}/api/analyze',", "fetch(`${API_BASE}/api/analyze`,")
content = content.replace("fetch(`${API_BASE}/api/portfolio/trade',", "fetch(`${API_BASE}/api/portfolio/trade`,")
content = content.replace("fetch(`${API_BASE}/api/portfolio/reset',", "fetch(`${API_BASE}/api/portfolio/reset`,")

with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed API_BASE quotes.")
