from builtins import NotImplementedError
from collections import defaultdict
from dataclasses import InitVar, dataclass, field
from typing import ClassVar, Optional, List, TypeAlias, Union


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
            constructor = RefinedEvent
        else:
            constructor = RefinedObject
    elif 'compound' in arg:
        constructor = CompoundFrame
    elif 'scope' in arg and 'name' in arg:
        constructor = ScopedObject

    if not constructor:
        print("Unrecognized")
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

    def get(self, name: str, recursive = False) -> Union['DPCLAstNode', None]:
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

    def get_as_list(self):
        return list(self.__symbol_table.values())

    def add(self, name: str, value: 'DPCLAstNode', overwrite = False):
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
            raise ValueError("Name already exists")
        self.__symbol_table[name] = value

    @property
    def full_name(self):
        if self.parent is None or self.parent.full_name == "":
            return self.name
        return f'{self.parent.full_name}::{self.name}'

    def get_auto_id(self, prefix):
        ctr = self.__auto_id_ctr[prefix]
        self.__auto_id_ctr[prefix] += 1
        return f'{self.full_name}::_{prefix}{ctr}'


@dataclass
class DPCLAstNode:
    """
    Base ast node. Should not be instantiated directly.
    """
    alias: str
    prefix: ClassVar[str]

    parent_namespace: Optional[Namespace] = field(init=False, repr=False)

    id: str = field(init=False)

    # def __post_init__(self):
    #     self.id = auto_alias(self.prefix)

    #     if self.alias is None:
    #         self.alias = self.id

    def set_parent_namespace(self, parent_namespace: Namespace):
        self.parent_namespace = parent_namespace
        self.id = parent_namespace.get_auto_id(self.prefix)

        parent_namespace.add(self.id, self)

        if self.alias is None:
            self.alias = self.id
        else:
            parent_namespace.add(self.alias, self)


@dataclass
class Program(DPCLAstNode):
    globals: list[DPCLAstNode]
    namespace: Namespace = field(init=False)
    id: str

    prefix = "P"

    def __post_init__(self):
        self.namespace = Namespace(self.id, None)

        # Use list to ensure ordering stays consistent
        for obj in self.globals:
            obj.set_parent_namespace(self.namespace)

        # for g in globals:
        #     self.namespace.add(g.id, g)
        #     if g.alias != g.id:
        #         self.namespace.add(g.alias, g)

    @classmethod
    def from_json(cls, globals: list, filename: str) -> 'Program':
        return Program(globals=[parse(g) for g in globals], id=filename, alias=None)


@dataclass
class CompoundFrame(DPCLAstNode):
    # compound: str  # NOTE I'm assuming this is the name?
    body: List[DPCLAstNode]
    params: List[str]

    namespace: Namespace = field(init=False)

    prefix = "CF"

    def __post_init__(self, body: list[DPCLAstNode]):
        self.namespace = Namespace(self.alias, None)
    #     for g in body:
    #         self.namespace.add(g.id, g)
    #         if g.alias != g.id:
    #             self.namespace.add(g.alias, g)

    @classmethod
    def from_json(cls, attrs: dict) -> 'CompoundFrame':
        compound = attrs['compound']
        body = [parse(item) for item in attrs['content']]
        params = attrs.get('params', [])

        return CompoundFrame(body=body,
                             params=params,
                             compound=compound,
                             alias=None)

    def set_parent_namespace(self, parent_namespace: Namespace):
        self.namespace.parent = parent_namespace

        for obj in self.body:
            obj.set_parent_namespace(self.namespace)


@dataclass
class TransformationalRule(DPCLAstNode):
    condition: object
    conclusion: object

    prefix = "TR"

    @classmethod
    def from_json(cls, attrs: dict) -> 'TransformationalRule':
        condition = parse(attrs['condition'])
        conclusion = parse(attrs['conclusion'])
        alias = attrs.get('alias', None)

        return TransformationalRule(condition=condition,
                                    conclusion=conclusion,
                                    alias=alias)

    def set_parent_namespace(self, parent_namespace: Namespace):
        super().set_parent_namespace(parent_namespace)

        self.condition.set_parent_namespace(parent_namespace)
        self.conclusion.set_parent_namespace(parent_namespace)


@dataclass
class ReactiveRule(DPCLAstNode):
    event: object
    reaction: object

    prefix = "RR"

    @classmethod
    def from_json(cls, attrs: dict) -> 'ReactiveRule':
        event = parse(attrs['event'])
        reaction = parse(attrs['reaction'])
        alias = attrs.get('alias', None)

        return ReactiveRule(event=event,
                            reaction=reaction,
                            alias=alias)

    def set_parent_namespace(self, parent_namespace: Namespace):
        super().set_parent_namespace(parent_namespace)

        self.event.set_parent_namespace(parent_namespace)
        self.reaction.set_parent_namespace(parent_namespace)


@dataclass
class PowerFrame(DPCLAstNode):
    position: str  # TODO maybe change to enum?
    action: object
    consequence: TransitionEvent
    holder: Optional[object] = None

    prefix = "PF"

    @classmethod
    def from_json(cls, attrs: dict) -> 'PowerFrame':
        position = parse(attrs['position'])
        action = parse(attrs['action'])
        consequence = parse(attrs['consequence'])
        holder = attrs.get('holder', None)
        alias = attrs.get('alias', None)

        return PowerFrame(position=position,
                          action=action,
                          consequence=consequence,
                          holder=holder,
                          alias=alias)

    def set_parent_namespace(self, parent_namespace: Namespace):
        super().set_parent_namespace(parent_namespace)

        # self.action.set_parent_namespace(parent_namespace)
        self.consequence.set_parent_namespace(parent_namespace)
        # self.holder.set_parent_namespace(parent_namespace)


