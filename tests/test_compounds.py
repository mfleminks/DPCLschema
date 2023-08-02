import pytest
import ASTtools.nodes as nodes


@pytest.fixture
def empty_compound():
    return nodes.CompoundFrame('empty_compound', ['bar'], [])


@pytest.fixture
def with_body():
    return nodes.CompoundFrame('foo', ['person'], [
        nodes.GenericObject('done', []),
        nodes.PowerFrame(position='power',
                         action=nodes.ActionReference('#do_something', None),
                         consequence=nodes.NamingEventPlaceholder(nodes.ObjectReference('person'),
                                                                  nodes.ObjectReference('done'),
                                                                  True),
                         holder=nodes.ObjectReference('person'))
    ])


@pytest.fixture
def alice():
    return nodes.GenericObject('alice')


def test_instantiation_empty(empty_compound: nodes.CompoundFrame):
    empty = empty_compound.instantiate({'bar': nodes.GenericObject('baz', [])})
    isinstance(empty, nodes.GenericObject)


def test_instantion_with_body(with_body: nodes.CompoundFrame, alice: nodes.GenericObject):
    instance = with_body.instantiate({'person': alice})
    nodes.ActionReference('#do_something', alice).fire()

def test_retrieval():
    pass
