import json
import jsonschema
import os


with open('DPCLschema.json') as schemaFile:
    schema = json.load(schemaFile)
    v = jsonschema.Draft202012Validator.check_schema(schema)
    print("Schema is valid")


# with open('DPCLexamples.json') as dataFile:
#     data = json.load(dataFile)
#     jsonschema.Draft202012Validator(schema).validate(data)
#     print("Validation of test set passed.")


for filename in os.listdir('examples'):
    filename = os.path.join('examples', filename)

    with open(filename) as dataFile:
        data = json.load(dataFile)
        try:
            jsonschema.Draft202012Validator(schema).validate(data)
            print(f"Validation of '{filename}' passed.")
        except jsonschema.exceptions.ValidationError as e:
            print(f"Error while validating '{filename}':")
            print(e)
