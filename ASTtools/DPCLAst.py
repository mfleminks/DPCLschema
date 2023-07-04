from __future__ import annotations

from builtins import NotImplementedError
from collections import defaultdict
from copy import deepcopy
from dataclasses import InitVar, dataclass, field
from itertools import count
from typing import ClassVar, Optional, List, TypeAlias, Union, TypeVar


TransitionEvent: TypeAlias = Union['ProductionEvent', 'NamingEvent']


alias_ctr = 0
def auto_alias(prefix: str):
    """
    Generate an auto-incrementing unique ID.
    """
    global alias_ctr

    result = prefix + str(alias_ctr)
    alias_ctr += 1

    return result


POWER_POSITIONS = {'power', 'liability', 'disability', 'immunity'}
def parse(arg):
    """Constructor dispatch"""
    if not isinstance(arg, dict):
        return arg

    constructor = None

    if 'event' in arg and 'reaction' in arg:
        constructor = ReactiveRule
    elif 'condition' in arg and 'conclusion' in arg:
        constructor = TransformationalRule
    elif 'position' in arg:
        if arg['position'] in POWER_POSITIONS:
            constructor = PowerFrame
        else:
            constructor = DeonticFrame
    elif 'plus' in arg or 'minus' in arg:
        constructor = ProductionEvent
    elif 'in' in arg or 'out' in arg:
        constructor = NamingEvent
    elif 'reference' in arg and 'refinement' in arg:
        if arg['reference'].startswith('#'):
            # constructor = RefinedEvent
            constructor = Action
        else:
            constructor = RefinedObject
    elif 'compound' in arg:
        constructor = CompoundFrame
    elif 'scope' in arg and 'name' in arg:
        constructor = ScopedObject

    if not constructor:
        # raise ValueError("No applicable constructor found")
        print(f"No applicable constructor found for {arg}")
        return arg

    return constructor.from_json(arg)


class Namespace:
    """
    A basic namespace to store the attributes of a single scope.

    Parameters
    ----------
    parent : Namespace, optional
        The Namespace object for the enclosing scope
    name : str
        The Namespace's name, should be unique
    """
    def __init__(self, name: str, parent: Optional['Namespace'] = None) -> None:
        self.name = name
        self.__symbol_table = {}
        self.parent = parent
        self.__auto_id_ctr = defaultdict(int)

    def get(self, name: str, recursive=False) -> Union[Node, None]:
        """
        Retrieve an attribute from the namespace.

        Paramerers
        ----------
        name : str
            The name to search for in the namespace
        recursive : bool, default False
            If set to true, the parent Namespace will be searched as well
            The first object that matches will be returned

        Returns
        -------
        DPCLAstNode | None
            The object stored under the specified name, or None if it doesn't exist.
        """
        result = self.__symbol_table.get(name)
        if result is None and self.parent is not None and recursive:
            return self.parent.get(name, True)

        return result

    def as_list(self):
        return list(self.__symbol_table.values())

    def add(self, name: str, value: Node, overwrite = False):
        """
        Add an attribute to the namespace

        Parameters
        ----------
        name : str
            The name of the attribute
        value : DPCLAstNode
            The object itself
        overwrite : bool, default False
            If set to True, a pre-existing object of the same name will be overwritten

        Raises
        ------
        ValueError
            If the name is already in use and overwrite is set to False
        """
        if name in self.__symbol_table and not overwrite:
            raise ValueError(f"Name {name} already exists in namespace {self.full_name}")
        self.__symbol_table[name] = value

    @property
    def full_name(self) -> str:
        if self.parent is None or self.parent.full_name == "":
            return self.name
        return f'{self.parent.full_name}::{self.name}'

    def get_auto_id(self, prefix):
        ctr = self.__auto_id_ctr[prefix]
        self.__auto_id_ctr[prefix] += 1
        return f'{self.full_name}::_{prefix}{ctr}'


