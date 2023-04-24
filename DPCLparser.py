import json
import jsonschema
import sys
import DPCLAst

# def parse(data):
#     # Must be program root
#     if isinstance(data, list):
#         for item in data:
#             parse(item)
#     elif isinstance(data, dict):
#         pass

if __name__ == "__main__":
    with open('DPCLschema.json') as schema_file:
        schema = json.load(schema_file)
        jsonschema.Draft202012Validator.check_schema(schema)

    with open(sys.argv[1]) as data_file:
        data = json.load(data_file)
        try:
            jsonschema.Draft202012Validator(schema).validate(data)
            print(f"Validation of file passed.")
        except jsonschema.exceptions.ValidationError as e:
            print(f"Error while validating file:")
            print(e)


    parse_result = DPCLAst.Program.from_json(data)
    print(parse_result)
