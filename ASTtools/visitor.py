from __future__ import annotations
from typing import TYPE_CHECKING

from ASTtools.namespace import Namespace
# import ASTtools.nodes as nodes
# from ASTtools.nodes import Node
# from DPCLAst import Node
from builtins import NotImplementedError
from copy import copy


# Prevent recursive imports
if TYPE_CHECKING:
    import ASTtools.nodes as nodes


class GenericVisitor:
    def __init__(self) -> None:
        self.running = False
        self.stack = []

    @property
    def current_depth(self) -> int:
        """
        Current recursion depth of the traversal, including the node
        curerntly being visited (i.e. at the root node current_depth == 1)
        """
        return len(self.stack)

    def run(self, node: nodes.Node):
        if self.running:
            # TODO exception type
            raise Exception("Visitor is already running")

        self.running = True


        result = self.visit(node)

        self.running = False

        return result

    def visit(self, node: nodes.Node):
        if node is None:
            return node

        self.stack.append(node)
        result = node.accept(self)
        self.stack.pop()
        return result

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

    def visitProductionEventReference(self, node: nodes.ProductionEventReference):
        return self.visitNode(node)

    def visitNamingEventReference(self, node: nodes.NamingEventReference):
        return self.visitNode(node)

    def visitActionReference(self, node: nodes.ActionReference):
        return self.visitNode(node)

    def visitObjectReference(self, node: nodes.ObjectReference):
        return self.visitNode(node)

    def visitGenericObject(self, node: nodes.GenericObject):
        return self.visitNode(node)

    def visitAtomicDeclarations(self, node: nodes.AtomicDeclarations):
        return self.visitNode(node)

    def visitDescriptorCondition(self, node: nodes.DescriptorCondition):
        return self.visitNode(node)


class CompoundInstantiator(GenericVisitor):
    def __init__(self) -> None:
        super().__init__()

        # Must be imported locally to avoid circular imports
        from ASTtools.nodes import GenericObject
        self.constructor = GenericObject

    def run(self, node: nodes.CompoundFrame, new_name: str, new_namespace: Namespace) -> nodes.CompoundFrame:
        """
        Parameters
        ----------
        node : CompoundFrame
            The compound to instantiate
        new_namespace : Namepspace
            The namespace for the newly created instance. Should be empty
            except for any arguments that are used for instantiation.
        """
        self.namespace_mapping = {}
        # self.new_name = new_name
        self.new_namespace = new_namespace
        self.new_name = new_name

        return super().run(node)

    def visitNode(self, node: nodes.Node):
        result = copy(node)
        self.visitChildren(node)
        return result

    def visitCompoundFrame(self, node: nodes.CompoundFrame):
        # Ensure we don't modify nested compounds
        if node is not self.stack[0]:
            # return self.visitGenericObject(node)
            return node

        result = self.constructor(self.new_name, node.body.copy())
        result.namespace = self.new_namespace
        result.body = node.body.copy()

        # result = copy(node)

        # result.name = self.new_name
        # result.namespace = self.new_namespace

        self.namespace_mapping[node.namespace] = self.new_namespace

        result.visit_children(self)

        # Must be done after visiting children to avoid recursion
        result.initial_descriptors = [node]
        result.add_initial_descriptors()

        return result

    def visitGenericObject(self, node: nodes.GenericObject):
        result = copy(node)
        result.body = node.body.copy()
        # result.namespace = copy(result.namespace)
        result.namespace = Namespace(node.name, node.namespace.parent)

        self.namespace_mapping[node.namespace] = result.namespace

        # result.visit_children(self)
        self.visitChildren(result)
        return result

    def visitPowerFrame(self, node: nodes.PowerFrame):
        return self.visitGenericObject(node)

    def visitDeonticFrame(self, node: nodes.DeonticFrame):
        return self.visitGenericObject(node)

    # def visitObjectReference(self, node: nodes.ObjectReference):
    #     # if reference points to namespace outside instantiated compound, leave it as is
    #     node.local_namespace = self.namespace_mapping.get(node.local_namespace, node.local_namespace)

    #     # if node.references_param:
    #     #     # node.references_param = False
    #     #     node.object = node.resolve(context=self.new_namespace)

    #     return node


class ASTLinker(GenericVisitor):
    """
    Visitor for assigning owner and parent references to nodes, and parents to namespaces.
    """
    def __init__(self, parent: nodes.Node = None, owner: nodes.Node = None) -> None:
        super().__init__()

        self.parent_node = parent
        self.current_scope = owner

    def visitNode(self, node: nodes.Node):
        node.owner = self.current_scope
        node.parent_node = self.parent_node
        self.parent_node = node

        self.visitChildren(node)

        self.parent_node = node.parent_node

        return node

    def visitProgram(self, node: nodes.Program):
        node.owner = self.current_scope
        node.parent_node = self.parent_node
        self.current_scope = node
        self.parent_node = node

        self.visitChildren(node)

        self.parent_node = node.parent_node
        self.current_scope = node.owner

        return node

    def visitGenericObject(self, node: nodes.GenericObject):
        result = self.visitProgram(node)
        node.namespace.parent = node.owner.namespace
        return result
        # node.owner = self.current_scope
        # self.current_scope = node

        # self.visitChildren(node)

        # self.current_scope = node.owner

        # return node

    def visitCompoundFrame(self, node: nodes.CompoundFrame):
        # return self.visitGenericObject(node)
        # uninstantiated compounds should not be linked
        node.owner = self.current_scope
        node.parent_node = self.parent_node

        return node

    def visitPowerFrame(self, node: nodes.PowerFrame):
        return self.visitGenericObject(node)

    def visitDeonticFrame(self, node: nodes.DeonticFrame):
        return self.visitGenericObject(node)
