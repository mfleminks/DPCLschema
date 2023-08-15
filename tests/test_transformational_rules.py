import pytest

from ASTtools import nodes


@pytest.fixture
def foo(request: pytest.FixtureRequest):
    return nodes.GenericObject('foo', active=request.param)


@pytest.fixture
def bar(request: pytest.FixtureRequest):
    return nodes.GenericObject('bar', active=request.param)


@pytest.fixture
def object_ref(request: pytest.FixtureRequest):
    return nodes.ObjectReference(request.param)


@pytest.fixture
def descriptor_condition(request: pytest.FixtureRequest):
    return nodes.DescriptorCondition(nodes.ObjectReference('foo'),
                                     nodes.ObjectReference('bar'),
                                     request.param)


@pytest.fixture
def literal(request: pytest.FixtureRequest):
    return nodes.BooleanLiteral(request.param)


@pytest.mark.parametrize('foo', [True, False], indirect=True)
@pytest.mark.parametrize('bar', [True, False], indirect=True)
class TestTransformationalRule:
    def test_object_object(self, foo: nodes.GenericObject, bar: nodes.GenericObject):
        expected = foo._imperative_active or bar._imperative_active
        program = nodes.Program('<test>', [foo, bar,
                                           nodes.TransformationalRule(nodes.ObjectReference('foo'),
                                                                      nodes.ObjectReference('bar'))])
        program.execute()

        assert bar.active == expected

    @pytest.mark.parametrize('descriptor_condition', [True, False], indirect=True)
    def test_object_descriptor(self, foo: nodes.GenericObject, bar, descriptor_condition):
        expected = foo._imperative_active
        program = nodes.Program('<test>', [foo, bar,
                                           nodes.TransformationalRule(nodes.ObjectReference('foo'),
                                                                      descriptor_condition)])
        program.execute()

        assert foo.has_descriptor(bar) == expected
