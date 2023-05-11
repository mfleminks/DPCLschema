import json
from typing import Tuple, Union
import jsonschema
import sys
import ASTtools.DPCLAst as DPCLAst


def load_schema(filename):
    with open(filename) as schema_file:
        schema = json.load(schema_file)
        jsonschema.Draft202012Validator.check_schema(schema)

    return jsonschema.Draft202012Validator(schema)


def load_validate_json(filename: str, schema: jsonschema.Draft202012Validator) -> Tuple[bool, Union[list, Exception]]:
    """
    Load and validate a JSON instance of a DPCL program.

    Parameters
    ----------
    filename : str
        The name of the json file to load
    schema : schema validator
        The validator to use. Should be Draft202012Validator based on DPCLschema.json

    Returns
    -------
    list
        A parsed JSON file representing a DPCL program,
        which should be a list containing a number of dicts

    Raises
    ------
    FileNotFoundError
        If the specified filename does not exist
    jsonschema.exceptions.ValidationError
        If the parsed file is invalid under the given schema


    """
    with open(filename) as data_file:
        data = json.load(data_file)

    schema.validate(data)
    return data



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
