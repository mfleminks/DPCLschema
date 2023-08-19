from ASTtools.visitor import GenericVisitor
from contextlib import contextmanager

import ASTtools.nodes as nodes


class ASTPrinter(GenericVisitor):
    replace_children = False

    def __init__(self) -> None:
        super().__init__()

        self.indent_ctr = 0
        self.indent_symbol = "\t"
        self.inline_ctr = 0
        self._no_indent = False

    @contextmanager
    def print_inline(self):
        self.inline_ctr += 1
        yield
        self.inline_ctr -= 1

    @contextmanager
    def indented(self):
        self.indent_ctr += 1
        yield
        self.indent_ctr -= 1

    @property
    def inline(self):
        return self.inline_ctr > 0

    @property
    def indent(self):
        return self.indent_symbol * self.indent_ctr

    def print(self, line: str, indent=True, newline=True):
        if self.inline or not newline:
            # print(line, end='')
            end = ''
        else:
            end = '\n'
            # print(self.indent + line)

        if self.inline or not indent or self._no_indent:
            start = ''
        else:
            start = self.indent

        print(start + line, end=end)
        self._no_indent = False

    def visitNode(self, node: nodes.Node):
        raise NotImplementedError

    def plus_minus(self, active: bool):
        return '+' if active else '-'

    def active_inactive(self, active: bool):
        return 'active' if active else 'inactive'

    def visitProgram(self, node: nodes.Program):
        # TOOD body does not contain objects created via REPL
        for n in node.body:
            self.visit(n)
            self.print

    def prevent_next_indent(self):
        self._no_indent = True

    def visitGenericObject(self, node: nodes.GenericObject):
        active = self.active_inactive(node.active)
        self.print(f"({active}) {node.name} [{', '.join(d.full_name for d in node.all_descriptors)}] {{")
        self.indent_ctr += 1

        self.visitChildren(node)

        self.indent_ctr -= 1
        self.print("}")

    def visitPowerFrame(self, node: nodes.PowerFrame):
        active = self.active_inactive(node.active)
        self.print(f"({active}) power {node.name or ''} {{")

        with self.indented():
            self.print(f"holder: {node.holder.name}")
            # self.print(f"action: {node.action.name}")
            self.print(f"action: ", newline=False)
            self.visit(node.action)
            self.print('', indent=False)

            # self.print(f"consequence: {self.visit(node.consequence)}")
            self.print('consequence: ', newline=False)
            # with self.print_inline():
            self.visit(node.consequence)

            self.print('', indent=False)

        self.print("}")

    def visitDeonticFrame(self, node: nodes.DeonticFrame):
        active = self.active_inactive(node.active)
        self.print(f"({active}) {node.position} {node.name or ''} {{")

        with self.indented():
            self.print(f"holder: {node.holder.name}")
            self.print(f"counterparty: {node.counterparty.name}")

            # self.print(f"action: {node.action.name}")
            self.print(f"action: ", newline=False)
            self.visit(node.action)
            self.print('', indent=False)

            # self.print(f"violation: {node._violation}")
            self.print("violation: ", newline=False)
            self.visit(node._violation)
            self.print('', indent=False)

           # self.print(f"fulfillment: {node._fulfillment}")
            self.print("fulfillment: ", newline=False)
            self.visit(node._fulfillment)
            self.print('', indent=False)

            self.print(f"violated: {node.violation_object.active}, fulfilled: {node.fulfillment_object.active}")

        self.print("}")

    def visitReactiveRule(self, node: nodes.ReactiveRule):
        # with self.print_inline():
        #     self.print(f"{self.visit(node.event)} => {self.visit(node.reaction)}")
        self.print('', newline=False)

        self.visit(node.event)

        with self.print_inline():
            self.print(' => ')

        self.visit(node.reaction)

        self.print('', indent=False)

    def visitTransformationalRule(self, node: nodes.TransformationalRule):
        self.print(f"{self.visit(node.antecedent)} -> {self.visit(node.consequent)}")

    def visitActionReference(self, node: nodes.ActionReference):
        agent = f"{(node.agent.resolve().full_name)}." if node.agent else ''
        with self.print_inline():
            self.print(f"{agent}{node.name}")

            if node.args:
                self.print(' {')
                for k, v in node.args.items():
                    self.print(f'{k}: ')
                    self.visit(v)
                    self.print(', ')

                self.print('}')

    def visitProductionEventReference(self, node: nodes.ProductionEventReference):
        # self.print(self.plus_minus(node.new_state) + node.object.resolve().full_name)
        with self.print_inline():
            self.print(self.plus_minus(node.new_state))

        self.prevent_next_indent()
        # with self.indented():
        #     self.visit(node.object)
        self.visit(node.object)

    def visitNamingEventReference(self, node: nodes.NamingEventReference):
        self.visit(node.object)

        with self.print_inline():
            if node.new_state:
                self.print(' gains ')
            else:
                self.print(' loses ')

        self.visit(node.descriptor)

    def visitObjectReference(self, node: nodes.ObjectReference):
        with self.print_inline():
            # try:
            #     self.print(node.resolve().full_name)
            # # TODO double-check the error raised by resolve
            # except ValueError:
            #     self.print(node.name)
            if node.parent:
                self.visit(node.parent)
                self.print('.')
            self.print(node.name)

            if node.refinement:
                self.print('{')
                for k, v in node.refinement.items():
                    self.print(f'{k}: ')
                    self.visit(v)
                    self.print(', ')

                self.print('}')

    def visitAtomicDeclarations(self, node: nodes.AtomicDeclarations):
        self.print(f"atomics: {', '.join(obj.name for obj in node.objects)}")

    def visitCompoundFrame(self, node: nodes.CompoundFrame):
        self.print(f"{node.name} ({', '.join(node.params)}) {{")

        with self.indented():
            self.visitChildren(node)

        self.print("}")

    def visitDescriptorCondition(self, node: nodes.DescriptorCondition):
        self.visit(node.object)

        with self.print_inline():
            if node._in:
                self.print(' gains ')
            else:
                self.print(' loses ')

        self.visit(node.descriptor)
