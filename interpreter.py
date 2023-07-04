import cmd
import json
from typing import IO
import os, glob

import jsonschema

# import DPCLparser.DPCLAst as DPCLAst, DPCLparser.DPCLparser as DPCLparser
from ASTtools import DPCLparser, DPCLAst


# Fix delimiters for tab completion
# taken from https://stackoverflow.com/questions/16826172/filename-tab-completion-in-cmd-cmd-of-python
import readline
readline.set_completer_delims(' \t\n')


class DPCLShell(cmd.Cmd):
    default_prompt = '>>> '
    continuation_prompt = '... '

    prompt = default_prompt
    file = None

    def __init__(self, completekey: str = "tab", stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> None:
        super().__init__(completekey, stdin, stdout)

        self.namespace = DPCLAst.Namespace("", None)
        self.instruction_buffer = ''

        # with open('DPCLschema.json') as schemaFile:
        self.schema = DPCLparser.load_schema('DPCLschema.json')  # TODO add schema file as clarg/config option

    def print(self, *args, **kwargs):
        print(*args, file=self.file, **kwargs)

    def do_json(self, arg):
        self.instruction_buffer += arg
        try:
            data = json.loads(self.instruction_buffer)
            self.schema.validate(data)

        except json.JSONDecodeError as e:
            # Error is unexpected EOF: allow user to continue
            if e.pos == len(self.instruction_buffer):
                self.prompt = self.continuation_prompt
                return

            # TODO shorter error msg
            self.print(e)
        except jsonschema.exceptions.ValidationError as e:
            self.print(e)

        self.prompt = self.default_prompt
        self.instruction_buffer = ''

    def do_load(self, arg):
        self.prompt = '... '
        try:
            data = DPCLparser.load_validate_json(arg, self.schema)
        except FileNotFoundError:
            self.print(f"File {arg} does not exist")
            return
        except jsonschema.exceptions.ValidationError as e:
            self.print(f"Error while validating file:")
            self.print(e)
            return

        self.print(f"Validation of file passed.")
        # self.program = DPCLAst.Program.from_json(data, arg)
        program = DPCLAst.Program.from_json(data, arg)
        try:
            self.namespace.add(program.id,  program)
            program.namespace.parent = self.namespace
        except ValueError:
            self.print("Error: File already loaded")

    def complete_load(self, text, line, begidx, endidx):
        # based on https://stackoverflow.com/questions/16826172/filename-tab-completion-in-cmd-cmd-of-python
        path = text
        if os.path.isdir(text):
            path = os.path.join(path, '*')
        else:
            path += '*'

        return glob.glob(path)

    def do_show(self, arg):
        if not arg:
            self.print(self.namespace.get_as_list())
            return

        self.print(self.namespace.get(arg))


if __name__ == '__main__':
    DPCLShell().cmdloop()
