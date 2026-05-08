from typing import Optional, Any

class StackIsEmpty(Exception):
    pass

class Stack():
    def __init__(self, items = None):
        self._items = list(items) if items is not None else []

    def push(self, value: Any) -> None:
        self._items.append(value)

    def pop(self) -> Any:
        if self.is_empty():
            raise StackIsEmpty("pop from empty stack")
        return self._items.pop()

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def __len__(self) -> int:
        return len(self._items)

    def __str__(self) -> str:
        string = ", ".join(str(i) for i in self._items)
        return f"Stack({string})"

    def __repr__(self) -> str:
        return f"Stack({repr(self._items)})"

    def __iter__(self) -> Any:
        return iter(self._items)

    def __contains__(self, item) -> bool:
        return item in self._items

    def __getitem__(self, index) -> Any:
        return self._items[index]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._items.clear()
        return False

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Stack):
            return NotImplemented
        return self._items == other._items