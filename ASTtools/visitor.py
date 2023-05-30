from DPCLAst import DPCLAstNode
from builtins import NotImplementedError


class GenericVisitor:
    def visit(self, node: DPCLAstNode):
        try:
            node.accept(self)
        except NotImplementedError:
            self.visitChildren(node)

    def visitChildren(self, node: DPCLAstNode):
        for c in node.children:
            self.visit(c)

    def visitProgram(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitProgram(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitCompoundFrame(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitTransformationalRule(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitReactiveRule(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitPowerFrame(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitDeonticFrame(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitProductionEvent(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitNamingEvent(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitRefinedObject(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitScopedObject(self, node: DPCLAstNode):
        raise NotImplementedError

    def visitRefinedEvent(self, node: DPCLAstNode):
        raise NotImplementedError