@dataclass
class DeonticFrame(DPCLAstNode):
    position: str  # TODO maybe change to enum?
    action: object
    holder: Optional[object] = None
    counterparty: Optional[object] = None
    violation: Optional[object] = None
    termination: Optional[object] = None

    prefix = "DF"

    @classmethod
    def from_json(cls, attrs: dict) -> 'DeonticFrame':
        position = parse(attrs['position'])
        action = parse(attrs['action'])
        counterparty = attrs.get('counterparty', None)
        violation = attrs.get('violation', None)
        termination = attrs.get('termination', None)
        holder = attrs.get('holder', None)
        alias = attrs.get('alias', None)

        return DeonticFrame(position=position,
                            action=action,
                            holder=holder,
                            counterparty=counterparty,
                            violation=violation,
                            termination=termination,
                            alias=alias)

    def set_parent_namespace(self, parent_namespace: Namespace):
        super().set_parent_namespace(parent_namespace)

        # self.action.set_parent_namespace(parent_namespace)
        # self.holder.set_parent_namespace(parent_namespace)
        # self.counterparty.set_parent_namespace(parent_namespace)
        # self.violation.set_parent_namespace(parent_namespace)
        # self.termination.set_parent_namespace(parent_namespace)


@dataclass
class ProductionEvent(DPCLAstNode):
    entity: object
    new_state: bool

    prefix = "PE"

    @classmethod
    def from_json(cls, attrs: dict) -> 'ProductionEvent':
        entity = parse(attrs.get('plus', attrs) or attrs['minus'])
        new_state = 'plus' in attrs

        return ProductionEvent(entity=entity,
                               new_state=new_state,
                               alias=None)

    def set_parent_namespace(self, parent_namespace: Namespace):
        super().set_parent_namespace(parent_namespace)

        # TODO this shouldn't be neccesary
        try:
            self.entity.set_parent_namespace(parent_namespace)
        except AttributeError:
            pass


@dataclass
class NamingEvent(DPCLAstNode):
    entity: object
    descriptor: object
    new_state: bool

    prefix = "NE"

    @classmethod
    def from_json(cls, attrs: dict) -> 'NamingEvent':
        entity = parse(attrs['entity'])
        new_state = 'in' in attrs
        descriptor = parse(attrs.get('in', None) or attrs['out'])

        return NamingEvent(entity=entity,
                           descriptor=descriptor,
                           new_state=new_state,
                           alias=None)

    def set_parent_namespace(self, parent_namespace: Namespace):
        super().set_parent_namespace(parent_namespace)

        # self.entity.set_parent_namespace(parent_namespace)
        # self.descriptor.set_parent_namespace(parent_namespace)


@dataclass
class RefinedObject(DPCLAstNode):
    reference: str
    refinement: object

    prefix = "RO"

    @classmethod
    def from_json(cls, attrs: dict) -> 'RefinedObject':
        reference = attrs['reference']
        refinement = attrs['refinement']
        alias = attrs.get('alias', None)

        return RefinedObject(reference=reference,
                             refinement=refinement,
                             alias=alias)


@dataclass
class ScopedObject(DPCLAstNode):
    scope: object
    name: str

    prefix = "SO"

    @classmethod
    def from_json(cls, attrs: dict) -> 'ScopedObject':
        scope = parse(attrs['scope'])
        name = attrs['name']

        return ScopedObject(scope=scope,
                            name=name,
                            alias=None)


@dataclass
class RefinedEvent(DPCLAstNode):
    reference: str
    refinement: object

    prefix = "RE"

    @classmethod
    def from_json(cls, attrs: dict) -> 'RefinedEvent':
        reference = attrs['reference']
        refinement = attrs['refinement']
        alias = attrs.get('alias', None)

        return RefinedEvent(reference=reference,
                            refinement=refinement,
                            alias=alias)


class Node:
    def __init__(self):
        self.aliases = []


class Event(Node):
    def __init__(self):
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def fire(self):
        for callback in self.callbacks:
            callback.fire()

        self.__fire()

    def __fire(self):
        pass


class TransitionEvent(Event):
    def __init__(self, object, new_state):
        super().__init__()

        self.object = object
        self.new_state = new_state

    def __fire(self):
        self.object.active = self.new_state


class NamingEvent(Event):
    def __init__(self, object: DPCLObject, descriptor, new_state):
        super().__init__()

        self.object = object
        self.descriptor = descriptor
        self.new_state = new_state

    def __fire(self):
        if self.new_state:
            self.object.add_descriptor(self.descriptor)
        else:
            self.object.remove_descriptor(self.descriptor)


class DPCLObject(Node):
    def __init__(self, active=True):
        super().__init__()

        self.descriptors = {}
        self.namespace = Namespace()
        self.active = active

    @property
    def children(self):
        raise NotImplementedError

    def add_descriptor(self, descriptor: DPCLObject):
        self.descriptors[descriptor.id] = descriptor

    def remove_descriptor(self, descriptor: DPCLObject):
        del self.descriptors[descriptor.id]


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


class DeonticFrame(DPCLObject):
    def __init__(self, position: str, action: Actio):
        super().__init__()
