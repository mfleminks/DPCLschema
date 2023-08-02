from __future__ import annotations
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from itertools import count
from builtins import NotImplementedError
from typing import TYPE_CHECKING

import ASTtools.visitor as visitor
from ASTtools.visitor import GenericVisitor
from ASTtools.namespace import Namespace


# if TYPE_CHECKING:
#     from visitor import GenericVisitor


POWER_POSITIONS = {'power', 'liability', 'disability', 'immunity'}


def from_json(data, *args, **kwargs) -> Node:
    """
    Construct a node from a JSON object or list, as appropriate for the node type

    Parameters
    ----------
    data : list | dict | str
        A JSON object representing an AST subtree, as per the schema

    Returns
    -------
        A Node object representing the parsed subtree

    Raises
    ------
    ValueError
        When no applicable constructor can be found
    """
    if isinstance(data, list):
        return Program.from_json(data, *args, **kwargs)

    constructor = None

    if isinstance(data, str):
        if data.startswith('#'):
            constructor = ActionReference
        else:
            constructor = ObjectReference

        return constructor.from_json(data)

    if 'event' in data and 'reaction' in data:
        constructor = ReactiveRule
    elif 'reaction' in data:
        return from_json(data['reaction'])
    elif 'condition' in data and 'conclusion' in data:
        constructor = TransformationalRule
    elif 'position' in data:
        if data['position'] in POWER_POSITIONS:
            constructor = PowerFrame
        else:
            constructor = DeonticFrame
    elif 'plus' in data or 'minus' in data:
        constructor = ProductionEventPlaceholder
    elif 'in' in data or 'out' in data:
        constructor = NamingEvent
    elif 'reference' in data and 'refinement' in data:
        if data['reference'].startswith('#'):
            constructor = ActionReference
        else:
            constructor = ObjectReference
    elif 'compound' in data:
        if 'params' in data:
            constructor = CompoundFrame
        else:
            constructor = GenericObject
    elif 'scope' in data:
        if 'name' in data:
            constructor = ObjectReference
        elif 'action' in data:
            constructor = ActionReference

    if not constructor:
        raise ValueError(f"No applicable constructor found for {data}")
        # print(f"No applicable constructor found for {data}")
        # return data

    try:
        return constructor.from_json(data, *args, **kwargs)
    except Exception as e:
        # print(e)
        print(data)

        raise e


class Node:
    """
    Generic AST node

    Attributes
    ----------
    children : list[str]
        The node's children, as list of strings equal to the attributes' names
    """
    # https://stackoverflow.com/a/1045724
    id_gen = count().__next__

    children: list[str] = []

    def __init__(self):
        self.__iid = self.id_gen()
        self.aliases = []

    @property
    def internal_id(self) -> int:
        """
        Read-only unique integer ID
        """
        return self.__iid

    def visit_children(self, visitor: GenericVisitor):
        """
        Visit each of the node's child nodes, and replace them with the return values

        Parameters
        ----------
        visitor : GenericVisitor
            The visitor object that will visit the children
        """
        for name in self.children:
            child = getattr(self, name)
            if child is None:
                continue
            setattr(self, name, visitor.visit(child))

    def accept(self, visitor: GenericVisitor):
        """
        Accepts a visitor object, and calls its visit* method,
        as determined by this node's type.

        Parameters
        ----------
        visitor : GenericVisitor
            the object visiting this node
        """
        self.visit_children(visitor)

        return self

    @classmethod
    def from_json(cls, data, *args, **kwargs) -> Node:
        raise NotImplementedError


class Program(Node):
    # TODO docstring
    # TODO make subclass of GenericObject
    def __init__(self, name: str, body: list):
        super().__init__()

        self.name = name
        self.body = body

        self.namespace = Namespace(self.name)
        self.init_root_descriptor()

    def init_root_descriptor(self):
        self.namespace.add('*', root_descriptor)

    def visit_children(self, visitor: GenericVisitor):
        for i, v in enumerate(self.body):
            # print(f"visiting program body {i} {v}")
            self.body[i] = visitor.visit(v)

    # @property
    # def children(self):
    #     return self.body

    @classmethod
    def from_json(cls, content: list, filename: str):
        content = [from_json(x) for x in content]
        return cls(filename, content)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitProgram(self)


