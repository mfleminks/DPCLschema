from __future__ import annotations
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from itertools import count
from builtins import NotImplementedError
from typing import TYPE_CHECKING, Any

import ASTtools.visitor as visitor
from ASTtools.visitor import GenericVisitor
from ASTtools.namespace import Namespace
from ASTtools import DPCLparser, exceptions, events


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

    if isinstance(data, bool):
        return BooleanLiteral(data)

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
        constructor = ProductionEventReference
    elif 'gains' in data:
        constructor = NamingEventReference
    elif 'refinement' in data:
        # if data['reference'].startswith('#'):
        if 'event' in data:
            constructor = ActionReference
        else:
            constructor = ObjectReference
    elif 'has' in data:
        constructor = DescriptorCondition
    elif 'object' in data:
        if 'params' in data:
            constructor = CompoundFrame
        else:
            constructor = GenericObject
    elif 'scope' in data:
        constructor = ObjectReference
        # if 'name' in data:
        #     constructor = ObjectReference
        # elif 'action' in data:
        #     constructor = ActionReference
    elif 'agent' in data:
        constructor = ActionReference
    elif 'atomics' in data:
        constructor = AtomicDeclarations

    if not constructor:
        raise ValueError(f"No applicable constructor found for {data}")
        # print(f"No applicable constructor found for {data}")
        # return data

    try:
        return constructor.from_json(data, *args, **kwargs)
    except Exception:
        print(data)
        raise


class BaseDescriptor(metaclass=ABCMeta):
    @abstractmethod
    def has_referent(self, object) -> bool:
        raise NotImplementedError

    def matches(self, other) -> bool:
        return self.has_referent(other)

    # @abstractmethod
    # def all_referents(self, object) -> list[GenericObject]:
    #     raise NotImplementedError


class Node:
    """
    Generic AST node

    A node's hash depends on its `internal_id`, ensuring that a node whose
    memory location is reused doesn't get confused for another
    (in practice this would be a non-issue)

    Attributes
    ----------
    children : list[str]
        The node's children, as list of strings equal to the attributes' names
    """
    children: list[str] = []

    owner: Program | GenericObject
    parent_node: Node
    prefix = 'undefined_node'

    def __init__(self, *args, **kwargs):
        self.aliases = []

    def visit_children(self, visitor: GenericVisitor) -> None:
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
        return getattr(visitor, f'visit{type(self).__name__}')(self)
        # self.visit_children(visitor)

        # return self

    @classmethod
    def from_json(cls, data, *args, **kwargs) -> Node:
        raise NotImplementedError

    # def __hash__(self) -> int:
    #     return hash(self.internal_id)


class Resolvable:
    """
    Base class for any node implementing a resolve function.
    This allows e.g. object definitions to be used wherever a reference might
    be encountered instead
    """
    def __init__(self, *args, **kwargs) -> None:
        # Support use as mixin
        super(Resolvable, self).__init__(*args, **kwargs)

    def resolve(self, *args, **kwargs):
        """
        Resolve a reference. The default implementation returns the object itself.
        """
        return self


