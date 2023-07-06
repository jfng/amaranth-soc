from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from amaranth import *


__all__ = ["GenericField", "FieldMap", "FieldArray"]


class GenericField(metaclass=ABCMeta):
    def __init__(self, shape, *, reset=0):
        try:
            shape = Shape.cast(shape)
        except TypeError as e:
            raise TypeError("Field shape must be a shape-castable object, not {!r}"
                            .format(shape)) from e
        self._shape = shape

        try:
            reset = Const.cast(reset)
        except TypeError as e:
            raise TypeError("Reset value must be a constant-castable expression, not {!r}"
                            .format(reset)) from e
        self._reset = reset

    @property
    def shape(self):
        return self._shape

    @property
    def reset(self):
        return self._reset

    @abstractmethod
    def intr_read(self, field):
        pass

    @abstractmethod
    def intr_write(self, field, value):
        pass

    @abstractmethod
    def user_read(self, field):
        pass

    @abstractmethod
    def user_write(self, field, value):
        pass


class FieldMap:
    def __init__(self, members):
        offset = 0
        self._fields = {}

        if not isinstance(members, Mapping):
            raise TypeError("Field map members must be provided as a mapping, not {!r}"
                            .format(members))

        for key, field in members.items():
            if not isinstance(key, str):
                raise TypeError("Field name must be a string, not {!r}"
                                .format(key))
            if not isinstance(field, (GenericField, FieldMap, FieldArray)):
                raise TypeError("Field must be a GenericField, a FieldMap or a FieldArray, "
                                "not {!r}"
                                .format(field))
            self._fields[key] = field

            if isinstance(field, GenericField):
                offset += Shape.cast(field.shape).width
            else:
                offset += field.size

        self._size = offset

    @property
    def size(self):
        return self._size

    def __iter__(self):
        yield from self._fields.items()

    def __len__(self):
        return len(self._fields)

    def __getitem__(self, key):
        return self._fields[key]

    def all_fields(self, *, name_prefix=""):
        for key, field in self._fields.items():
            field_name = f"{name_prefix}__{key}"
            if isinstance(field, GenericField):
                yield field_name, field
            elif isinstance(field, (FieldMap, FieldArray)):
                yield from field.all_fields(name_prefix=field_name)
            else:
                assert False


class FieldArray:
    def __init__(self, field, length):
        if not isinstance(field, (GenericField, FieldMap, FieldArray)):
            raise TypeError("Field must be a GenericField, a FieldMap or a FieldArray, "
                            "not {!r}"
                            .format(field))
        if not isinstance(length, int) or length < 0:
            raise TypeError("Field array length must be a non-negative integer, not {!r} "
                            .format(length))

        self._field  = field
        self._length = length

        if isinstance(field, GenericField):
            self._size = Shape.cast(field.shape).width * length
        else:
            self._size = field.size * length

    @property
    def size(self):
        return self._size

    def __iter__(self):
        for index in range(self._length):
            yield self._field

    def __len__(self):
        return self._length

    def __getitem__(self, key):
        if isinstance(key, int):
            if key not in range(-self._length, self._length):
                raise IndexError(key)
            return self._field
        raise TypeError("Cannot index field array with {!r}".format(key))

    def all_fields(self, *, name_prefix=""):
        for index in range(self._length):
            field_name = f"{name_prefix}__{index}"
            if isinstance(self._field, GenericField):
                yield field_name, self._field
            elif isinstance(self._field, (FieldMap, FieldArray)):
                yield from self._field.all_fields(name_prefix=field_name)
            else:
                assert False