# TODO rename baseevent
class Event(Node):
    # TODO make ABC?
    def __init__(self):
        super().__init__()

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

    @staticmethod
    def get_event(**kwargs):
        """
        Get a specific instance of an event type.
        kwargs must be the parameters normally passed to the type's constructor.

        Signatures
        ----------
        NamingEvent.get_event(object: GenericObject, descriptor: GenericObject, new_state: bool)
        TransitionEvent.get_event(object: GenericObject, new_state: bool)
        Action.get_event(name: str)
        """
        raise NotImplementedError

    #     self.__fire()

    # def __fire(self):
    #     pass

    # @classmethod
    # def from_json(cls, arg):


class ProductionEvent(Event):
    children = ['object']

    def __init__(self, object: GenericObject, new_state: bool):
        super().__init__()

        self.object = object
        self.new_state = new_state

    def fire(self, **kwargs):
        old_state = self.object.active

        self.object.active = self.new_state

        # Only trigger event if state changed
        if self.new_state != old_state:
            self.notify_callbacks(**kwargs)

    @staticmethod
    def get_event(object: GenericObject, new_state: bool) -> ProductionEvent:
        return object.get_production_event(new_state)

    @classmethod
    def from_json(cls, arg):
        if 'plus' in arg:
            object = arg['plus']
            new_state = True
        else:
            object = arg['minus']
            new_state = False

        object = from_json(object)

        return cls(object, new_state)


class NamingEvent(Event):
    children = ['object', 'descriptor']

    def __init__(self, object: GenericObject, descriptor: GenericObject, new_state: bool):
        super().__init__()

        self.object = object
        self.descriptor = descriptor
        self.new_state = new_state

    def fire(self, simulate=False, object: GenericObject = None, descriptor: GenericObject = None, new_state: bool = None, **kwargs):
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
            self.object.set_descriptor(self.descriptor, self.new_state)
            # if self.new_state:
            #     self.object.add_descriptor(self.descriptor)
            # else:
            #     self.object.remove_descriptor(self.descriptor)

        # TODO code duplcation from ProductionEvent
        # Only trigger event if state changed
        if self.new_state != old_state:
            self.notify_callbacks(**kwargs)

    @classmethod
    def from_json(cls, arg):
        entity = arg['entity']
        if 'in' in arg:
            descriptor = arg['in']
            new_state = True
        else:
            descriptor = arg['out']
            new_state = False

        entity = from_json(entity)
        descriptor = from_json(descriptor)

        return cls(entity, descriptor, new_state)

    @staticmethod
    def get_event(object: GenericObject, descriptor: GenericObject, new_state: bool) -> NamingEvent:
        return object.get_naming_event(descriptor, new_state)


# TODO rename genericevent
class Action(Event):
    __instances = {}

    def __init__(self, name: str, refinement: dict = None, alias: str = None):
        super().__init__()

        self.name = name
        self.refinement = refinement or {}  # NOTE this is no longer an inherent part of the action
        self.powers: dict[str, PowerFrame] = {}
        if alias:
            self.aliases.append(alias)

        self.__instances[name] = self

    def fire(self, **kwargs):
        if not any(p.notify(**kwargs) for p in self.powers.values()):
            print(f"Action {self.name} not enabled by any powers")
            return False

        return super().fire(**kwargs)

    def add_power(self, power: PowerFrame):
        self.powers[power.internal_id] = power

    def remove_power(self, power: PowerFrame):
        del self.powers[power.internal_id]

    @classmethod
    def get_event(cls, name: str) -> Action:
        if name not in cls.__instances:
            cls.__instances[name] = cls(name)

        return cls.__instances[name]

    @classmethod
    def from_json(cls, arg: dict):
        if isinstance(arg, str):
            return Action(arg)

        name = arg['reference']
        refinement = arg['refinement']
        alias = arg.get('alias', None)
        return Action(name, refinement, alias)