# ABCs
class BaseBoolean(Resolvable, metaclass=ABCMeta):
    """
    Base class for a boolean expression, for use as condition/conclustion by trasformational rules.

    Current uses include:
        object (active/inactive)
        descriptor (in/out)

    Attributes
    active : bool
        The current value of the boolean expression.
    """
    def __init__(self, active: bool, *args, **kwargs) -> None:
        # For use as mixin
        super().__init__(active=active, *args, **kwargs)
        self._imperative_active = active
        self._transformational_ctr = 0
        self._observers = set()

        # Track last known state, to be able to detect changes
        self.prev_active = active

    # TODO better name for 3rd arg
    def set_active(self, active: bool, transformational: bool, positive_change: bool = False) -> None:
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
        possitive_change : bool, default False
            Whether this change is because of a condition becoming True,
            and thus is able to cause logical conflicts. This is ignored for
            reactive rules.

        Raises
        ------
        ValueError
            When a transformational rule sets this object to active while
            the counter is negative, or vice versa, indicating a logical contradiction.
        """
        # old_state = self.active

        if not transformational:
            self._imperative_active = active
            self.check_active_change()
            return

        ctr_change = 1 if active else -1
        # Check if signs are different, which implies t. rules are
        # assigning contradictory states
        if positive_change and ctr_change * self._transformational_ctr < 0:
            raise exceptions.LogicError("Contradictory transformational rules")

        self._transformational_ctr += ctr_change

        # if self.active != old_state:
        #     self.on_active_change(transformational)
        self.check_active_change()

    @property
    # @abstractmethod
    def active(self) -> bool:
        """
        The current value of the boolean expression.
        """
        # Transformational takes precedence over reactive
        if self._transformational_ctr == 0:
            result = self._imperative_active
        else:
            result = self._transformational_ctr > 0

        self.prev_active = result
        return result

    def add_boolean_observer(self, observer: TransformationalRule):
        self._observers.add(observer)

    def remove_boolean_observer(self, observer: TransformationalRule):
        self._observers.remove(observer)

    def on_active_change(self, transformational: bool):
        self.notify_boolean_observers()

        # Don't fire event if this change was caused by event
        if transformational:
            self.get_bool_event(self.active).fire()

    def check_active_change(self):
        if self.prev_active != self.active:
            self.on_active_change(False)

    def notify_boolean_observers(self):
        for observer in self._observers:
            observer.notify()

    @abstractmethod
    def get_bool_event(self, state) -> events.BaseEventHandler:
        """

        """
        raise NotImplementedError


class EventListener(metaclass=ABCMeta):
    """
    TODO docstring
    """
    def __init__(self, *args, **kwargs) -> None:
        # Support use as mixin
        super(EventListener, self).__init__(*args, **kwargs)

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
    def __init__(self, *args, **kwargs) -> None:
        # Support use as mixin
        super(Statement, self).__init__(*args, **kwargs)

    @abstractmethod
    def execute(self) -> None:
        """
        Execute the statement.
        """
        raise NotImplementedError


class Program(Node, Statement):
    # TODO docstring
    # TODO maybe make subclass of GenericObject

    # To support global objects checking their active state
    active = True

    def __init__(self, name: str, body: list[Statement]):
        super().__init__()

        self.name = name
        self.body = body

        self.namespace = Namespace(self.name)
        self.init_wildcard_descriptor()

        visitor.ASTLinker().run(self)

    def init_wildcard_descriptor(self):
        self.namespace.add('*', wildcard_descriptor, auto_id=False)
        wildcard_descriptor.parent_node = self
        wildcard_descriptor.owner = self

    def visit_children(self, visitor: GenericVisitor):
        for i, v in enumerate(self.body):
            # print(f"visiting program body {i} {v}")
            self.body[i] = visitor.visit(v)

    def execute(self):
        for statement in self.body:
            statement.execute()

    def get_variable(self, name: str) -> GenericObject:
        """
        Retrieve a variable from this object's namespace. If the specified name
        does not exist in this object's namepsace, higher namespaces are
        searched.

        This function should not be used for implementing the dot operator.
        For that purpose, use `get_attribute` instead.

        Parameters
        ----------
        name : str
            The name of the variable to retrieve

        Raises
        ------
        DPCLNameError
            When the requested name can't be found
        """
        return self.namespace.get(name, recursive=True)

    @classmethod
    def from_json(cls, content: list, filename: str):
        content = [from_json(x) for x in content]
        return Program(filename, content)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitProgram(self)

    @property
    def full_name(self):
        return f"<{self.name}>"


class EventReference(Node, Statement, Resolvable):
    @abstractmethod
    def fire(self, *args, **kwargs):
        pass

    @abstractmethod
    def resolve(self, *args, **kwargs) -> events.BaseEventHandler:
        raise NotImplementedError

    def add_observer(self, observer: EventListener):
        self.resolve().add_callback(observer)

    def execute(self):
        self.fire()


class ActionReference(EventReference):
    """
    Parameters
    ----------
    name : str
        The name of the event referenced. Must begin with '#'
    agent : ObjectReference, optional
        A reference to the agent invoking this action.
        If ommited, this object represents a global generic event.
    args : dict, optional
        Any arguments passed to the event
    """
    def __init__(self, name: str, agent: ObjectReference = None, args: dict[str, ObjectReference] = None):
        super().__init__()

        # self.action = events.ActionHandler.get_event(name)
        self.name = name
        self.agent = agent
        self.args = args or {}

    def fire(self, context: Namespace = None):
        args = {name: ref.resolve() for name, ref in self.args.items()}

        if self.agent is not None:
            args = {**args, 'holder': self.agent.resolve(context=context)}

        self.resolve().fire(**args)

    def resolve(self, context: Namespace = None, *args, **kwargs) -> events.ActionHandler:
        # Get via local alias, if any
        namespace = (context or self.owner.namespace)

        try:
            return namespace.get(self.name)
        except exceptions.DPCLNameError:
            return events.ActionHandler.get_event(self.name)

    def visit_children(self, visitor: GenericVisitor):
        self.agent = visitor.visit(self.agent)

        for name, ref in self.args.items():
            self.args[name] = ref.accept(visitor)

    @classmethod
    def from_json(cls, json: dict | str):
        if 'agent' in json:
            agent = from_json(json['agent'])
            json = json['action']
        else:
            agent = None
        # action = json['action']

        if isinstance(json, str):
            name = json
            refinement = {}
        else:
            name = json['event']
            refinement = json['refinement']

        refinement = {name: from_json(value) for name, value in refinement.items()}

        return ActionReference(name, agent, refinement)

    def __repr__(self) -> str:
        result = "ActionRef:"
        if self.agent:
            result += f"{self.agent}."
        result += self.name
        if self.args:
            result += f" {self.args}"

        return result
        # return f"action: ({self.agent}).{self.name}"


class NamingEventReference(EventReference):
    children = ['object', 'descriptor']

    def __init__(self, object: ObjectReference, descriptor: ObjectReference, new_state: bool):
        super().__init__()

        self.object = object
        self.descriptor = descriptor
        self.new_state = new_state

    def fire(self, context: Namespace = None):
        object = self.object.resolve(context=context)
        descriptor = self.descriptor.resolve(context=context)

        object.set_descriptor(descriptor, self.new_state)

    def resolve(self, *args, **kwargs) -> events.NamingEventHandler:
        return events.NamingEventHandler.get_event(self.object.resolve(), self.descriptor.resolve(), self.new_state)

    @classmethod
    def from_json(cls, json):
        entity = from_json(json['entity'])
        descriptor = from_json(json['descriptor'])
        new_state = json['gains']

        # if 'in' in json:
        #     descriptor = json['in']
        #     new_state = True
        # else:
        #     descriptor = json['out']
        #     new_state = False


        return cls(entity, descriptor, new_state)

    def __repr__(self) -> str:
        operator = "gains" if self.new_state else "loses"
        return f"NERef:( {self.object} {operator} {self.descriptor} )"


class ProductionEventReference(EventReference):
    children = ['object']

    def __init__(self, object: GenericObject, new_state: bool):
        super().__init__()

        self.object = object
        self.new_state = new_state

    def fire(self, **kwargs):
        object = self.object.resolve(**kwargs)

        object.set_active(self.new_state, transformational=False)
        # object.get_production_event(self.new_state).fire()

    def resolve(self, *args, **kwargs) -> events.ProductionEventHandler:
        return events.ProductionEventHandler.get_event(self.object.resolve(), self.new_state)

    @classmethod
    def from_json(cls, json):
        if 'plus' in json:
            object = json['plus']
            new_state = True
        else:
            object = json['minus']
            new_state = False

        object = from_json(object)

        return cls(object, new_state)


class GenericObject(BaseDescriptor, Statement, BaseBoolean, Resolvable, Node):
    """
    TODO docstring
    """
    prefix = "Object"
    # namespace: Namespace

    def __init__(self, name: str, body: list[Statement] = None, active=True, descriptors: list[ObjectReference] = []):
        super().__init__(active=active)
        # BaseDescriptor.__init__(self)
        # Statement.__init__(self)
        # BaseBoolean.__init__(self, active)
        # Node.__init__(self)

        self.name = name
        self.body = body or []

        self.namespace = Namespace(name)

        self.initial_descriptors = descriptors

        self.descriptor_relation_cache = defaultdict(bool)
        self.imperative_descriptor = defaultdict(type(None))
        self.declarative_descriptor_ctr = defaultdict(int)
        # self.descriptors: dict[int, GenericObject] = {}
        # self.referents: dict[int, GenericObject] = {}
        self.descriptors: set[GenericObject] = set()
        self.referents: set[GenericObject] = set()

        # TODO instance list would probably be more at home in the actual event classes
        # Should be indexed with bools
        # self.__production_events = [None, None]

    # Functions for interacting with the namespace

    def get_variable(self, name: str) -> GenericObject:
        """
        Retrieve a variable from this object's namespace. If the specified name
        does not exist in this object's namepsace, higher namespaces are
        searched.

        This function should not be used for implementing the dot operator.
        For that purpose, use `get_attribute` instead.

        Parameters
        ----------
        name : str
            The name of the variable to retrieve

        Raises
        ------
        DPCLNameError
            When the requested name can't be found
        """
        return self.namespace.get(name, recursive=True)

    def get_attribute(self, name: str) -> GenericObject:
        """
        Retrieve an attribute from this object's namespace, as per the dot operator.
        If the specified name does not exist in this object's namespace, the
        namespaces of the object's descriptors are searched.

        Parameters
        ----------
        name : str
            The name of the variable to retrieve

        Raises
        ------
        DPCLNameError
            When the requested name can't be found
        """
        # Search own namespace
        try:
            return self.namespace.get(name, recursive=False)
        except exceptions.DPCLNameError:
            pass

        # Search descriptor's namespaces
        desc_attrs = []
        for d in self.descriptors:
            try:
                # return d.get_attribute(name)
                desc_attrs.append(d.get_attribute(name))
            except exceptions.DPCLNameError:
                pass

        if not desc_attrs:
            # Name not found in entire descriptor tree
            raise exceptions.DPCLNameError(f"object {self.full_name} does not have an attribute named {name}")

        # Construct new attribute if inheritable
        result = GenericObject(name, descriptors=desc_attrs)
        result.owner = result.parent_node = self
        result.execute()

        return result

    def set_variable(self, name: str, value: GenericObject, replace=False):
        """
        Raises
        ------
        DPCLNameError
            If the name is already in use and replace is set to False
        """
        self.namespace.add(name, value, replace)

    # Functions from BaseBoolean

    def get_bool_event(self, state) -> events.ProductionEventHandler:
        return self.get_production_event(state)

    @property
    def active(self) -> bool:
        return super().active and self.owner.active

    def on_active_change(self, transformational: bool):
        super().on_active_change(transformational)

        for obj in self.body:
            if not isinstance(obj, BaseBoolean): continue
            obj.check_active_change()

    # Funtions Dealing with descriptors

    @property
    def all_descriptors(self) -> set[GenericObject]:
        """
        Returns
        -------
        set
            The object's descriptor tree, not including the object itself
        """
        result = self.descriptors.copy()
        for d in self.descriptors:
            result |= d.all_descriptors
        return result

    @property
    def all_referents(self) -> set[GenericObject]:
        """
        Returns
        -------
        set
            The object's referent tree, not including the object itself
        """
        result = self.referents.copy()
        for d in self.referents:
            result |= d | d.all_referents
        return result

    def add_descriptor(self, descriptor: BaseDescriptor):
        # self.descriptors[descriptor.internal_id] = descriptor
        # descriptor.referents[self.internal_id] = self
        self.descriptors.add(descriptor)
        descriptor.referents.add(self)

        # for r in self.referents:
        #     r.get_naming_event(descriptor, True).fire(simulate=True)

    def remove_descriptor(self, descriptor: BaseDescriptor):
        try:
            # del self.descriptors[descriptor.internal_id]
            # del descriptor.referents[self.internal_id]
            self.descriptors.remove(descriptor)
            descriptor.referents.remove(self)
        except KeyError:
            print(f"Attempting to remove descriptor {descriptor.full_name} from {self.full_name}, but descriptor is already absent; doing nothing")

        # TODO: clean up code duplication
        # for r in self.referents.values():
        #     r.get_naming_event(descriptor, False).fire(simulate=True)

    def _should_have_descriptor(self, descriptor: BaseDescriptor):
        """
        Returns
        -------
        bool or None

        Raises
        ------
        LogicError
        """
        if self.declarative_descriptor_ctr[descriptor] != 0:
            return self.declarative_descriptor_ctr[descriptor] > 0

        if self.imperative_descriptor[descriptor] is not None:
            return self.imperative_descriptor[descriptor]

        parent_descriptors = [p.has_descriptor(descriptor) for p in self.descriptors]
        if True in parent_descriptors and False in parent_descriptors:
            raise exceptions.LogicError("Contradictory descriptor inheritance")
        if True in parent_descriptors:
            return True
        if False in parent_descriptors:
            return False

        return None

    def check_descriptor_change(self, descriptor: BaseDescriptor):
        cached_state = bool(self.descriptor_relation_cache[descriptor])
        current_state = self._should_have_descriptor(descriptor)

        self.descriptor_relation_cache[descriptor] = current_state

        # These don't need to be executed on a change from None to False
        if bool(cached_state) != current_state:
            if current_state:
                self.add_descriptor(descriptor)
            else:
                self.remove_descriptor(descriptor)

            # Check newly inherited descriptors
            for d in descriptor.descriptors:
                self.check_descriptor_change(d)

            self.get_naming_event(descriptor, current_state).fire()

        # Referents do need to check for new conflicts
        if cached_state != current_state:
            for r in self.referents:
                r.check_descriptor_change(descriptor)

    def set_descriptor(self, descriptor: BaseDescriptor, state: bool, transformational=False, positive_change=False):
        # print(f"desciptor set: {self = }, {descriptor = }, {state = }, {transformational = }")

        if not state and descriptor is self:
            raise exceptions.DescriptorError(f"Cannot remove descriptor {self.full_name} from itself")

        if not state and descriptor is wildcard_descriptor:
            raise exceptions.DescriptorError(f"Cannot remove descriptor '*' from {self.full_name}")

        if not transformational:
            self.imperative_descriptor[descriptor] = state
            self.check_descriptor_change(descriptor)
            return

        ctr_change = 1 if state else -1
        if positive_change and ctr_change * self.declarative_descriptor_ctr[descriptor] < 0:
            raise exceptions.LogicError(f"Contradictory transformational rules affecting {descriptor.full_name} in/out {self.full_name}")

        self.declarative_descriptor_ctr[descriptor] += ctr_change

        self.check_descriptor_change(descriptor)

        # if state:
        #     self.add_descriptor(descriptor)
        # else:
        #     self.remove_descriptor(descriptor)

        # TODO this does not work recursively, as simulate prevents calling set_descriptor
        # for r in self.referents.values():
        #     r.get_naming_event(descriptor, True).fire(simulate=True)

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
        if descriptor is self:
            return True
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
        if referent is self:
            return True
        return referent in self.referents

    def add_initial_descriptors(self) -> None:
        """
        Add the specified initial descriptors to this object.
        This consumes the `initial_descriptors` attribute and sets it to and empty list.
        """
        for d in self.initial_descriptors:
            # Add descriptor directly to bypass triggering any events
            self.add_descriptor(d.resolve())
            self.imperative_descriptor[d] = True
            self.descriptor_relation_cache[d] = True

        self.initial_descriptors = []

    # Event getters

    def get_naming_event(self, descriptor: GenericObject, new_state: bool) -> events.NamingEventHandler:
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
        return events.NamingEventHandler.get_event(self, descriptor, new_state)

    def get_production_event(self, new_state: bool) -> events.ProductionEventHandler:
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
        # if self.__production_events[new_state] is None:
        #     self.__production_events[new_state] = events.ProductionEventHandler(self, new_state)

        # return self.__production_events[new_state]
        return events.ProductionEventHandler.get_event(self, new_state)

    # Misc.

    def accept(self, visitor: GenericVisitor):
        return visitor.visitGenericObject(self)

    def get_instance(self, *args, **kwargs):
        raise exceptions.DPCLTypeError(f"Can't instantiate non-parametrized object {self.full_name}")

    def execute(self):
        self.owner.namespace.add(self.name, self)
        self.namespace.add('self', self)
        self.namespace.add('super', self.owner)

        self.add_initial_descriptors()

        for statement in self.body:
            statement.execute()

    def visit_children(self, visitor: GenericVisitor):
        for i, d in enumerate(self.initial_descriptors):
            self.initial_descriptors[i] = visitor.visit(d)

        for i, v in enumerate(self.body):
            self.body[i] = visitor.visit(v)

    @property
    def full_name(self):
        # if self.owner:
        try:
            return f'{self.owner.full_name}.{self.name}'
        except AttributeError:
            return self.name

    @classmethod
    def from_json(cls, json: dict):
        name = json['object']
        content = [from_json(c) for c in json['content']]

        descriptors = [from_json(d) for d in json.get('initial_descriptors', [])]

        return GenericObject(name, content, descriptors=descriptors)

    def __repr__(self) -> str:
        return f"{'+' if self.active else '-'}{self.__class__.__name__}:{self.name}[{', '.join(d.name for d in list(self.descriptors))}]"


class DescriptorCondition(BaseBoolean, Node):
    children = ['object', 'descriptor']

    def __init__(self, object: ObjectReference, descriptor: ObjectReference, _in: bool) -> None:
        # BaseBoolean.__init__(self, None)
        Node.__init__(self)

        self._observers = set()

        self.object = object
        self.descriptor = descriptor
        self._in  = _in

    def set_active(self, active: bool, transformational: bool, positive_change: bool = False) -> None:
        super().set_active(active, transformational, positive_change)
        self.object.resolve().check_descriptor_change(self.descriptor.resolve())
        # pass

    @property
    def _imperative_active(self):
        return self.object.resolve().imperative_descriptor[self.descriptor.resolve()]

    @_imperative_active.setter
    def _imperative_active(self, val: bool):
        self.object.resolve().imperative_descriptor[self.descriptor.resolve()] = val

    @property
    def _transformational_ctr(self):
        return self.object.resolve().declarative_descriptor_ctr[self.descriptor.resolve()]

    @_transformational_ctr.setter
    def _transformational_ctr(self, val: int):
        self.object.resolve().declarative_descriptor_ctr[self.descriptor.resolve()] = val

    @property
    def prev_active(self):
        return self.object.resolve().descriptor_relation_cache[self.descriptor.resolve()]

    @prev_active.setter
    def prev_active(self, val):
        self.object.resolve().descriptor_relation_cache[self.descriptor.resolve()] = val

    @property
    def active(self):
        result = self.object.resolve().has_descriptor(self.descriptor.resolve())
        self.prev_active = result
        return result

    def get_bool_event(self, state) -> events.NamingEventHandler:
        return events.NamingEventHandler.get_event(self.object.resolve(), self.descriptor.resolve(), self._in == state)

    def on_active_change(self, transformational: bool):
        # return super().on_active_change(transformational)
        # self.object.set_descriptor(self.descriptor, self.active)
        pass

    @classmethod
    def from_json(cls, data) -> DescriptorCondition:
        object = from_json(data['entity'])
        descriptor = from_json(data['descriptor'])
        _in = data['has']
        return cls(object, descriptor, _in)


class BooleanNegation(BaseBoolean, Node):
    def __init__(self, condition: BaseBoolean) -> None:
        super().__init__(True)
        self._condition = condition

    def set_active(self, active: bool, transformational: bool, positive_change: bool = False) -> None:
        self._condition.set_active(not active, transformational, positive_change)

    @property
    def active(self) -> bool:
        result = not self._condition.active
        self.prev_active = result
        return result

    def get_bool_event(self, state) -> events.BaseEventHandler:
        return self._condition.get_bool_event(not state)


class AtomicDeclarations(Statement, Node):
    def __init__(self, names):
        super().__init__()
        self.names = names

        self.objects = [GenericObject(name, []) for name in names]

    def execute(self):
        # for name in self.names:
        #     obj = GenericObject(name, [])
        #     self.owner.namespace.add(name, obj)
        for o in self.objects:
            o.execute()

    def visit_children(self, visitor: GenericVisitor):
        for i, v in enumerate(self.objects):
            self.objects[i] = visitor.visit(v)

    @classmethod
    def from_json(cls, json, *args, **kwargs) -> AtomicDeclarations:
        names = json['atomics']
        return AtomicDeclarations(names)


class BooleanLiteral(BaseBoolean, Node):
    active: bool

    def __init__(self, active: bool) -> None:
        self.active = active

    def get_bool_event(self, state) -> events.DummyEventHandler:
        return events.DummyEventHandler()


class Import(Node, Statement):
    obj: GenericObject
    __module_chache = {}

    def __init__(self, filename: str, alias: str):
        Node.__init__(self)
        Statement.__init__(self)
        # self.filename = filename
        self.alias = alias

        body = DPCLparser.load_validate_json(self)
        json = {'compound': f'import({filename})', 'content': body}

        if filename in self.__module_chache:
            self.obj = self.__module_chache[filename]
        else:
            self.obj = self.__module_chache[filename] = from_json(json)
            self.obj.prefix = 'import'


    def execute(self):
        self.owner.namespace.add(self.alias, self.obj)

        for statement in self.obj.body:
            statement.execute()
        # self.obj.execute()


# TODO maybe introduce separate descriptor ABC?
class WildcardDescriptor(GenericObject):
    """
    Singleton class representing the universal descriptor `*`
    """
    __instance = None

    def __new__(cls):
        # Ensure only one instance exists
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        else:
            # TODO remove after testing
            print("Warning: multiple calls made to constructor of WildcardDescriptor")

        return cls.__instance

    def __init__(self):
        super().__init__('*', [], True)

    def has_referent(self, referent: GenericObject):
        return True

    def has_descriptor(self, descriptor: GenericObject):
        return False

    def add_descriptor(self, descriptor: GenericObject):
        raise exceptions.DPCLTypeError("Cannot assign descriptor to '*'")

    def remove_descriptor(self, descriptor: GenericObject):
        raise exceptions.DPCLTypeError("Cannot remove descriptor from '*'")

    def set_active(self, active: bool, transformational: bool, positive_change: bool = False) -> None:
        raise exceptions.DPCLTypeError("Cannot change active state of '*'")

    @property
    def full_name(self):
        return self.name

    def __repr__(self) -> str:
        return "WilcardDescriptor(*)"


class PatternDescriptor(Node):
    def __init__(self, pattern, descriptor: GenericObject):
        self.pattern = pattern
        self.descriptor = descriptor


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
        self.references_param = False

        self.name = name
        self.refinement = refinement or {}
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
            If called when neither parent nor local_namespace is set, and no context is specified
            If a parameter is referenced as attribute (i.e. `object.parameter`)
        """
        if self.object:
            return self.object
        # TODO this does not work with nested compounds
        if self.references_param:
            return context.get(self.name, recursive=False)

        namespace = (context or self.owner.namespace)

        if self.parent is None and namespace is None:
            raise ValueError("ObjectReference has neither parent reference nor namespace")

        if self.parent:
            result = self.parent.resolve(context=context).namespace.get(self.name, recursive=False)

            if isinstance(result, Parameter):
                raise ValueError("Cannot reference parameter as attribute")
        else:
            result = namespace.get(self.name, recursive=True)

            if isinstance(result, Parameter):
                self.references_param = True
                return NotImplemented

        # NOTE should self.object be set to this?
        # result = namespace.get(self.name, recursive=False)

        if self.refinement:
            result = result.get_instance({k: v.resolve(context=namespace) for k, v in self.refinement.items()})

        # TODO move check for selector elsewhere
        if save and not isinstance(result, Selector):
            self.object = result

        return result

    def accept(self, visitor: GenericVisitor):
        return visitor.visitObjectReference(self)

    def visit_children(self, visitor: GenericVisitor):
        self.parent = visitor.visit(self.parent)

        for k, v in self.refinement.items():
            self.refinement[k] = visitor.visit(v)

        return self

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

        refinement = {k: from_json(v) for k, v in arg['refinement'].items()}

        return ObjectReference(arg['object'], refinement, parent=parent)

    def __repr__(self) -> str:
        result = "ObjRef:"
        if self.parent:
            result += f"{self.parent}."
        result += self.name
        if self.refinement:
            result += f"{self.refinement}"

        return result
        # return f"ObjRef:{self.parent}{self.name}"


