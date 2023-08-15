import pytest
import ASTtools.nodes as nodes


def test_empty_program():
    node = nodes.from_json([], filename='test.json')
    assert isinstance(node, nodes.Program)
    assert node.body == []
    assert node.name == 'test.json'


class TestAction:
    def test_atomic_action(self):
        name = "#borrow"
        node: nodes.ActionReference = nodes.from_json(name)
        assert isinstance(node, nodes.ActionReference)
        assert node.name == name

    def test_action_args(self):
        data = {'event': '#foo', 'refinement': {'item': 'book'}}

        node: nodes.ActionReference = nodes.from_json(data)
        assert isinstance(node, nodes.ActionReference)
        assert node.name == '#foo'
        assert 'item' in node.args

        item_arg = node.args['item']
        assert isinstance(item_arg, nodes.ObjectReference)
        assert item_arg.name == 'book'

    def test_scoped_action(self):
        data = {'agent': 'alice', 'action': '#register'}

        node: nodes.ActionReference = nodes.from_json(data)
        assert isinstance(node, nodes.ActionReference)
        assert node.name == '#register'
        # assert node.agent is not None

        agent = node.agent
        assert isinstance(agent, nodes.ObjectReference)
        assert agent.name == 'alice'


@pytest.mark.parametrize("new_state", [True, False])
def test_naming_event(new_state):
    data = {'entity': 'alice', 'gains': new_state, 'descriptor': 'member'}

    node: nodes.NamingEventReference = nodes.from_json(data)

    assert isinstance(node, nodes.NamingEventReference)
    assert node.object.name == 'alice'
    assert node.descriptor.name == 'member'
    assert node.new_state == new_state

@pytest.mark.parametrize("new_state", [True, False])
def test_descriptor_condition(new_state):
    data = {'entity': 'alice', 'has': new_state, 'descriptor': 'member'}

    node: nodes.DescriptorCondition = nodes.from_json(data)

    assert isinstance(node, nodes.DescriptorCondition)
    assert node.object.name == 'alice'
    assert node.descriptor.name == 'member'
    assert node._in == new_state

@pytest.mark.parametrize("operator,state", [("plus", True), ("minus", False)])
def test_production_event(operator, state):
    data = {operator: "foo"}

    node: nodes.ProductionEventReference = nodes.from_json(data)

    assert isinstance(node, nodes.ProductionEventReference)
    assert node.new_state == state
    assert node.object.name == "foo"

@pytest.mark.parametrize("name", ["alice", "bob"])
class TestObjectReference:
    scopes = pytest.mark.parametrize('scope', ['foo', 'bar'])
    refinements = pytest.mark.parametrize('refinement', [{'person': 'alice'}, {'item': 'book'}, {'person': 'alice', 'item': 'book'}])

    def test_object_reference_simple(self, name):
        data = name

        node: nodes.ObjectReference = nodes.from_json(data)

        assert isinstance(node, nodes.ObjectReference)
        assert node.name == name
        assert node.parent is None
        assert node.refinement == {}

    @scopes
    def test_object_reference_dot(self, scope, name):
        data = {'scope': scope, 'name': name}

        node: nodes.ObjectReference = nodes.from_json(data)

        assert isinstance(node, nodes.ObjectReference)
        assert node.name == name
        assert node.parent.name == scope
        assert node.refinement == {}

    @refinements
    def test_object_reference_refined(self, name, refinement):
        data = {'object': name, 'refinement': refinement}

        node: nodes.ObjectReference = nodes.from_json(data)

        assert isinstance(node, nodes.ObjectReference)
        assert node.name == name
        assert node.parent is None
        for k, v in node.refinement.items():
            assert isinstance(v, nodes.ObjectReference)
            assert v.name == refinement[k]

    @scopes
    @refinements
    def test_object_reference_refined_local(self, scope, name, refinement):
        data = {'scope': scope, 'name': {'object': name, 'refinement': refinement}}

        node: nodes.ObjectReference = nodes.from_json(data)

        assert isinstance(node, nodes.ObjectReference)
        assert node.name == name
        assert node.parent.name is scope
        for k, v in node.refinement.items():
            assert isinstance(v, nodes.ObjectReference)
            assert v.name == refinement[k]

    @scopes
    @refinements
    def test_object_reference_refined_scope(self, scope, name, refinement):
        data = {'scope': {'object': scope, 'refinement': refinement}, 'name': name }

        node: nodes.ObjectReference = nodes.from_json(data)

        assert isinstance(node, nodes.ObjectReference)
        assert node.name == name
        assert node.refinement == {}

        assert node.parent.name is scope
        for k, v in node.parent.refinement.items():
            assert isinstance(v, nodes.ObjectReference)
            assert v.name == refinement[k]