class Node:
    # https://stackoverflow.com/a/1045724
    id_gen = count().__next__

    def __init__(self):
        self.__iid = self.id_gen()
        self.aliases = []

    @property
    def children(self) -> list[Node]:
        """
        List of this Node's child nodes
        """
        raise NotImplementedError

    @property
    def internal_id(self) -> int:
        """
        Read-only unique integer ID
        """
        return self.__iid


class Program(Node):
    def __init__(self, name: str, body: list):
        super().__init__()

        self.name = name
        self.body = body

        self.namespace = Namespace()

    @property
    def children(self):
        return self.body

    @classmethod
    def from_json(cls, content: list, filename: str):
        content = [parse(x) for x in content]
        return cls(filename, content)


# T = TypeVar('T', bound='Event')
class Event(Node):
    def __init__(self):
        super().__init__()

        # self.callbacks = []
        self.callbacks = {}

    def add_callback(self, callback: Event):
        # self.callbacks.append(callback)
        self.callbacks[callback.internal_id] = callback

    def remove_callback(self, callback: Event):
        del self.callbacks[callback.internal_id]

    def notify_callbacks(self, **kwargs):
        # TODO this will crash if a callback adds or removes a callback e.g. cross_road
        for callback in self.callbacks.values():
            callback.fire(**kwargs)

    def fire(self, **kwargs):
        self.notify_callbacks(**kwargs)

    # @staticmethod
    # def get_event(cls, **kwargs):
    #     """
    #     Get a specific instance of an event type.
    #     kwargs must be the parameters normally passed to the type's constructor.

    #     Signatures
    #     ----------
    #     NamingEvent.get_event(object: DPCLObject, descriptor: DPCLObject, new_state: bool)
    #     TransitionEvent.get_event(object: DPCLObject, new_state: bool)
    #     """
    #     raise NotImplementedError

    #     self.__fire()

    # def __fire(self):
    #     pass

    # @classmethod
    # def from_json(cls, )


class ProductionEvent(Event):
    def __init__(self, object: DPCLObject, new_state: bool):
        super().__init__()

        self.object = object
        self.new_state = new_state

    def fire(self, **kwargs):
        old_state = self.object.active

        self.object.active = self.new_state

        # Only trigger event if state changed
        if self.new_state != old_state:
            self.notify_callbacks(**kwargs)

    # @staticmethod
    # def get_event(cls, object: DPCLObject, new_state: bool) -> Self:
    #     return object.get_production_event(new_state)


class NamingEvent(Event):
    def __init__(self, object: DPCLObject, descriptor: DPCLObject, new_state: bool):
        super().__init__()

        self.object = object
        self.descriptor = descriptor
        self.new_state = new_state

    def fire(self, simulate=False, object: DPCLObject = None, descriptor: DPCLObject = None, new_state: bool = None, **kwargs):
        """
        Trigger the event, and notify its callbacks if changes were made to the underlying object

        Parameters
        ----------
        simulate : bool
            If true, do not actually edit the underlying object,
            but still notify callbacks if appropriate
        """
        old_state = self.object.has_descriptor(self.descriptor)

        if not simulate:
            self.object.set_descriptor(self.descriptor)
            # if self.new_state:
            #     self.object.add_descriptor(self.descriptor)
            # else:
            #     self.object.remove_descriptor(self.descriptor)

        # TODO code duplcation from ProductionEvent
        # Only trigger event if state changed
        if self.new_state != old_state:
            self.notify_callbacks(**kwargs)

    # @staticmethod
    # def get_event(cls, object: DPCLObject, descriptor: DPCLObject, new_state: bool) -> Self:
    #     return object.get_naming_event(descriptor, new_state)


class Action(Event):
    __instances = {}

    def __init__(self, name: str, refinement: dict, alias: str):
        super().__init__()

        self.name = name
        self.refinement = refinement
        self.aliases.append(alias)

        self.__instances[name] = self

    @classmethod
    def get_event(cls, name: str):
        return cls.__instances[name]

    @classmethod
    def from_json(cls, name: str, refinement: dict, alias: str = None):
        return Action(name, refinement, alias)


