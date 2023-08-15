from __future__ import annotations

from collections import defaultdict
from typing import Optional, Union, TYPE_CHECKING


from ASTtools import exceptions


if TYPE_CHECKING:
    import nodes


class Namespace:
    """
    A basic namespace to store the attributes of a single scope.

    Parameters
    ----------
    parent : Namespace, optional
        The Namespace object for the enclosing scope
    name : str
        The Namespace's name, should be unique
    initial : dict[str, nodes.Node], optional
        The intial contents of the symbol table
    """
    def __init__(self, name: str, parent: Namespace = None, initial: dict[str, nodes.Node] = None) -> None:
        self.name = name
        self.__symbol_table = initial or {}
        self.parent = parent
        self.__auto_id_ctr = defaultdict(int)

    def get(self, name: str, recursive=True) -> nodes.Node:
        """
        Retrieve an attribute from the namespace.

        Paramerers
        ----------
        name : str
            The name to search for in the namespace
        recursive : bool, default True
            If set to true, the parent Namespace will be searched as well
            The first object that matches will be returned

        Returns
        -------
        DPCLAstNode
            The object stored under the specified name

        Raises
        ------
        DPCLNameError
            When the requested name can't be found
        """
        # print(f"searching name '{name}' in namespace {self.full_name}")
        result = self.__symbol_table.get(name, None)
        if result is not None:
            return result

        if self.parent is not None and recursive:
            try:
                return self.parent.get(name, True)
            except exceptions.DPCLNameError:
                raise exceptions.DPCLNameError((f"can't resolve reference '{name}' in namespace {self.full_name}"))

        raise exceptions.DPCLNameError((f"can't resolve reference '{name}' in namespace {self.full_name}"))

    def as_list(self):
        return list(self.__symbol_table.items())

    def print(self):
        for name, value in self.__symbol_table.items():
            # skip auto-IDs
            if name.startswith('_'):
                continue

            print(f"{name}: {value}")
            # Print a compound's instances
            try:
                value.print_instances()
            except AttributeError:
                pass

    def add(self, name: str, value: nodes.Node, auto_id=True, overwrite=False):
        """
        Add an attribute to the namespace

        Parameters
        ----------
        name : str
            The name of the attribute
        value : DPCLAstNode
            The object itself
        auto_id : bool, default True
            If True, the value is also added under an auto-generated ID, as defined by `get_auto_id`
        overwrite : bool, default False
            If True, a pre-existing object of the same name will be overwritten

        Raises
        ------
        DPCLNameError
            If the name is already in use and overwrite is set to False
        """
        if name in self.__symbol_table and not overwrite:
            raise exceptions.DPCLNameError(f"Name {name} already exists in namespace {self.full_name}")

        if name is not None:
            self.__symbol_table[name] = value

        if auto_id:
            self.__symbol_table[self.get_auto_id(value.prefix)] = value

    @property
    def full_name(self) -> str:
        if self.parent is None or self.parent.full_name == "":
            return self.name

        return f'{self.parent.full_name}::{self.name}'

    def get_auto_id(self, prefix) -> str:
        """
        Create a new auto-incrementing ID. This takes the form `_<prefix><counter>`.
        """
        # TODO should the full name be part of the ID?
        # it might make more sense to just use the prefix+ctr,
        # and give the object a reference to its parent namespce, so its repr can decide whether to do full
        ctr = self.__auto_id_ctr[prefix]
        self.__auto_id_ctr[prefix] += 1
        return f'_{prefix}{ctr}'
        # return f'{self.full_name}::_{prefix}{ctr}'
