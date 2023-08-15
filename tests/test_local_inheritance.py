import pytest

from ASTtools import exceptions, nodes


def test_inheritance():
    person = nodes.GenericObject('person', [nodes.GenericObject('parent')])
    alice = nodes.GenericObject('alice')
    program = nodes.Program('<test>', [person, alice])

    program.execute()

    with pytest.raises(exceptions.DPCLNameError):
        alice.get_attribute('parent')

    alice.add_descriptor(person)

    assert isinstance(alice.get_attribute('parent'), nodes.GenericObject)
    assert alice.get_attribute('parent') is not person.get_attribute('parent')
