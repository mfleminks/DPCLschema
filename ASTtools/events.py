from __future__ import annotations
from typing import TYPE_CHECKING

from abc import ABCMeta, abstractmethod

from ASTtools import exceptions


# Prevent recursive imports
if TYPE_CHECKING:
    import ASTtools.nodes as nodes


class BaseEventHandler(metaclass=ABCMeta):
    """
    Base class for handling an event's observers
    """
    # TODO make ABC?
    def __init__(self):
        super().__init__()

        # self.callbacks = {}
        self.callbacks: set[nodes.EventListener] = set()

    def add_callback(self, callback: nodes.EventListener):
        # self.callbacks.append(callback)
        # self.callbacks[callback.internal_id] = callback
        self.callbacks.add(callback)

    def remove_callback(self, callback: nodes.EventListener):
        # del self.callbacks[callback.internal_id]
        self.callbacks.remove(callback)

    def notify_callbacks(self, **kwargs):
        # TODO this will crash if a callback adds or removes a callback e.g. cross_road
        # for callback in self.callbacks.values():
        for callback in self.callbacks:
            callback.notify(**kwargs)

    def fire(self, **kwargs):
        self.notify_callbacks(**kwargs)

    @classmethod
    @abstractmethod
    def get_event(cls, **kwargs):
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


class DummyEventHandler(BaseEventHandler):
    def fire(self, **kwargs):
        raise TypeError("A DummyEventHandler should never be fired")

    @classmethod
    def get_event(cls, **kwargs):
        return DummyEventHandler()


class ProductionEventHandler(BaseEventHandler):
    __instances = {}

    def __init__(self, object: nodes.GenericObject, new_state: bool):
        super().__init__()
        self.object = object
        self.new_state = new_state

    @classmethod
    def get_event(cls, object: nodes.GenericObject, new_state: bool) -> ProductionEventHandler:
        # return object.get_production_event(new_state)

        key = (object, new_state)

        if key not in cls.__instances:
            cls.__instances[key] = ProductionEventHandler(object, new_state)

        return cls.__instances[key]

    def __repr__(self) -> str:
        return f"ProductionEvent:{'+' if self.new_state else '-'}{self.object.full_name}"


class NamingEventHandler(BaseEventHandler):
    __instances = {}

    def __init__(self, object: nodes.GenericObject, descriptor: nodes.GenericObject, new_state: bool):
        super().__init__()
        self.object = object
        self.descriptor = descriptor
        self.new_state = new_state

    @classmethod
    def get_event(cls, object: nodes.GenericObject, descriptor: nodes.GenericObject, new_state: bool) -> NamingEventHandler:
        key = (object, descriptor, new_state)

        if key not in cls.__instances:
            cls.__instances[key] = NamingEventHandler(object, descriptor, new_state)

        return cls.__instances[key]

    def __repr__(self) -> str:
        return f"NamingEvent{self.object} {'in' if self.new_state else 'out'} {self.descriptor}"


class ActionHandler(BaseEventHandler):
    __instances = {}

    def __init__(self, name: str):
        super().__init__()

        self.name = name
        # self.refinement = refinement or {}  # NOTE this is no longer an inherent part of the action
        # self.powers: dict[str, nodes.PowerFrame] = {}
        self.powers: set[nodes.PowerFrame] = set()

        self.__instances[name] = self

    def fire(self, _bypass_powers=False, **kwargs):
        """
        Parameters
        ----------
        _bypass_powers : bool, default False
            Debug option: if set to True, notify all callbacks regardless of powers
        """
        if 'holder' in kwargs and not (any(p.notify(action_args=kwargs) for p in self.powers) or _bypass_powers):
            print(f"Action {self.name} not enabled by any powers")
            # print(self.powers)
            # print(kwargs)
            return False

        return super().fire(**kwargs)

    def add_power(self, power: nodes.PowerFrame):
        # self.powers[power.internal_id] = power
        self.powers.add(power)

    def remove_power(self, power: nodes.PowerFrame):
        # del self.powers[power.internal_id]
        self.powers.remove(power)

    def matches(self, other: ActionHandler) -> bool:
        """
        Check if an event matches this event, for use by powers and deontic frames.
        By default, the check is for identity.

        Parameters
        ----------
        other : ActionHandler
            The action to compare against
        Returns
        -------
        bool
            Whether `other` matches this action
        """
        return other is self

    @classmethod
    def get_event(cls, name: str) -> ActionHandler:
        if name not in cls.__instances:
            cls.__instances[name] = cls(name)

        if name == "#*":
            return WildcardActionHandler.get_event()

        return cls.__instances[name]

    def __repr__(self) -> str:
        return f"Action:{self.name}"


class WildcardActionHandler(ActionHandler):
    """
    Dummy action, for use as selector by powers and doentic frames.
    Will match any action.
    """
    def __init__(self):
        super().__init__("#*")

    def matches(self, other: ActionHandler) -> bool:
        return True

    @classmethod
    def get_event(cls) -> WildcardActionHandler:
        return cls()

    def fire(self, **kwargs):
        raise exceptions.DPCLTypeError("WildcardActionHandler is not meant to be fired")
