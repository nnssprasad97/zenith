import pathlib

content = pathlib.Path('ZENITH_DOCS.html').read_text(encoding='utf-8')

# Fix hero heading  
old_h1 = '<h1>\n      <span class="cyan">Just A Rather</span><br/>\n      <span class="purple">Very Intelligent System</span>\n    </h1>'
new_h1 = '<h1>\n      <span class="cyan">Zero Latency Engineered</span><br/>\n      <span class="purple">Network for Intuitive Tasks</span>\n    </h1>'
content = content.replace(old_h1, new_h1)

# Fix hero subtitle
old_sub = 'A fully decoupled, microservices-based AI agent with biometric identity, real-time WebRTC voice, local automation, and intelligent web search — all in one command.'
new_sub = 'A fully decoupled, microservices-based AI system with biometric identity, real-time WebRTC voice, local automation, and intelligent web search — all in one command.'
content = content.replace(old_sub, new_sub)

# Fix page title
content = content.replace(
    '<title>ZENITH — System Documentation</title>',
    '<title>ZENITH — Zero Latency Engineered Network for Intuitive Task Handling</title>'
)

# Fix logo in nav
content = content.replace('<div class="logo">J.A.R.V.I.S.</div>', '<div class="logo">ZENITH</div>')
content = content.replace('<div class="logo">ZENITH</div>', '<div class="logo">ZENITH</div>')

# Fix Architecture step 1 identity confirmation
content = content.replace(
    'Identity confirmed as <strong>nnssprasad</strong>.',
    'Identity of <strong>nnssprasad</strong> confirmed.'
)

pathlib.Path('ZENITH_DOCS.html').write_text(content, encoding='utf-8')
print('Done')