@pytest.mark.parametrize('consequence,consequence_type', [
    ({'plus': 'foo'}, nodes.ProductionEventReference),
    ({'entity': 'alice', 'gains': True, 'descriptor': 'member'}, nodes.NamingEventReference)
    ])
class TestPowerFrame:
    def test_no_holder(self, consequence, consequence_type):
        data = {'position': 'power', 'action': '#foo', 'consequence': consequence}
        node: nodes.PowerFrame = nodes.from_json(data)

        assert isinstance(node, nodes.PowerFrame)

        assert isinstance(node.holder, nodes.ObjectReference)
        assert node.holder.name == '*'

        assert isinstance(node.action, nodes.ActionReference)
        assert node.action.name == '#foo'

        assert isinstance(node.consequence, consequence_type)

    @pytest.mark.parametrize('holder', [
        'alice',
        {'scope': 'alice', 'name': 'parent'},
        {'object': 'mayor', 'refinement': {'city': 'amsterdam'}}])
    def test_holder(self, consequence, consequence_type, holder):
        data = {'position': 'power', 'action': '#foo', 'consequence': consequence, 'holder': holder}
        node: nodes.PowerFrame = nodes.from_json(data)

        assert isinstance(node, nodes.PowerFrame)

        assert isinstance(node.holder, nodes.ObjectReference)
        assert node.holder.name != '*'
        assert node.selectors['holder'] is node.holder

        assert isinstance(node.action, nodes.ActionReference)
        assert node.action.name == '#foo'

        assert isinstance(node.consequence, consequence_type)

    @pytest.mark.parametrize('args', [{}, {'item': 'book'}, {'arg1': 'foo', 'arg2': 'bar'}])
    def test_action_args(self, consequence, consequence_type, args):
        data = {'position': 'power', 'action': {'event': '#foo', 'refinement': args}, 'consequence': consequence}
        node: nodes.PowerFrame = nodes.from_json(data)

        assert isinstance(node, nodes.PowerFrame)

        assert isinstance(node.holder, nodes.ObjectReference)
        assert node.holder.name == '*'
        assert node.selectors['holder'] is node.holder

        assert isinstance(node.action, nodes.ActionReference)
        assert node.action.name == '#foo'

        for k, v in args.items():
            assert isinstance(node.selectors[k], nodes.ObjectReference)
            assert node.selectors[k].name == v

        assert isinstance(node.consequence, consequence_type)


@pytest.mark.parametrize('name', ['foo', 'bar',])
class TestGenericObject:
    def test_empty(self, name):
        data = {'object': name, 'content': []}
        node = nodes.from_json(data)

        assert isinstance(node, nodes.GenericObject)
        assert not isinstance(node, nodes.CompoundFrame)

        assert node.name == name
        assert node._imperative_active == True
        assert node.body == []

    @pytest.mark.parametrize('content,types', [
        ([{'atomics': ['foo', 'bar']}], [nodes.AtomicDeclarations]),
        ([{'object': 'foo', 'content': []}], [nodes.GenericObject])
    ])
    def test_with_body(self, name, content, types):
        data = {'object': name, 'content': content}
        node = nodes.from_json(data)

        assert isinstance(node, nodes.GenericObject)
        assert not isinstance(node, nodes.CompoundFrame)

        assert node.name == name
        assert node._imperative_active == True
        assert len(node.body) == len(content)

        for statement, t in zip(node.body, types):
            assert isinstance(statement, t)

    @pytest.mark.parametrize('params', [['arg1'], ['arg1', 'arg2']])
    class TestCompoundFrame:
        def test_empty(self, name, params):
            data = {'object': name, 'params': params, 'content': []}
            node: nodes.CompoundFrame = nodes.from_json(data)

            assert isinstance(node, nodes.CompoundFrame)

            assert node.name == name
            assert node.body == []
            assert node.params == params
            assert not node._imperative_active