class PowerFrame(GenericObject):
    children = ['action', 'consequence', 'holder']
    visit_children = Node.visit_children
    prefix = "Power"

    def __init__(self, position: str, action: ActionReference, consequence: EventReference, holder: ObjectReference, alias=None):
        super().__init__(alias)

        self.position = position
        self.action = action
        self.consequence = consequence
        self.holder = holder
        # self.holder = Selector(holder)
        # self.alias = alias

        self.selectors = action.args.copy()
        self.selectors['holder'] = self.holder
        # self.selectors = {k: Selector(v) for k, v in self.selectors.items()}

        # self.action.action.add_power(self)

    def notify(self, action_args: dict) -> bool:
        """
        Notify this power that its associated action has been called.

        Parameters
        ----------
        action_args : dict
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
        # if not all(action_args[name].has_descriptor(s) for name, s in self.selectors.items()):

        context = Namespace('<power_args>', self.namespace, action_args)

        # If an expected argument is not provided, the wildcard descriptor is substituted.
        # This works, because wildcard_descriptor.has_descriptor always returns false,
        # signaling any missing args without causing KeyErrors.
        # if not all(action_args.get(name, wildcard_descriptor).has_descriptor(s.resolve(context=context)) for name, s in self.selectors.items()):
            # return False
        for name, s in self.selectors.items():
            arg = action_args.get(name)
            s = s.resolve(context=context)
            if arg is None:
                return False
            # if isinstance(arg, GenericObject) and arg.has_descriptor(s):
            #     continue
            # # arg is an ActionHandler
            # s: events.ActionHandler
            if s.matches(arg):
                continue

            return False

        context = Namespace('', self.namespace, initial=action_args)
        self.consequence.fire(context=context)

        return True

    def fire(self, args: dict[str, GenericObject]):
        # NOTE deprecated

        # print(f"power {self.name} called, {kwargs = }")
        # print(self.action.args)
        # print(f"calling {self.consequence} with {args = }")

        # if args['holder'].has_descriptor(self.holder):
        raise NotImplementedError("Power.fire is deprecated")
        if all(s.matches(args[name], context=self.namespace) for name, s in self.selectors.items()):
            # print("triggering consequence")
            context = Namespace('', self.namespace, initial=args)
            self.consequence.fire(context)

    def execute(self):
        self.action.resolve().add_power(self)
        return super().execute()

    @classmethod
    def from_json(cls, arg: dict) -> PowerFrame:
        position = arg['position']
        alias = arg.get('alias')

        holder = from_json(arg.get('holder', '*'))
        action = from_json(arg['action'])
        consequence = from_json(arg['consequence'])

        # if 'plus' in consequence or 'minus' in consequence:
        #     consequence = ProductionEventReference.from_json(consequence)
        # elif 'in' in consequence or 'out' in consequence:
        #     consequence = NamingEventReference.from_json(consequence)

        return cls(position, action, consequence, holder, alias)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitPowerFrame(self)


class DeonticFrame(GenericObject, EventListener, Statement):
    children = ['action', 'holder', 'counterparty',
                '_violation', '_fulfillment', '_termination',
                # 'violation_object', 'fulfillment_object'
                ]
    visit_children = Node.visit_children

    def __init__(self, position: str, action: ActionReference,
                 holder: ObjectReference, counterparty: ObjectReference,
                 violation: events.BaseEventHandler | BaseBoolean = None,
                 fulfillment: events.BaseEventHandler | BaseBoolean = None,
                 termination: events.BaseEventHandler | BaseBoolean = None,
                 alias: str = None):
        # self.violation_object = GenericObject('violated', active=False)
        # self.fulfillment_object = GenericObject('fulfilled', active=False)

        body = [
            GenericObject('violated', active=False),
            GenericObject('fulfilled', active=False)
        ]
        super().__init__(alias, body=body)
        # super().__init__(alias, body=[self.violation_object, self.fulfillment_object])
        # GenericObject.__init__(self, alias)
        # EventListener.__init__(self)

        self.position = position
        self.action = action
        self.holder = holder
        self.counterparty = counterparty
        self._violation = violation
        self._fulfillment = fulfillment
        self._termination = termination

        # self.action.add_callback(self)
        # self.violation.add_callback(self)
        # self.fulfillment.add_callback(self)

    @property
    def violation_object(self):
        return self.body[0]

    @property
    def fulfillment_object(self):
        return self.body[1]

    def create_internal_rules(self):
        # Create appropriate rule for violation
        if isinstance(self._violation, BaseBoolean):
            self.body.append(TransformationalRule(self._violation, self.violation_object))
        elif isinstance(self._violation, EventReference):
            self.body.append(ReactiveRule(self._violation, self.violation_object.get_bool_event(True)))
        self.body[-1].owner = self
        self.body[-1].parent_node = self

        # Create appropriate rule for fulfillment
        if isinstance(self._fulfillment, BaseBoolean):
            self.body.append(TransformationalRule(self._fulfillment, self.fulfillment_object))
        elif isinstance(self._fulfillment, EventReference):
            self.body.append(ReactiveRule(self._fulfillment, self.fulfillment_object.get_bool_event(True)))
        self.body[-1].owner = self
        self.body[-1].parent_node = self

         # Create appropriate rule for termination
        if isinstance(self._termination, BaseBoolean):
            self.body.append(TransformationalRule(self._termination, BooleanNegation(self)))
        elif isinstance(self._termination, EventReference):
            self.body.append(ReactiveRule(self._termination, self.get_production_event(False)))
        self.body[-1].owner = self
        self.body[-1].parent_node = self

    def execute(self):
        self.create_internal_rules()

        super().execute()

        self.action.add_observer(self)

        self.namespace.add('holder', self.holder, auto_id=False)
        self.namespace.add('counterparty', self.counterparty, auto_id=False)

    def notify(self, **kwargs):
        print(f"deontic frame {self} notified of event {kwargs}")

        if self.position == 'duty':
            self.fulfillment_object.set_active(True, transformational=False)
        elif self.position == 'prohibition':
            self.violation_object.set_active(True, transformational=False)
            print("set violation to True")
            print(self.violation_object.owner is self)
            print(self.violation_object.owner.active, self.violation_object._imperative_active)

    def visit_children(self, visitor: GenericVisitor):
        Node.visit_children(self, visitor)
        super().visit_children(visitor)

    @property
    def prefix(self):
        return self.position

    @classmethod
    def from_json(cls, JSON: dict):
        position = JSON['position']
        action = from_json(JSON['action'])

        holder = from_json(JSON.get('holder', '*'))
        counterparty = from_json(JSON.get('counterparty', '*'))

        violation = JSON.get('violation')
        if violation is not None:
            if 'event' in violation:
                violation = violation['event']
            violation = from_json(violation)

        fulfillment = JSON.get('fulfillment')
        if fulfillment is not None:
            fulfillment = from_json(fulfillment['event'])

        termination = JSON.get('termination')
        if termination is not None:
            termination = from_json(termination)

        alias = JSON.get('alias')

        return DeonticFrame(position, action, holder, counterparty, violation, fulfillment, termination, alias)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitDeonticFrame(self)

    def __repr__(self) -> str:
        # return super().__repr__() + f"({self.position}{', violated'*self.violation_object.active}{', fulfilled'*self.fulfillment_object.active})"
        result = '+' if self.active else '-'
        result += f"{self.position}:"
        if self.name:
            result += self.name
        # result += f"({', violated'*self.violation_object.active}{', fulfilled'*self.fulfillment_object.active})"
        result += f"(', violated':{self.violation_object.active}', fulfilled':{self.fulfillment_object.active})"
        return result

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
    def __init__(self, name: str, params: list[str], body: list, descriptors=[]):
        super().__init__(name, body, active=False, descriptors=descriptors)

        self.params = params
        for name in params:
            self.namespace.add(name, Parameter(name))
        # self.body = body

        self.instances = {}

    def instantiate(self, args: dict[str, GenericObject]) -> GenericObject:
        """
        Create a new instance of this compound
        """
        full_name = f'{self.name}{self.args_to_key(args)}'
        new_namespace = Namespace(full_name, self.namespace.parent, args)

        result = visitor.CompoundInstantiator().run(self, full_name, new_namespace)

        visitor.ASTLinker(self.parent_node, self.owner).run(result)

        for statement in result.body:
            statement.execute()

        return result

        # copy = visitor.CompoundInstantiator().run(self, full_name, new_namespace)

        # # copy = visitor.ASTCopier().visit(self)
        # result = GenericObject(full_name, copy.body)
        # result.namespace = Namespace(full_name, self.namespace, args)
        # # result.namespace.parent = self.namespace


        # # Bypass triggering any events
        # result.add_descriptor(self)

        # return result

    def args_to_key(self, args: dict[str, GenericObject]) -> tuple:
        """

        """
        return tuple(args[name] for name in self.params)

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

    def execute(self):
        # Do not execute body of inactive compound
        self.owner.namespace.add(self.name, self)

        self.add_initial_descriptors()

    def accept(self, visitor: GenericVisitor):
        return visitor.visitCompoundFrame(self)

    @property
    def active(self):
        return False

    @active.setter
    def active(self):
        raise AttributeError(f"can't activate compound frame {self.name}")

    @classmethod
    def from_json(cls, arg):
        name = arg['object']
        content = [from_json(c) for c in arg['content']]
        params = arg['params']

        descriptors = [from_json(d) for d in arg.get('initial_descriptors', [])]

        return CompoundFrame(name, params, content, descriptors=descriptors)

    def print_instances(self, indent="\t"):
        for k, v in self.instances.items():
            print(f"{indent}{v}")

    # @property
    # def children(self):
    #     return self.content


class TransformationalRule(Node, Statement):
    children = ['antecedent', 'consequent']

    def __init__(self, antecedent: BaseBoolean, consequent: BaseBoolean, alias: str = None):
        super().__init__()

        # self.antecedent = antecedent if isinstance(antecedent, NamingEvent) else antecedent.
        match antecedent:
            case GenericObject():
                antecedent.get_production_event
            case events.NamingEventHandler():
                antecedent.add_callback(self)
        self.consequent = consequent
        self.antecedent = antecedent

        self.alias = alias

    def notify(self):
        self.consequent.resolve().set_active(self.antecedent.resolve().active,
                                   transformational=True,
                                   positive_change=self.antecedent.resolve().active)

    def execute(self):
        if self.antecedent.resolve().active:
            self.notify()

        self.antecedent.resolve().add_boolean_observer(self)

    @classmethod
    def from_json(cls, arg):
        condition = from_json(arg['condition'])
        conclusion = from_json(arg['conclusion'])

        alias = arg.get('alias')

        return ReactiveRule(condition, conclusion, alias)

    # @property
    # def children(self):
    #     return [self.antecedent, self.consequent]


class ReactiveRule(Node, EventListener, Statement):
    children = ['event', 'reaction']

    def __init__(self, event: EventReference, reaction: EventReference, alias: str = None):
        super().__init__()

        self.event = event
        self.reaction = reaction

        self.alias = alias

        # TODO move this to after resolving references
        # self.event.add_callback(self)

    def notify(self, **kwargs):
        self.reaction.fire(**kwargs)

    def execute(self) -> None:
        return self.event.add_observer(self)

    @classmethod
    def from_json(cls, json: dict):
        reaction = from_json(json['reaction'])

        event = json.get('event')
        if event is not None:
            event = from_json(event)

        alias = json.get('alias')

        return ReactiveRule(event, reaction, alias)


wildcard_descriptor = WildcardDescriptor()