# TODO refactor to not inherit Event, to avoid dealing with callbacks
class ActionReference(Event):
    """
    Parameters
    ----------
    name : str
        The name of the event referenced. Must begin with '#'
    parent : ObjectReference, optional
        A reference to the agent invoking this action.
        If ommited, this object represents a global generic event.
    args : dict, optional
        Any arguments passed to the event
    """
    def __init__(self, name: str, parent: ObjectReference = None, args: dict[str, ObjectReference] = None):
        super().__init__()

        self.action = Action.get_event(name)
        self.parent = parent
        self.args = args or {}

    def fire(self, context: Namespace = None):
        args = {name: ref.resolve() for name, ref in self.args.items()}
        if self.parent is not None:
            args = {**args, 'holder': self.parent.resolve(context=context)}
        self.action.fire(**args)

    def visit_children(self, visitor: GenericVisitor):
        self.parent = visitor.visit(self.parent)

        for name, ref in self.args.items():
            self.args[name] = ref.accept(visitor)

    @classmethod
    def from_json(cls, arg: dict | str):
        if 'scope' in arg:
            parent = from_json(arg['scope'])
            arg = arg['action']
        else:
            parent = None
        # action = arg['action']

        if isinstance(arg, str):
            name = arg
            refinement = {}
        else:
            name = arg['reference']
            refinement = arg['refinement']

        refinement = {name: ObjectReference.from_json(value) for name, value in refinement.items()}

        return ActionReference(name, parent, refinement)

    def __repr__(self) -> str:
        return f"action: ({self.parent}).{self.action.name}"


class NamingEventPlaceholder(Node):
    children = ['object', 'descriptor']

    def __init__(self, object: ObjectReference, descriptor: ObjectReference, new_state: bool):
        super().__init__()

        self.object = object
        self.descriptor = descriptor
        self.new_state = new_state

    def fire(self, context: Namespace):
        object = self.object.resolve(context=context)
        descriptor = self.descriptor.resolve(context=context)

        # print(f"calling {object} {'in' if self.new_state else 'out'} {descriptor}")

        object.get_naming_event(descriptor, self.new_state).fire()

    @classmethod
    def from_json(cls, arg):
        entity = from_json(arg['entity'])

        if 'in' in arg:
            descriptor = arg['in']
            new_state = True
        else:
            descriptor = arg['out']
            new_state = False

        descriptor = from_json(descriptor)

        return cls(entity, descriptor, new_state)

    def __repr__(self) -> str:
        return f"NamingEventReference( {self.object}, {self.descriptor}, {self.new_state} )"


class ProductionEventPlaceholder(Node):
    children = ['object']

    def __init__(self, object: GenericObject, new_state: bool):
        super().__init__()

        self.object = object
        self.new_state = new_state

    def fire(self, **kwargs):
        object = self.object.resolve(**kwargs)

        object.get_production_event(self.new_state).fire()

    @classmethod
    def from_json(cls, arg):
        if 'plus' in arg:
            object = arg['plus']
            new_state = True
        else:
            object = arg['minus']
            new_state = False

        object = from_json(object)

        return cls(object, new_state)


# ABCs
class BaseBoolean(metaclass=ABCMeta):
    """
    Base class for a boolean expression, for use as condition/conclustion by trasformational rules.

    Current uses include:
        object (active/inactive)
        descriptor (in/out)

    Attributes
    active : bool
        The current value of the boolean expression.
    """
    def __init__(self, active: bool) -> None:
        self._active = active
        self._transformational_ctr = 0

    def set_state(self, active: bool, transformational: bool) -> None:
        """
        Change this boolean's state. This is handled differently depending on
        whether the state is changes reactively or declaratively
        (i.e. by transformational rule).

        For reactive rules, an internal bool is set to the `active` argument.

        For transformational rules, a counter is incremented/decremented to
        ensure consistency when multiple rules are affecting this object.

        The bool's true state depends on this counter:
            positive : True
            negative : False
            zero     : determined by the internal variable set reactively

        Parameters
        ----------
        active : bool
            The object's new state
        transformational : bool
            True for transformational rules, False for reactive rules.

        Raises
        ------
        ValueError
            When a transformational rule sets this object to active while
            the counter is negative, or vice versa, indicating a logical contradiction.
        """
        if not transformational:
            self._active = active
            return

        ctr_change = 1 if active else -1
        # Check if signs are different, which implies t. rules are
        # assigning contradictory states
        if ctr_change * self._transformational_ctr < 0:
            raise ValueError("Contradictory transformational rules")

        self._transformational_ctr += ctr_change

    @property
    @abstractmethod
    def active(self) -> bool:
        """
        The current value of the boolean expression.
        """
        # Transformational takes precedence over reactive
        if self._transformational_ctr == 0:
            return self._active

        return self._transformational_ctr > 0

    @abstractmethod
    def get_bool_event(self, state) -> Event:
        """

        """
        raise NotImplementedError


