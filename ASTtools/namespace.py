from __future__ import annotations

from collections import defaultdict
from typing import Optional, Union, TYPE_CHECKING


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
    def __init__(self, name: str, parent: Optional['Namespace'] = None, initial: dict[str, nodes.Node] = None) -> None:
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
        KeyError
            When the requested name can't be found
        """
        result = self.__symbol_table.get(name, None)
        if result is None:
            if self.parent is not None and recursive:
                return self.parent.get(name, True)

            print(f"can't find {name} in {self.__symbol_table}")
            raise KeyError

        return result

    def as_list(self):
        return list(self.__symbol_table.values())

    def add(self, name: str, value: nodes.Node, overwrite = False):
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