# NOTE: probably deprecated
# class Converter(Event):
#     def __init__(self, mapping: dict[str, str]):
#         super().__init__()

#         self.mapping = mapping

#     def fire(self, **kwargs):
#         # https://stackoverflow.com/a/19189356
#         # converted_kwargs = rec_dd()
#         converted_kwargs = {}

#         for new, old in self.mapping.items():
#             old_path = old.split('.')

#             val = kwargs
#             for k in old_path:
#                 val = val[k]

#             new_path = new.split('.')
#             d = converted_kwargs
#             # https://stackoverflow.com/a/37704379
#             for k in new_path[:-1]:
#                 d = d.setdefault(k, {})
#             d[new_path[-1]] = val

#         self.notify_callbacks(**converted_kwargs)


# class EventPlaceholder(Node):
#     def __init__(self, event_type: type[Event], /, **kwargs: dict[str, DPCLObject]):
#         super().__init__()

#         self.event_type = event_type
#         self.kwargs = kwargs

#     def fire(self, **kwargs: dict[str, DPCLObject]):
#         event_args = {}

#         for k, v in self.kwargs.items():
#             event_args[k] = v.resolve(**kwargs)

#         self.event_type.get_event(**event_args).fire()


class NamingEventPlaceholder(Node):
    def __init__(self, object: DPCLObject, descriptor: DPCLObject, new_state: bool):
        super().__init__()

        self.object = object
        self.descriptor = descriptor
        self.new_state = new_state

    def fire(self, **kwargs):
        object = self.object.resolve(**kwargs)
        descriptor = self.descriptor.resolve(**kwargs)

        object.get_naming_event(descriptor, self.new_state).fire()


class ProductionEventPlaceholder(Node):
    def __init__(self, object: DPCLObject, new_state: bool):
        super().__init__()

        self.object = object
        self.new_state = new_state

    def fire(self, **kwargs):
        object = self.object.resolve(**kwargs)

        object.get_production_event(self.new_state).fire()


class DPCLObject(Node):
    # __activation_event = None
    # __deactivation_event = None

    def __init__(self, name: str, active=True):
        super().__init__()

        self.name = name

        self.descriptors: dict[str, DPCLObject] = {}
        # Could also be called descriptum
        self.referents: dict[str, DPCLObject] = {}
        self.namespace = Namespace(name)
        self.active = active

        # Should be indexed with bools
        self.__production_events = [None, None]
        # Should be indexed with [id: str][state: bool]
        self.__naming_events = defaultdict(lambda: [None, None])
        # self.__naming_events = {}

    def add_descriptor(self, descriptor: 'DPCLObject'):
        self.descriptors[descriptor.internal_id] = descriptor
        descriptor.referents[self.internal_id] = self

        for r in self.referents:
            r.get_naming_event(descriptor, True).fire()

    def remove_descriptor(self, descriptor: 'DPCLObject'):
        del self.descriptors[descriptor.internal_id]
        del descriptor.referents[self.internal_id]

        # TODO: clean up code duplication
        for r in self.referents:
            r.get_naming_event(descriptor, False).fire()

    def set_descriptor(self, descriptor: DPCLObject, state: bool):
        if state:
            self.add_descriptor(descriptor)
        else:
            self.remove_descriptor(descriptor)

    def has_descriptor(self, descriptor: DPCLObject):
        return descriptor.internal_id in self.descriptors

    def get_production_event(self, new_state: bool) -> ProductionEvent:
        """
        Get the ProductionEvent responsible for setting this object to new_state.
        Creates a new object if it doesn't already exist.

        Parameters
        ----------
        new_state : bool
            The state this object is set to by the event

        Returns
        -------
        ProductionEvent
            The specified event object
        """
        if self.__production_events[new_state] is None:
            self.__production_events[new_state] = ProductionEvent(self, new_state)

        return self.__production_events[new_state]

    def get_naming_event(self, descriptor: DPCLObject, new_state: bool) -> NamingEvent:
        """
        Get the NamingEvent responsible for adding or removing a descriptor to/from this object.
        Creates a new object if it doesn't already exist.

        Parameters
        ----------
        descriptor : DPCLObject
            The descriptor to be added/removed
        new_state : bool
            Whether to add the descriptor (True) or remove it (False)

        Returns
        -------
        NamingEvent
            The specified event object
        """
        # TODO maybe use defaultdict?
        # if descriptor.internal_id not in self.__naming_events:
        #     self.__naming_events[descriptor.internal_id] = [None, None]

        events = self.__naming_events[descriptor.internal_id]

        if events[new_state] is None:
            events[new_state] = NamingEvent(self, descriptor, new_state)

        return events[new_state]

    def resolve(self, **kwargs) -> DPCLObject:
        """
        Resolve an object reference. For regular DPCLObjects, this is the object itself.
        Subclasses may use kwargs to return a different object.

        Returns
        -------
        DPCLObject
            The object referenced
        """
        return self