class EventListener(metaclass=ABCMeta):
    """
    TODO docstring
    """
    def __init__(self):
        super().__init__()

    @abstractmethod
    def notify(self, **kwargs):
        """
        Notify the listener that an event has fired

        Parameters
        ----------
        TODO
        """
        pass


class Statement(metaclass=ABCMeta):
    """
    Abstract class representing executable statements, such as definitions of
    frames/rules, and the invocation of events, including actions.
    """
    @abstractmethod
    def execute(self):
        """
        Execute the statement.
        """
        raise NotImplementedError

class GenericObject(Node):
    # namespace: Namespace
    parent: GenericObject

    def __init__(self, name: str, body: list = None, active=True):
        super().__init__()

        self.name = name
        self.body = body or []
        self._active = active

        self.descriptors: dict[int, GenericObject] = {}
        self.referents: dict[int, GenericObject] = {}
        self.namespace = Namespace(name)

        # TODO instance list would probably be more at home in the actual event classes
        # Should be indexed with bools
        self.__production_events = [None, None]
        # Should be indexed with [id: int][state: bool]
        self.__naming_events = defaultdict(lambda: [None, None])

    @property
    def all_descriptors(self) -> set[GenericObject]:
        """
        Returns
        -------
        set
            The object's descriptor tree, not including the object itself
        """
        result = set()
        for d in self.descriptors.values():
            result |= d | d.all_descriptors
        return result

    @property
    def all_referents(self) -> set[GenericObject]:
        """
        Returns
        -------
        set
            The object's referent tree, not including the object itself
        """
        result = set()
        for d in self.referents.values():
            result |= d | d.all_referents
        return result

    @property
    def active(self):
        return self._active and self.parent.active

    @active.setter
    def active(self, val: bool):
        self._active = val

    def add_descriptor(self, descriptor: 'GenericObject'):
        self.descriptors[descriptor.internal_id] = descriptor
        descriptor.referents[self.internal_id] = self

        # for r in self.referents:
        #     r.get_naming_event(descriptor, True).fire(simulate=True)

    def remove_descriptor(self, descriptor: 'GenericObject'):
        del self.descriptors[descriptor.internal_id]
        del descriptor.referents[self.internal_id]

        # TODO: clean up code duplication
        # for r in self.referents.values():
        #     r.get_naming_event(descriptor, False).fire(simulate=True)

    def set_descriptor(self, descriptor: GenericObject, state: bool):
        if state:
            self.add_descriptor(descriptor)
        else:
            self.remove_descriptor(descriptor)

        # TODO this does not work recursively, as simulate prevents calling set_descriptor
        for r in self.referents.values():
            r.get_naming_event(descriptor, True).fire(simulate=True)

    def has_descriptor(self, descriptor: GenericObject) -> bool:
        """
        Check whether this object has another object as descriptor.

        This is implemented by calling the descriptor's `has_referent()` function,
        allowing for polymorphism in the descriptor's type.
        For example, the root descriptor can always return True, and compound
        descriptors (`a & b`, `a | b`) can use their own logic.

        Parameters
        ----------
        descriptor : GenericObject
            The descriptor to check for

        Returns
        -------
        bool
            Whether this object has the descriptor

        """
        return descriptor.has_referent(self)
        # return descriptor.internal_id in self.descriptors

    def has_referent(self, referent: GenericObject) -> bool:
        """
        Determine whether another object has this object as referent.

        This is intended to be a helper function for `has_descriptor()`,
        though in practice `has_descriptor()` is just a wrapper around this function,
        unless different object types choose to override `has_descriptor()`,
        like `RootDescriptor`, which has no descrpitors.

        Parameters
        ----------
        referent : GenericObject
            The referent to check for

        Returns
        -------
        bool
            Whether this object has the referent
        """
        return referent.internal_id in self.referents

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

    def get_naming_event(self, descriptor: GenericObject, new_state: bool) -> NamingEvent:
        """
        Get the NamingEvent responsible for adding or removing a descriptor to/from this object.
        Creates a new object if it doesn't already exist.

        Parameters
        ----------
        descriptor : GenericObject
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

    def accept(self, visitor: GenericVisitor):
        return visitor.visitGenericObject(self)

    def resolve(self, **kwargs) -> GenericObject:
        """
        Resolve an object reference. For regular GenericObjects, this is the object itself.
        Subclasses may use kwargs to return a different object.

        Returns
        -------
        GenericObject
            The object referenced
        """
        return self

    @classmethod
    def from_json(cls, arg):
        name = arg['compound']
        content = [from_json(c) for c in arg['content']]

        return GenericObject(name, content)

    def __repr__(self) -> str:
        return f"{'+' if self.active else '-'}{self.__class__.__name__}:{self.name}[{', '.join(d.name for d in list(self.descriptors.values()))}]"


# TODO maybe introduce separate descriptor ABC?
class RootDescriptor(GenericObject):
    """
    Singleton class representing the root descriptor '*'
    """
    def __init__(self):
        super().__init__('*', [], True)

    def has_referent(self, referent: GenericObject):
        return True

    def has_descriptor(self, descriptor: GenericObject):
        return False


class ObjectReference(Node):
    """
    Node representing an object defined elsewhere

    Parameters
    ----------
    name : str
        The name of the object referenced
    refinement : dict[str, ObjectReference], optional
        Any arguments to a compound object
    parent : ObjectReference, optional
        The object this object is nested in
    namespace : Namespace, optional
        The enclosing namespace

    Notes
    -----
    If both parent and namespace are specified, namespace is ignored
    """
    # TODO namespace can't be passed at creation time
    def __init__(self, name: str, refinement: dict[str, ObjectReference] = None, parent: ObjectReference = None, namespace: Namespace = None):
        super().__init__()

        self.object = None

        self.name = name
        self.refinement = refinement
        self.parent = parent
        self.local_namespace = namespace

    def resolve(self, save=False, context: Namespace = None, **kwargs) -> GenericObject:
        """
        Parameters
        ----------
        save : bool, default=False
            If set to True, the result will be saved and returned by future calls.
        context : Namespace, optional
            A local namespace to use as local, instead of the object's saved local_namespace.

        Raises
        ValueError
            If neither parent nor namespace is set
        """
        if self.object:
            return self.object

        namepsace = (context or self.local_namespace)

        if self.parent is None and namepsace is None:
            raise ValueError("ObjectReference has neither parent reference nor namespace")

        if self.parent:
            result = self.parent.resolve(context=context).namespace.get(self.name, recursive=False)
        else:
            result = namepsace.get(self.name, recursive=True)

        # NOTE should self.object be set to this?
        # result = namespace.get(self.name, recursive=False)

        if self.refinement:
            result = result.get_instance(self.refinement)

        # TODO move check for selector elsewhere
        if save and not isinstance(result, Selector):
            self.object = result

        return result

    def accept(self, visitor: GenericVisitor):
        return visitor.visitObjectReference(self)

    @classmethod
    def from_json(cls, arg):
        # Atomic object
        if isinstance(arg, str):
            return ObjectReference(name=arg)

        if 'scope' in arg:
            parent = from_json(arg['scope'])
            arg = arg['name']
        else:
            parent = None

        if isinstance(arg, str):
            return ObjectReference(arg, parent=parent)

        return ObjectReference(arg['reference'], arg['refinement'], parent=parent)

    def __repr__(self) -> str:
        return f"ObjectReference:{self.name}"


class PowerFrame(GenericObject):
    children = ['action', 'consequence', 'holder']

    def __init__(self, position: str, action: ActionReference, consequence: Event, holder: ObjectReference, alias=None):
        super().__init__(alias)

        self.position = position
        self.action = action
        self.consequence = consequence
        self.holder = Selector(holder)
        # self.alias = alias

        # self.selectors = {name: Selector(val) for name, val in action.args.items()}
        self.selectors = action.args.copy()
        self.selectors['holder'] = self.holder

        self.action.action.add_power(self)

    def notify(self, **kwargs) -> bool:
        """
        Notify this power that its associated action has been called.

        Parameters
        ----------
        **kwargs : dict, optional
            Any arguments passed to the action, including the calling object under the name 'holder'

        Returns
        -------
        bool
            True if the power is active and the action's arguments match those
            expected by this power, False otherwise.
        """
        if not self.active:
            return False

        # if not any(s.matches(kwargs[name], context=self.namespace) for name, s in self.selectors.items()):
        if not all(kwargs[name].has_descriptor(s) for name, s in self.descriptors.items()):
            return False

        context = Namespace('', self.namespace, initial=kwargs)
        self.consequence.fire(context)

        return True

    def fire(self, args: dict[str, GenericObject]):
        # NOTE deprecated

        # print(f"power {self.name} called, {kwargs = }")
        # print(self.action.args)
        # print(f"calling {self.consequence} with {args = }")

        # if args['holder'].has_descriptor(self.holder):
        if all(s.matches(args[name], context=self.namespace) for name, s in self.selectors.items()):
            # print("triggering consequence")
            context = Namespace('', self.namespace, initial=args)
            self.consequence.fire(context)

    @classmethod
    def from_json(cls, arg: dict) -> PowerFrame:
        holder = arg.get('holder', '*')
        position = arg['position']
        action = arg['action']
        consequence = arg['consequence']
        alias = arg.get('alias')

        if 'plus' in consequence or 'minus' in consequence:
            consequence = ProductionEventPlaceholder.from_json(consequence)
        elif 'in' in consequence or 'out' in consequence:
            consequence = NamingEventPlaceholder.from_json(consequence)

        return cls(position, ActionReference.from_json(action), consequence, ObjectReference(holder), alias)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitPowerFrame(self)


# class Selector(metaclass=ABCMeta):
#     """
#     Generic selector, used for pattern matching.

