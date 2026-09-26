import re
with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace("if (!openaiKey) {\n      setError('Please provide an OpenAI API key in the header to run agent analysis.');\n      return;\n    }", "// Frontend API Key is now optional. If blank, backend uses its secure environment variable.")

c = c.replace('placeholder="sk-proj-..."', 'placeholder="sk-proj-... (Optional if set in backend)"')

with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(c)
