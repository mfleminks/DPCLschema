from __future__ import annotations
from typing import TYPE_CHECKING

from ASTtools.namespace import Namespace
# import ASTtools.nodes as nodes
# from ASTtools.nodes import Node
# from DPCLAst import Node
from builtins import NotImplementedError
from copy import copy


if TYPE_CHECKING:
    import ASTtools.nodes as nodes


class GenericVisitor:
    def start(self, node: nodes.Node):
        self.on_start()

        self.visit(node)

        self.on_finish()

    def on_start(self):
        pass

    def on_finish(self):
        pass

    def visit(self, node: nodes.Node):
        if node is None:
            return node

        return node.accept(self)

    def visitChildren(self, node: nodes.Node):
        node.visit_children(self)
        return node

    def visitNode(self, node: nodes.Node):
        return self.visitChildren(node)

    def visitProgram(self, node: nodes.Program):
        return self.visitNode(node)

    def visitCompoundFrame(self, node: nodes.CompoundFrame):
        return self.visitNode(node)

    def visitTransformationalRule(self, node: nodes.TransformationalRule):
        return self.visitNode(node)

    def visitReactiveRule(self, node: nodes.ReactiveRule):
        return self.visitNode(node)

    def visitPowerFrame(self, node: nodes.PowerFrame):
        return self.visitNode(node)

    def visitDeonticFrame(self, node: nodes.DeonticFrame):
        return self.visitNode(node)

    def visitProductionEvent(self, node: nodes.ProductionEvent):
        return self.visitNode(node)

    def visitNamingEvent(self, node: nodes.NamingEvent):
        return self.visitNode(node)

    def visitAction(self, node: nodes.Action):
        return self.visitNode(node)

    def visitObjectReference(self, node: nodes.ObjectReference):
        return self.visitNode(node)

    def visitGenericObject(self, node: nodes.Action):
        return self.visitNode(node)

    # def visitRefinedObject(self, node: nodes.RefinedObject):
    #     return self.visitNode(node)

    # def visitScopedObject(self, node: nodes.ScopedObject):
    #     return self.visitNode(node)


class SymnbolTableBuilder(GenericVisitor):
    def __init__(self, namespace: Namespace = None) -> None:
        super().__init__()

        self.current_namespace = namespace

    # def push_namespace(self, name: str) -> Namespace:
    #     self.current_namespace = Namespace(name, self.current_namespace)
    #     return self.current_namespace

    def push_namespace(self, namespace: Namespace) -> Namespace:
        """
        Set the current namespace, and add parent namespace
        """
        namespace.parent = self.current_namespace
        self.current_namespace = namespace
        return namespace

    def pop_namespace(self) -> None:
        self.current_namespace = self.current_namespace.parent

    def visitProgram(self, node: nodes.Program):
        # node.namespace = self.push_namespace(node.name)
        self.push_namespace(node.namespace)
        # node.init_root_descriptor()

        self.visitChildren(node)

        self.pop_namespace()

    def visitGenericObject(self, node: nodes.GenericObject):
        self.current_namespace.add(node.name, node)

        node.namespace = self.push_namespace(node.namespace)

        self.visitChildren(node)

        self.pop_namespace()

        return node

    def visitObjectReference(self, node: nodes.ObjectReference):
        node.local_namespace = self.current_namespace

        return node

    def visitDeonticFrame(self, node: nodes.DeonticFrame):
        raise NotImplementedError

    def visitCompoundFrame(self, node: nodes.CompoundFrame):
        self.current_namespace.add(node.name, node)

        node.namespace = self.push_namespace(node.namespace)

        for name in node.params:
            # TODO figure out param type; can't import nodes here
            node.namespace.add(name, None)

        self.visitChildren(node)

        self.pop_namespace()

        return node

    def visitPowerFrame(self, node: nodes.PowerFrame):
        # try:
        #     self.current_namespace.add(node.name, node)
        # except ValueError as e:
        #     print(e)

        self.current_namespace.add(node.name, node)

        node.namespace = self.push_namespace(node.namespace)
        node.namespace.add('holder', node.holder)

        self.visitChildren(node)

        self.pop_namespace()

        return node


class NameResolver(GenericVisitor):
    def __init__(self, namespace: Namespace = None) -> None:
        super().__init__()

        self.in_slot = None
        self.error = False

        self.current_namespace = namespace

    def on_finish(self):
        super().on_finish()

        if self.error:
            # TODO exception type
            raise Exception

    def pop_namespace(self) -> None:
        self.current_namespace = self.current_namespace.parent

    def visitProgram(self, node: nodes.Program):
        self.current_namespace = node.namespace

        self.visitChildren(node)

        self.pop_namespace()

    def visitObjectReference(self, node: nodes.ObjectReference):
        node.resolve(save=True)

        return node
        # try:
        #     node.object = self.current_namespace.get(node.name)
        # except KeyError:
        #     if self.in_slot != 'consequence':
        #         self.error = True
        #         print("cannot resolve reference")


class ASTCopier(GenericVisitor):
    """
    Visitor that returns a copy of a node tree.

    Only child nodes are deep copied. All other attributes are shallow copied,
    i.e.original.name is copy.name
    """
    def visitNode(self, node: nodes.Node):
        node = copy(node)
        node.visit_children(self)
        return node