#     Meant to be subclassed by e.g. object (for matching against descriptors)
#     or events (for matching against event calls).
#     """
#     @abstractmethod
#     def matches(self, other) -> bool:
#         """
#         Checks whether other matches this selector
#         """
#         raise NotImplementedError


class Selector(Node):
    # TODO this class seems superfluous: it's just a wrapper around resolve() and has_descriptor
    def __init__(self, object: ObjectReference):
        super().__init__()

        self.object = object

    def matches(self, other: ObjectReference, context: Namespace = None):
        return other.resolve(context=context).has_descriptor(self.object.resolve(context=context))


class DeonticFrame(GenericObject, EventListener):
    children = ['action', 'holder', 'counterparty', 'violation', 'fulfillment', 'termination']

    def __init__(self, position: str, action: Action, holder, counterparty, violation: Event, fulfillment: Event, termination, alias):
        super().__init__(alias)

        self.position = position
        self.action = action
        self.holder = holder
        self.counterparty = counterparty
        self.violation = violation
        self.fulfillment = fulfillment
        self.termination = termination

        self.action.add_callback(self)
        self.violation.add_callback(self)
        self.fulfillment.add_callback(self)

    def notify(self, **kwargs):
        print(f"deontic frame {self} notified of event {kwargs}")

    @classmethod
    def from_json(cls, arg):
        position = arg['position']
        action = from_json(arg['position'])

        holder = from_json(arg.get('holder', '*'))
        counterparty = from_json(arg.get('counterparty', '*'))

        violation = arg.get('violation')
        if violation is not None:
            if 'event' in violation:
                violation = violation['event']
            violation = from_json(violation)

        fulfillment = arg.get('fulfillment')
        if fulfillment is not None:
            fulfillment = from_json(fulfillment['event'])

        termination = arg.get('termination')
        if termination is not None:
            termination = from_json(termination)

        alias = arg.get('alias')

        return DeonticFrame(position, action, holder, counterparty, violation, fulfillment, termination, alias)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitDeonticFrame(self)


