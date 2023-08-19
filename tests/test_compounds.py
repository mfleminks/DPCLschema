import pytest
from ASTtools import events, visitor
import ASTtools.nodes as nodes


@pytest.fixture
def test_program():
    empty = nodes.CompoundFrame('empty_compound', ['person'], [])
    with_body = nodes.CompoundFrame('with_body', ['person'], [
        nodes.GenericObject('done', []),
        nodes.PowerFrame(position='power',
                         action=nodes.ActionReference('#do_something', None),
                         consequence=nodes.NamingEventReference(nodes.ObjectReference('person'),
                                                                  nodes.ObjectReference('done'),
                                                                  True),
                         holder=nodes.ObjectReference('person'))
    ])
    with_duty = nodes.CompoundFrame('with_duty', ['person'], [
        nodes.DeonticFrame(position='prohibition',
                           holder=nodes.ObjectReference('person'),
                           counterparty=nodes.ObjectReference('bob'),
                           action=nodes.ActionReference('#kill'),
                           violation=nodes.ActionReference('#timeout'),
                           alias='pr_kill')
    ])


    alice = nodes.GenericObject('alice')
    bob = nodes.GenericObject('bob')

    result = nodes.Program('test', [empty, with_body, with_duty, alice, bob])
    result.execute()

    return result


@pytest.fixture
def alice(test_program: nodes.Program):
    return test_program.get_variable('alice')

@pytest.fixture
def bob(test_program: nodes.Program):
    return test_program.get_variable('bob')

@pytest.fixture
def with_body(test_program: nodes.Program):
    return test_program.get_variable('with_body')

@pytest.fixture
def empty_compound(test_program: nodes.Program):
    return test_program.get_variable('empty_compound')

@pytest.fixture
def with_duty(test_program: nodes.Program):
    return test_program.get_variable('with_duty')


def test_instantiation_empty(empty_compound: nodes.CompoundFrame, alice: nodes.GenericObject):
    # baz = nodes.GenericObject('baz', [])
    # empty = empty_compound.instantiate({'bar': baz})
    empty = empty_compound.instantiate({'person': alice})

    assert isinstance(empty, nodes.GenericObject)
    assert empty.get_attribute('person') is alice


def test_instantion_with_body(with_body: nodes.CompoundFrame, alice: nodes.GenericObject):
    instance = with_body.instantiate({'person': alice})
    assert instance is not with_body
    assert instance.get_attribute('person') is alice

    # Uninstantiated compound has empty namespace, so we need to retrieve attributes the dirty way
    assert instance.get_attribute('done') is not with_body.body[0]
    assert with_body.body[0].name == 'done'


def test_instance_identity(empty_compound: nodes.CompoundFrame, alice: nodes.GenericObject, bob: nodes.GenericObject):
    assert empty_compound.get_instance({'person': alice}) is empty_compound.get_instance({'person': alice})
    assert empty_compound.get_instance({'person': alice}) is not empty_compound.get_instance({'person': bob})

def test_deontic_frame(with_duty: nodes.CompoundFrame, alice):
    instance = with_duty.get_instance({'person': alice})

    pr_kill: nodes.DeonticFrame = instance.get_attribute('pr_kill')
    violated = pr_kill.get_attribute('violated')
    assert violated is pr_kill.violation_object
    assert violated.owner is pr_kill
    assert pr_kill is not with_duty.body[0]

    events.ActionHandler.get_event('#kill').fire(holder=alice, _bypass_powers=True)
    # violated._imperative_active = True
    assert pr_kill.active
    assert pr_kill.owner.active

    assert violated._imperative_active
    assert violated.active

    assert violated.owner is pr_kill
