from __future__ import annotations
from collections import defaultdict
import ASTtools.visitor as visitor
from ASTtools.visitor import GenericVisitor

from ASTtools.namespace import Namespace

from itertools import count
from builtins import NotImplementedError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # import visitor
    from visitor import GenericVisitor


POWER_POSITIONS = {'power', 'liability', 'disability', 'immunity'}


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
    def from_json(cls, arg):
        """
        Construct a node from a JSON object or list, as appropriate for the node type
        """
        if isinstance(arg, list):
            return Program.from_json(arg)

        constructor = None

        if isinstance(arg, str):
            if arg.startswith('#'):
                constructor = Action
            else:
                constructor = ObjectReference

            return constructor.from_json(arg)

        if 'event' in arg and 'reaction' in arg:
            constructor = ReactiveRule
        elif 'reaction' in arg:
            return cls.from_json(arg['reaction'])
        elif 'condition' in arg and 'conclusion' in arg:
            constructor = TransformationalRule
        elif 'position' in arg:
            if arg['position'] in POWER_POSITIONS:
                constructor = PowerFrame
            else:
                constructor = DeonticFrame
        elif 'plus' in arg or 'minus' in arg:
            constructor = ProductionEventPlaceholder
        elif 'in' in arg or 'out' in arg:
            constructor = NamingEvent
        elif 'reference' in arg and 'refinement' in arg:
            if arg['reference'].startswith('#'):
                constructor = Action
            else:
                constructor = ObjectReference
        elif 'compound' in arg:
            if 'params' in arg:
                constructor = CompoundFrame
            else:
                constructor = GenericObject
        elif 'scope' in arg:
            if 'name' in arg:
                constructor = ObjectReference
            elif 'action' in arg:
                constructor = ActionReference

        if not constructor:
            raise ValueError(f"No applicable constructor found for {arg}")
            # print(f"No applicable constructor found for {arg}")
            # return arg

        try:
            return constructor.from_json(arg)
        except Exception as e:
            # print(e)
            print(arg)

            raise e

class Program(Node):
    # TODO docstring
    # TODO make subclass of GenericObject
    def __init__(self, name: str, body: list):
        super().__init__()

        self.name = name
        self.body = body

        self.namespace = Namespace(self.name)

    def init_root_descrptor(self):
        # TODO make special root class, invert descriptor check
        self.namespace.add('*', GenericObject('*'))

    def visit_children(self, visitor: GenericVisitor):
        for i, v in enumerate(self.body):
            # print(f"visiting program body {i} {v}")
            self.body[i] = visitor.visit(v)

    # @property
    # def children(self):
    #     return self.body

    @classmethod
    def from_json(cls, content: list, filename: str):
        content = [Node.from_json(x) for x in content]
        return cls(filename, content)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitProgram(self)


class Event(Node):
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

        object = Node.from_json(object)

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

        entity = Node.from_json(entity)
        descriptor = Node.from_json(descriptor)

        return cls(entity, descriptor, new_state)

    @staticmethod
    def get_event(object: GenericObject, descriptor: GenericObject, new_state: bool) -> NamingEvent:
        return object.get_naming_event(descriptor, new_state)


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


class ActionReference(Event):
    def __init__(self, name: str, parent: ObjectReference, args: dict[str, ObjectReference] = None):
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
    def from_json(cls, arg):
        if 'scope' in arg:
            parent = Node.from_json(arg['scope'])
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
        entity = Node.from_json(arg['entity'])

        if 'in' in arg:
            descriptor = arg['in']
            new_state = True
        else:
            descriptor = arg['out']
            new_state = False

        descriptor = Node.from_json(descriptor)

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

        object = ObjectReference.from_json(object)

        return cls(object, new_state)


class EventListener(Node):
    def __init__(self):
        super().__init__()

    def notify(self, **kwargs):
        pass


