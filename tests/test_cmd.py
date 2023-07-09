import pytest
from interpreter import DPCLShell


def get_instructions(filename):
    with open(f'tests/test_instructions/{filename}.txt') as f:
        return f.readlines()


@pytest.fixture
def alice_register():
    with open('tests/test_instructions/register_library.txt') as f:
        return f.readlines()

@pytest.fixture
def  disabled_power():
    return get_instructions('disable_power')


@pytest.fixture
def shell():
    result = DPCLShell()
    return result


def test_register(shell: DPCLShell, alice_register):
    shell.cmdqueue.extend(alice_register)
    shell.cmdloop()

    alice = shell.program.namespace.get('alice')
    member = shell.program.namespace.get('member')
    assert alice.has_descriptor(member)


def test_disabled_action(shell: DPCLShell, disabled_power):
    shell.cmdqueue.extend(disabled_power)
    shell.cmdloop()

    alice = shell.program.namespace.get('alice')
    member = shell.program.namespace.get('member')
    assert not alice.has_descriptor(member)
