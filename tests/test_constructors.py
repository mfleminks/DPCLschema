import pytest
import ASTtools.nodes as nodes


def test_empty_program():
    node = nodes.from_json([], filename='test.json')
    assert isinstance(node, nodes.Program)
    assert node.body == []
    assert node.name == 'test.json'


def test_atomic_action():
    name = "#borrow"
    node: nodes.ActionReference = nodes.from_json(name)
    assert isinstance(node, nodes.ActionReference)
    assert node.action.name == name


def test_action_args():
    data = {'reference': '#foo', 'refinement': {'item': 'book'}}

    node: nodes.ActionReference = nodes.from_json(data)
    assert isinstance(node, nodes.ActionReference)
    assert node.action.name == '#foo'
    assert 'item' in node.args

    item_arg = node.args['item']
    assert isinstance(item_arg, nodes.ObjectReference)
    assert item_arg.name == 'book'


def test_scoped_action():
    data = {'scope': 'alice', 'action': '#register'}

    node: nodes.ActionReference = nodes.from_json(data)
    assert isinstance(node, nodes.ActionReference)
    assert node.action.name == '#register'
    assert node.parent is not None

    parent = node.parent
    assert isinstance(parent, nodes.ObjectReference)
    assert parent.name == 'alice'