class ObjectPlaceholder(DPCLObject):
    def resolve(self, **kwargs) -> DPCLObject:
        return kwargs[self.name]


class PowerFrame(DPCLObject):
    def __init__(self, position: str, action, consequence, holder=None, alias=None):
        super().__init__()

        self.position = position
        self.action = action
        self.consequence = consequence
        self.holder = holder
        self.alias = alias

    @property
    def children(self):
        return [self.action, self.consequence, self.holder]

    @classmethod
    def from_json(cls, position: str, holder: str, action: str, consequence: dict, alias: str = None) -> PowerFrame:
        return cls(position, ObjectPlaceholder(holder), Action.get_event(action))


class DeonticFrame(DPCLObject):
    def __init__(self, position: str, action: Action, holder, counterparty, violation, fulfillment):
        super().__init__()

        self.position = position
        self.action = action


class CompoundFrame(DPCLObject):
    def __init__(self, params: list[str], content: list):
        super().__init__(active=False)

        self.params = params
        self.content = content

    def instantiate(self, args: dict[str, DPCLObject]) -> DPCLObject:
        if not all(p in args for p in self.params):
            # TODO what error should this be?
            raise ValueError

        result = deepcopy(self)

        for name, value in args.items():
            result.namespace.add(name, value, overwrite=True)

    @property
    def children(self):
        return self.content


class TransformationalRule(Node):
    def __init__(self, antecedent: DPCLObject, consequent: DPCLObject):
        super().__init__()

        self.antecedent = antecedent
        self.consequent = consequent

    @property
    def children(self):
        return [self.antecedent, self.consequent]


class ReactiveRule(Node):
    def __init__(self, event: Event, reaction: Event):
        super().__init__()

        self.event = event
        self.reaction = reaction

        # TODO move this to after resolving references
        self.event.add_callback(self.reaction)

    @property
    def children(self):
        return [self.event, self.reaction]


class RefinedObject(DPCLObject):
    """
    An instance of a parametrized compiund frame.
    Starts off inactive.

    Parameters
    ----------
    reference : str
        The name of the compound frame this object is an instance of
    args : dict[str, DPCLObject]
        The arguments used to instantiate this object
    """
    def __init__(self, reference: str, args: dict[str, DPCLObject]):
        super().__init__(False)

        self.reference = reference
        self.args = args


# TODO How is this going to work when the scope can't be resolved statically?
# e.g. referencing holder.parent inside a power
class ScopedObject(ObjectPlaceholder):
    """
    Object representing an object referenced via dot operator, e.g. 'alice.parent'.
    Only exists for use during name resolution


    Parameters
    ----------
    path : list[ObjectPlaceholder]
    """
    def __init__(self, path: list[ObjectPlaceholder]):
        super().__init__()

        self.path = path

    def resolve(self, **kwargs):
        # result
        # for o in self.path:
        #     o.resolve(**kwargs)
        pass
