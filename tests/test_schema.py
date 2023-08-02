import json
import pytest
import jsonschema

@pytest.fixture
def schema():
    with open('DPCLschema.json') as f:
        data = json.load(f)

    return jsonschema.Draft202012Validator(data)


def test_(schema):
    pass