class GenericObject(Node):
    namespace: Namespace

    def __init__(self, name: str, body: list = None, active=True):
        super().__init__()

        self.name = name
        self.body = body or []
        self.active = active

        self.descriptors: dict[str, GenericObject] = {}
        self.referents: dict[str, GenericObject] = {}
        # self.namespace = Namespace(name)

        # Should be indexed with bools
        self.__production_events = [None, None]
        # Should be indexed with [id: str][state: bool]
        self.__naming_events = defaultdict(lambda: [None, None])

    def add_descriptor(self, descriptor: 'GenericObject'):
        self.descriptors[descriptor.internal_id] = descriptor
        descriptor.referents[self.internal_id] = self

        for r in self.referents:
            r.get_naming_event(descriptor, True).fire()

    def remove_descriptor(self, descriptor: 'GenericObject'):
        del self.descriptors[descriptor.internal_id]
        del descriptor.referents[self.internal_id]

        # TODO: clean up code duplication
        for r in self.referents:
            r.get_naming_event(descriptor, False).fire()

    def set_descriptor(self, descriptor: GenericObject, state: bool):
        if state:
            self.add_descriptor(descriptor)
        else:
            self.remove_descriptor(descriptor)

    def has_descriptor(self, descriptor: GenericObject):
        # TODO refactor explicit check for * object
        return descriptor.internal_id in self.descriptors or descriptor.name == '*'

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
        content = [Node.from_json(c) for c in arg['content']]

        return GenericObject(name, content)

    def __repr__(self) -> str:
        return f"{'+' if self.active else '-'}{self.__class__.__name__}:{self.name}[{', '.join(d.name for d in list(self.descriptors.values()))}]"


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
            return ObjectReference(arg)

        if 'scope' in arg:
            parent = Node.from_json(arg['scope'])
            arg = arg['name']
        else:
            parent = None

        if isinstance(arg, str):
            return ObjectReference(arg, parent=parent)

        return ObjectReference(arg, arg['refinement'], parent=parent)

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

        self.selectors = {name: Selector(val) for name, val in action.args.items()}
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

        if not any(s.matches(kwargs[name], context=self.namespace) for name, s in self.selectors.items()):
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


class Selector(Node):
    def __init__(self, object: ObjectReference):
        super().__init__()

        self.object = object

    def matches(self, other: ObjectReference, context: Namespace = None):
        return other.resolve(context=context).has_descriptor(self.object.resolve(context=context))


class DeonticFrame(GenericObject):
    children = ['action', 'holder', 'counterparty', 'violation', 'fulfillment', 'termination']

    def __init__(self, position: str, action: Action, holder, counterparty, violation, fulfillment, termination, alias):
        super().__init__(alias)

        self.position = position
        self.action = action
        self.holder = holder
        self.counterparty = counterparty
        self.violation = violation
        self.fulfillment = fulfillment
        self.termination = termination

    @classmethod
    def from_json(cls, arg):
        position = arg['position']
        action = Node.from_json(arg['position'])

        holder = Node.from_json(arg.get('holder', '*'))
        counterparty = Node.from_json(arg.get('counterparty', '*'))

        violation = arg.get('violation')
        if violation is not None:
            if 'event' in violation:
                violation = violation['event']
            violation = Node.from_json(violation)

        fulfillment = arg.get('fulfillment')
        if fulfillment is not None:
            fulfillment = Node.from_json(fulfillment['event'])

        termination = arg.get('termination')
        if termination is not None:
            termination = Node.from_json(termination)

        alias = arg.get('alias')

        return DeonticFrame(position, action, holder, counterparty, violation, fulfillment, termination, alias)

    def accept(self, visitor: GenericVisitor):
        return visitor.visitDeonticFrame(self)

class CompoundFrame(GenericObject):
    def __init__(self, name: str, params: list[str], body: list):
        super().__init__(name, body, active=False)

        self.params = params
        # self.body = body

        self.instances = {}

    def instantiate(self, args: dict[str, GenericObject]) -> GenericObject:
        """
        Create a new instance of this compound
        """
        full_name = f'{self.name}{self.args_to_key(args)})'

        result = visitor.ASTcopier().visit(self)
        result = GenericObject(full_name, self.body)
        result.namespace = Namespace(full_name, self.namespace)

        return result

    def visit_children(self, visitor: GenericVisitor):
        for i, v in enumerate(self.body):
            self.body[i] = visitor.visit(v)

    def args_to_key(self, args: dict[str, GenericObject]) -> tuple:
        return tuple(args[name].internl_id for name in self.params)

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

    @classmethod
    def from_json(cls, arg):
        name = arg['compound']
        content = [Node.from_json(c) for c in arg['content']]
        params = arg['params']

        return CompoundFrame(name, params, content)

    # @property
    # def children(self):
    #     return self.content


class TransformationalRule(Node):
    children = ['antecedent', 'consequent']

    def __init__(self, antecedent: GenericObject, consequent: GenericObject, alias: str = None):
        super().__init__()

        self.antecedent = antecedent
        self.consequent = consequent

        self.alias = alias

    @classmethod
    def from_json(cls, arg):
        condition = Node.from_json(arg['condition'])
        conclusion = Node.from_json(arg['conclusion'])

        alias = arg.get('alias')

        return ReactiveRule(condition, conclusion, alias)

    # @property
    # def children(self):
    #     return [self.antecedent, self.consequent]


class ReactiveRule(Node):
    children = ['event', 'reaction']

    def __init__(self, event: Event, reaction: Event, alias: str = None):
        super().__init__()

        self.event = event
        self.reaction = reaction

        self.alias = alias

        # TODO move this to after resolving references
        self.event.add_callback(self.reaction)

    @classmethod
    def from_json(cls, arg):
        reaction = Node.from_json(arg['reaction'])

        event = arg.get('event')
        if event is not None:
            event = Node.from_json(event)

        alias = arg.get('alias')

        return ReactiveRule(event, reaction, alias)
