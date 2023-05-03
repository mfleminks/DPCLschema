import json
import jsonschema
import sys
import ASTtools.DPCLAst as DPCLAst


def load_schema(filename):
    with open(filename) as schema_file:
        schema = json.load(schema_file)
        jsonschema.Draft202012Validator.check_schema(schema)

    return jsonschema.Draft202012Validator(schema)


def load_validate_json(filename: str, schema: jsonschema.Draft202012Validator):
    """
    Load and validate a JSON instance of a DPCL program.

    return: A 2-tuple containing:
        A bool indicicating success
        A parsed JSON file on success, or None if the json is invalid.
    """
    with open(filename) as data_file:
        data = json.load(data_file)
        try:
            schema.validate(data)
            return True, data
        except jsonschema.exceptions.ValidationError as e:
            return False, e


if __name__ == "__main__":
    schema = load_schema('DPCLschema.json')
    success, data = load_validate_json(sys.argv[1], schema)
    if success:
        print(f"Validation of file passed.")
    else:
        print(f"Error while validating file:")
        print(data)

    parse_result = DPCLAst.Program.from_json(data)
    print([g.id for g in parse_result.globals])
