from dataclasses import dataclass, field
from typing import ClassVar, Optional, List


alias_ctr = 0
def auto_alias(prefix=''):
    global alias_ctr
    """
    Generate an auto-incrementing unique ID.
    """
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
    if 'compound' in arg:
        constructor = CompoundFrame

    if not constructor:
        print("Unrecognized")
        return arg

    return constructor.from_json(arg)


@dataclass
class DPCLAstNode:
    """
    Base ast node. Should not be instantiated directly.
    """
    alias: str
    prefix: ClassVar[str]

    def __post_init__(self):
        if self.alias is None:
            self.alias = auto_alias(self.prefix)


@dataclass
class Program(DPCLAstNode):
    globals: list

    prefix = "P"

    @classmethod
    def from_json(cls, globals: list) -> 'Program':
        return Program(globals=[parse(g) for g in globals], alias=None)


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


@dataclass
class PowerFrame(DPCLAstNode):
    position: str  # TODO maybe change to enum?
    action: object
    consequence: 'TransitionEvent'
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


@dataclass
class CompoundFrame(DPCLAstNode):
    compound: str  # NOTE I'm assuming this is the name?
    body: List[object]
    params: List[str]

    prefix = "CF"

    @classmethod
    def from_json(cls, attrs: dict) -> 'CompoundFrame':
        compound = attrs['compound']
        body = [parse(item) for item in attrs['content']]
        params = attrs.get('params', [])

        return CompoundFrame(body=body,
                             params=params,
                             compound=compound,
                             alias=None)


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
