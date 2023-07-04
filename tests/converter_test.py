from ASTtools import DPCLAst


class TestEvent(DPCLAst.Event):
    def fire(self, **kwargs):
        self.kwargs = kwargs


def test_converter():
    c = DPCLAst.Converter({'object': 'args.item'})
    t = TestEvent()

    c.add_callback(t)
    c.fire(args={'item': 'foo'})

    assert t.kwargs == {'object': 'foo'}