class Parameter(Node):
    """
    Dummy value for namespaces, representing the promise an argument
    of this name will be provided later
    """
    def __init__(self, name: str):
        super().__init__()

        self.name = name
        self.references: set[ObjectReference] = set()

    def add_reference(self, ref: ObjectReference):
        self.references.add(ref)

    # TODO better name
    def realise(self, value: GenericObject):
        """
        Assign a value to this parameter, and set all references.
        """
        for ref in self.references:
            ref.object = value

class CompoundFrame(GenericObject):
    """
    Node representing a parametrized or 'template' compound frame.

    Cannot be active
    """
    def __init__(self, name: str, params: list[str], body: list):
        super().__init__(name, body, active=False)

        self.params = params
        for name in params:
            self.namespace.add(name, Parameter(name))
        # self.body = body

        self.instances = {}

    def instantiate(self, args: dict[str, GenericObject]) -> GenericObject:
        """
        Create a new instance of this compound
        """
        full_name = f'{self.name}{self.args_to_key(args)})'

        copy = visitor.ASTCopier().visit(self)
        result = GenericObject(full_name, copy.body)
        # result.namespace = Namespace(full_name, self.namespace)
        result.namespace.parent = self.namespace

        return result

    def visit_children(self, visitor: GenericVisitor):
        # TODO This should be an exact copy of genericobject, in which case this can go
        for i, v in enumerate(self.body):
            self.body[i] = visitor.visit(v)

    def args_to_key(self, args: dict[str, GenericObject]) -> tuple:
        """

        """
        return tuple(args[name].internal_id for name in self.params)

    def get_instance(self, args: dict[str, GenericObject]) -> GenericObject:
        """
        Get a specific instance of this compound. A new one is created

        Parameters
        ----------
        args : dict[str, GenericObject]

        """
        key = self.args_to_key(args)
        if key in self.instances:
            return self.instances[key]

        result = self.instances[key] = self.instantiate(args)
        return result

    @property
    def active(self):
        return False

    @active.setter
    def active(self):
        raise AttributeError(f"can't activate compound frame {self.name}")

    @classmethod
    def from_json(cls, arg):
        name = arg['compound']
        content = [from_json(c) for c in arg['content']]
        params = arg['params']

        return CompoundFrame(name, params, content)

    # @property
    # def children(self):
    #     return self.content


