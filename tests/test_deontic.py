import pytest

from ASTtools import events, nodes


@pytest.mark.parametrize('position,condition', [('duty', 'fulfilled'),
                                                ('prohibition', 'violated')])
class TestDeontic:
    @pytest.fixture
    @staticmethod
    def test_program(position):
        # frame = nodes.DeonticFrame(position, holder=)

        # alice = nodes.GenericObject('alice')
        # bob = nodes.GenericObject('bob')
        # result = nodes.Program('<test>', [alice, bob])
        result: nodes.Program = nodes.from_json([
            {"atomics": ["alice", "bob"]},
            {
                "position": "power",
                "action": "#foo",
                "consequence": {"plus": "self"}
            },
            {
                "position": position,
                "action": "#foo",
                "alias": "simple"
            }
        ], filename="test")

        result.execute()
        return result

    @pytest.fixture
    @staticmethod
    def simple(test_program: nodes.Program):
        return test_program.get_variable("simple")

    def test_action(self, simple: nodes.DeonticFrame, test_program, condition, position):
        events.ActionHandler.get_event("#foo").fire(holder=simple)

        assert simple.get_attribute(condition).active
