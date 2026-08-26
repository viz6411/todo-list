import sys
sys.path.insert(0, 'tests')
# Check what the test mocks do
with open('tests/test_oauth2.py') as f:
    content = f.read()
    for i, line in enumerate(content.split('\n'), 1):
        if 'open_by' in line:
            print(f"{i}: {line.strip()}")