class TransformationalRule(Node):
    children = ['antecedent', 'consequent']

    def __init__(self, antecedent: GenericObject, consequent: GenericObject, alias: str = None):
        super().__init__()

        # self.antecedent = antecedent if isinstance(antecedent, NamingEvent) else antecedent.
        match antecedent:
            case GenericObject():
                antecedent.get_production_event
            case NamingEvent():
                antecedent.add_callback(self)
        self.consequent = consequent

        self.alias = alias

    @classmethod
    def from_json(cls, arg):
        condition = from_json(arg['condition'])
        conclusion = from_json(arg['conclusion'])

        alias = arg.get('alias')

        return ReactiveRule(condition, conclusion, alias)

    # @property
    # def children(self):
    #     return [self.antecedent, self.consequent]


class ReactiveRule(Node, EventListener):
    children = ['event', 'reaction']

    def __init__(self, event: Event, reaction: Event, alias: str = None):
        super().__init__()

        self.event = event
        self.reaction = reaction

        self.alias = alias

        # TODO move this to after resolving references
        self.event.add_callback(self)

    def notify(self, **kwargs):
        self.reaction.fire(**kwargs)

    @classmethod
    def from_json(cls, arg):
        reaction = from_json(arg['reaction'])

        event = arg.get('event')
        if event is not None:
            event = from_json(event)

        alias = arg.get('alias')

        return ReactiveRule(event, reaction, alias)


root_descriptor = RootDescriptor()
