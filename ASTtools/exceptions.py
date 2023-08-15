class DPCLException(Exception):
    """
    Base class for DPCL's custom exceptions
    """
    pass


class LogicError(DPCLException):
    """
    Exception for representing logical conflicts, such as boolean being
    simultaneously True and False
    """
    pass


class DPCLTypeError(DPCLException):
    """
    Exception for when an operation is attempted on an invalid operand, such as
    assigning a descriptor to the wildcard `*`
    """
    pass


class DPCLNameError(DPCLException):
    """
    Exception for when a name can't be found in the namespace being searched,
    or if multiple objects with the same FQN are defined.
    """
    pass

class DescriptorError(DPCLException):
    """
    Exception for when an illegal operation involving descriptors is attempted,
    such as removing a descriptor from itself.
    """
    pass
