import pytest
from REPL.interpreter import DPCLShell


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
def library_borrow():
    return get_instructions('library_borrow')

@pytest.fixture
def library_deadline():
    return get_instructions('library_deadline')


@pytest.fixture
def ban_bowling():
    return get_instructions('ban_bowling')


@pytest.fixture
def homework():
    return get_instructions('homework')


@pytest.fixture
def shell():
    result = DPCLShell(debug=True)
    return result


def test_register(shell: DPCLShell, alice_register):
    shell.cmdqueue.extend(alice_register)
    shell.cmdloop()

    alice = shell.program.get_variable('alice')
    member = shell.program.get_variable('member')
    assert alice.has_descriptor(member)


def test_disabled_action(shell: DPCLShell, disabled_power):
    shell.cmdqueue.extend(disabled_power)
    shell.cmdloop()

    alice = shell.program.get_variable('alice')
    member = shell.program.get_variable('member')
    assert not alice.has_descriptor(member)


def test_library_borrow(shell: DPCLShell, library_borrow):
    shell.cmdqueue.extend(library_borrow)
    shell.cmdloop()

    alice = shell.program.get_variable('alice')
    dracula = shell.program.get_variable('dracula')
    library = shell.program.get_variable('library')

    assert shell.program.get_variable('borrowing').get_instance(args={'item': dracula, 'borrower': alice, 'lender': library}).get_variable('d1').get_variable('fulfilled').active


def test_library_deadline(shell: DPCLShell, library_deadline):
    shell.cmdqueue.extend(library_deadline)
    shell.cmdloop()

    alice = shell.program.get_variable('alice')
    fined = shell.program.get_variable('fined')
    assert alice.has_descriptor(fined)


def test_ban_bowling(shell: DPCLShell, ban_bowling):
    shell.cmdqueue.extend(ban_bowling)
    shell.cmdloop()

def test_homework(shell: DPCLShell, homework):
    shell.cmdqueue.extend(homework)
    shell.cmdloop()
