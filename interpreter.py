import cmd
import json
from typing import IO

import jsonschema

# import DPCLparser.DPCLAst as DPCLAst, DPCLparser.DPCLparser as DPCLparser
from ASTtools import DPCLparser, DPCLAst


class DPCLShell(cmd.Cmd):
    prompt = '> '
    file = None

    def __init__(self, completekey: str = "tab", stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> None:
        super().__init__(completekey, stdin, stdout)

        with open('DPCLschema.json') as schemaFile:
            self.schema = DPCLparser.load_schema('DPCLschema.json')  # TODO add schema file as clarg/config option

    def print(self, *args, **kwargs):
        print(*args, file=self.file, **kwargs)

    def do_load(self, arg):
        success, data = DPCLparser.load_validate_json(arg, self.schema)
        if success:
            print(f"Validation of file passed.")
        else:
            print(f"Error while validating file:")
            print(data)

        self.program = DPCLAst.Program.from_json(data)

    def do_show(self, arg):
        print(self.program.namespace.get(arg))


if __name__ == '__main__':
    DPCLShell().cmdloop()
