from collections.abc import Mapping, Sequence
import enum
from amaranth import *

from ..memory import MemoryMap
from .bus import Element


__all__ = ["FieldPort", "Field", "FieldMap", "FieldArray", "Register", "Cluster"]


class FieldPort:
    class Access(enum.Enum):
        """Field access mode."""
        R  = "r"
        W  = "w"
        RW = "rw"

        def readable(self):
            return self == self.R or self == self.RW

        def writable(self):
            return self == self.W or self == self.RW

    """CSR register field port.

    An interface between a CSR register and one of its fields.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    access : :class:`FieldPort.Access`
        Field access mode.

    Attributes
    ----------
    r_data : Signal(shape)
        Read data. Must always be valid, and is sampled when ``r_stb`` is asserted.
    r_stb : Signal()
        Read strobe. Fields with read side effects should perform them when this strobe is
        asserted.
    w_data : Signal(shape)
        Write data. Valid only when ``w_stb`` is asserted.
    w_stb : Signal()
        Write strobe. Fields should update their value or perform the write side effect when
        this strobe is asserted.

    Raises
    ------
    :exc:`TypeError`
        If ``shape`` is not a shape-castable object.
    :exc:`ValueError`
        If ``access`` is not a member of :class:`FieldPort.Access`.
    """
    def __init__(self, shape, access):
        try:
            shape = Shape.cast(shape)
        except TypeError as e:
            raise TypeError("Field shape must be a shape-castable object, not {!r}"
                            .format(shape)) from e
        if not isinstance(access, FieldPort.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        self._shape  = shape
        self._access = FieldPort.Access(access)

        self.r_data  = Signal(shape)
        self.r_stb   = Signal()
        self.w_data  = Signal(shape)
        self.w_stb   = Signal()

    @property
    def shape(self):
        return self._shape

    @property
    def access(self):
        return self._access

    def __repr__(self):
        return "FieldPort({}, {})".format(self.shape, self.access)


class Field(Elaboratable):
    """A generic register field.

    Parameters
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    access : :class:`FieldPort.Access`
        Field access mode.

    Attributes
    ----------
    port : :class:`FieldPort`
        Field port.
    data : Signal(shape)
        Field value.
    """
    def __init__(self, shape, access):
        self.port = FieldPort(shape, access)
        self.data = Signal(shape)

    @property
    def shape(self):
        return self.port.shape

    @property
    def access(self):
        return self.port.access


class FieldMap(Mapping):
    """A mapping of CSR register fields.

    Parameters
    ----------
    fields : dict of :class:`str` to one of :class:`Field` or :class:`FieldMap`.
    """
    def __init__(self, fields):
        self._fields = {}

        if not isinstance(fields, Mapping) or len(fields) == 0:
            raise TypeError("Fields must be provided as a non-empty mapping, not {!r}"
                            .format(fields))

        for key, field in fields.items():
            if not isinstance(key, str) or not key:
                raise TypeError("Field name must be a non-empty string, not {!r}"
                                .format(key))
            if not isinstance(field, (Field, FieldMap, FieldArray)):
                raise TypeError("Field must be a Field or a FieldMap or a FieldArray, not {!r}"
                                .format(field))
            self._fields[key] = field

    def __getitem__(self, key):
        """Access a field by name or index.

        Returns
        --------
        :class:`Field` or :class:`FieldMap` or :class:`FieldArray`
            The field associated with ``key``.

        Raises
        ------
        :exc:`KeyError`
            If there is no field associated with ``key``.
        """
        return self._fields[key]

    def __getattr__(self, name):
        """Access a field by name.

        Returns
        -------
        :class:`Field` or :class:`FieldMap` or :class:`FieldArray`
            The field associated with ``name``.

        Raises
        ------
        :exc:`AttributeError`
            If the field map does not have a field associated with ``name``.
        :exc:`AttributeError`
            If ``name`` is reserved (i.e. starts with an underscore).
        """
        try:
            item = self[name]
        except KeyError:
            raise AttributeError("Field map does not have a field {!r}; "
                                 "did you mean one of: {}?"
                                 .format(name, ", ".join(repr(name) for name in self.keys())))
        if name.startswith("_"):
            raise AttributeError("Field map field {!r} has a reserved name and may only be "
                                 "accessed by indexing"
                                 .format(name))
        return item

    def __iter__(self):
        """Iterate over the field map.

        Yields
        ------
        :class:`str`
            Key (name) for accessing the field.
        """
        yield from self._fields

    def __len__(self):
        return len(self._fields)

    def flatten(self):
        """Recursively iterate over the field map.

        Yields
        ------
        iter(:class:`str`)
            Name of the field. It is prefixed by the name of every nested field collection.
        :class:`Field`
            Register field.
        """
        for key, field in self.items():
            if isinstance(field, Field):
                yield (key,), field
            elif isinstance(field, (FieldMap, FieldArray)):
                for sub_name, sub_field in field.flatten():
                    yield (key, *sub_name), sub_field
            else:
                assert False # :nocov:


class FieldArray(Sequence):
    """An array of CSR register fields.

    Parameters
    ----------
    field : :class:`Field`
    length : :class:`int`

    Attributes
    ----------
    size : int
        The amount of bits required to store the field array.
    shape : :class:`ArrayLayout`
        Shape of the field array.
    """
    def __init__(self, field, length):
        if not isinstance(field, (Field, FieldMap, FieldArray)):
            raise TypeError("Field must be a Field or a FieldMap or a FieldArray, not {!r}"
                            .format(field))
        if not isinstance(length, int) or length <= 0:
            raise TypeError("Field array length must be a positive integer, not {!r}"
                            .format(length))

        self._field  = field
        self._length = length

    def __getitem__(self, key):
        """Access a field by index.

        Returns
        --------
        :class:`Field` or :class:`FieldMap` or :class:`FieldArray`
            The field associated with ``key``.

        Raises
        ------
        :exc:`IndexError`
            If ``key`` is out of bounds.
        :exc:`TypeError`
            If ``key`` is not an :class:`int`.
        """
        if isinstance(key, int):
            if key not in range(-self._length, self._length):
                raise IndexError(key)
            return self._field
        raise TypeError("Cannot index field array with {!r}".format(key))

    def __len__(self):
        return self._length

    def flatten(self):
        """Recursively iterate over the field array.

        Yields
        ------
        iter(:class:`str`)
            Name of the field. It is prefixed by the name of every nested field collection.
        :class:`Field`
            Register field.
        """
        for key in range(self._length):
            if isinstance(self._field, Field):
                yield (key,), self._field
            elif isinstance(self._field, (FieldMap, FieldArray)):
                for sub_name, sub_field in self._field.flatten():
                    yield (key, *sub_name), sub_field
            else:
                assert False # :nocov:

    def __eq__(self, other):
        return isinstance(other, FieldArray) and list(self) == list(other)


class Register(Elaboratable):
    """CSR register.

    Parameters
    ----------
    access : :class:`Element.Access`
        Register access mode.
    fields : :class:`FieldMap` or :class:`FieldArray`
        Collection of register fields. If ``None`` (default), a :class:`FieldMap` is created
        from Python :term:`variable annotations <python:variable annotations>`.

    Attributes
    ----------
    element : :class:`Element`
        Interface between this register and a CSR bus primitive.
    f : :class:`FieldMap` or :class:`FieldArray`
        Collection of register fields.

    Raises
    ------
    :exc:`ValueError`
        If ``access`` is not a member of :class:`Element.Access`.
    :exc:`TypeError`
        If ``fields`` is not ``None`` or a :class:`FieldMap` or a :class:`FieldArray`.
    :exc:`ValueError`
        If ``access`` is not readable and at least one field is readable.
    :exc:`ValueError`
        If ``access`` is not writable and at least one field is writable.
    """
    def __init__(self, access, fields=None):
        if not isinstance(access, Element.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        access = Element.Access(access)

        if fields is None and hasattr(self, "__annotations__"):
            fields = {}
            for key, field in self.__annotations__.items():
                if isinstance(field, (Field, FieldMap, FieldArray)):
                    fields[key] = field
            fields = FieldMap(fields)

        if not isinstance(fields, (FieldMap, FieldArray)):
            raise TypeError("Field collection must be a FieldMap or a FieldArray, not {!r}"
                            .format(fields))

        width = 0
        for field_name, field in fields.flatten():
            width += Shape.cast(field.shape).width
            if field.access.readable() and not access.readable():
                raise ValueError("Field {} is readable, but register access mode is '{}'"
                                 .format("__".join(field_name), access))
            if field.access.writable() and not access.writable():
                raise ValueError("Field {} is writable, but register access mode is '{}'"
                                 .format("__".join(field_name), access))

        self.element = Element(width, access)
        self._fields = fields

    @property
    def f(self):
        return self._fields

    def __iter__(self):
        """Recursively iterate over the field collection.

        Yields
        ------
        iter(:class:`str`)
            Name of the field. It is prefixed by the name of every nested field collection.
        :class:`Field`
            Register field.
        """
        yield from self._fields.flatten()

    def elaborate(self, platform):
        m = Module()

        field_start = 0

        for field_name, field in self:
            m.submodules["__".join(str(key) for key in field_name)] = field

            field_slice = slice(field_start, field_start + Shape.cast(field.shape).width)

            if field.access.readable():
                m.d.comb += [
                    self.element.r_data[field_slice].eq(field.port.r_data),
                    field.port.r_stb.eq(self.element.r_stb),
                ]
            if field.access.writable():
                m.d.comb += [
                    field.port.w_data.eq(self.element.w_data[field_slice]),
                    field.port.w_stb .eq(self.element.w_stb),
                ]

            field_start = field_slice.stop

        return m


class Cluster:
    """A group of neighboring CSR registers.

    Parameters
    ----------
    name : :class:`str
        Name of the cluster.
    addr_width : :class:`int`
        Address width.
    data_width : :class:`int`
        Data width.
    alignment : :class:`int`
        Range alignment. Each added register will be placed at an address that is a multiple of
        ``2 ** alignment``, and its size will be rounded up to be a multiple of ``2 ** alignment``.
        Optional, defaults to 0.
    access : :class:`Element.Access`
        Cluster access mode. Individual registers can have more restrictive access modes, e.g.
        R/O registers can be a part of an R/W cluster. Optional, defaults to R/W.

    Attributes
    ----------
    memory_map : :class:`MemoryMap`
        Map of the cluster address space. The memory map is frozen as a side-effect of referencing
        this attribute.

    Raises
    ------
    :exc:`ValueError`
        If ``access`` is not a member of :class:`Element.Access`.
    """
    def __init__(self, *, name, addr_width, data_width, alignment=0, access="rw"):
        if not isinstance(access, Element.Access) and access not in ("r", "w", "rw"):
            raise ValueError("Access mode must be one of \"r\", \"w\", or \"rw\", not {!r}"
                             .format(access))
        self._access = Element.Access(access)
        self._map    = MemoryMap(addr_width=addr_width, data_width=data_width, alignment=alignment,
                                 name=name)

    @property
    def access(self):
        return self._access

    @property
    def memory_map(self):
        self._map.freeze()
        return self._map

    def freeze(self):
        """Freeze the cluster.

        Once the cluster is frozen, registers cannot be added anymore.
        """
        self._map.freeze()

    def add(self, reg, *, name, addr, alignment=None, extend=False):
        """Add a register.

        See :meth:`MemoryMap.add_resource for details.

        Returns
        -------
        The register ``reg``, which is added to the cluster.

        Raises
        ------
        :exc:`TypeError`
            If ``reg` is not an instance of :class:`Register`.
        :exc:`ValueError`
            If the cluster is not readable and ``reg.element`` is readable.
        :exc:`ValueError`
            If the cluster is not writable and ``reg.element`` is writable.
        """
        if not isinstance(reg, Register):
            raise TypeError("Register must be an instance of csr.Register, not {!r}"
                            .format(reg))
        if reg.element.access.readable() and not self.access.readable():
            raise ValueError("Register {} is readable, but cluster access mode is {}"
                             .format(name, self.access))
        if reg.element.access.writable() and not self.access.writable():
            raise ValueError("Register {} is writable, but cluster access mode is {}"
                             .format(name, self.access))

        size = (reg.element.width + self._map.data_width - 1) // self._map.data_width
        self._map.add_resource(reg.element, name=name, size=size, addr=addr, alignment=alignment,
                               extend=extend)
        return reg
