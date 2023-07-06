import pytest
from interpreter import DPCLShell


@pytest.fixture
def alice_register():
    with open('tests/test_instructions/register_library.txt') as f:
        return f.readlines()


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

    shell.cmdqueue.append
