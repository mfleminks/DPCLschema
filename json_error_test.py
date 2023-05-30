import json


with open('examples/EOF_error.json') as f:
    data = f.read()
try:
    json.loads(data)
except json.decoder.JSONDecodeError as e:
    print(f'{e.pos = }, {len(data) = }')
