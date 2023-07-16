from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from amaranth import *
from amaranth.lib import data

from .bus import Element


__all__ = ["GenericField", "FieldMap", "FieldArray", "RegisterInterface", "Register"]


class GenericField(metaclass=ABCMeta):
    """A generic register field.

    Attributes
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    reset : int or integral Enum
        Reset or default value. Defaults to 0.
    """
    def __init__(self, shape, *, reset=0):
        try:
            shape = Shape.cast(shape)
        except TypeError as e:
            raise TypeError("Field shape must be a shape-castable object, not {!r}"
                            .format(shape)) from e
        self._shape = shape

        try:
            Const.cast(reset)
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

    def __eq__(self, other):
        """Compare register fields.

        Two fields are equal if they have the same type, shape and reset value.
        """
        return type(self) == type(other) and \
                Shape.cast(self._shape) == Shape.cast(other.shape) and \
                Const.cast(self._reset).value == Const.cast(other.reset).value

    @staticmethod
    @abstractmethod
    def intr_read(storage):
        """Read from the bus initiator.

        Parameters
        ----------
        storage : :class:`Value`
            The value of this field in the register storage.

        Returns
        -------
        The :class:`Value` of this field returned to the bus initiator.
        """

    @staticmethod
    @abstractmethod
    def intr_write(storage, w_data):
        """Write from the bus initiator.

        Parameters
        ----------
        storage : :class:`Value`
            The value of this field in the register storage.
        w_data : :class:`Value`
            The value written to this field by the bus initiator.

        Returns
        -------
        The :class:`Value` of this field written to the register storage.
        """

    @staticmethod
    @abstractmethod
    def user_write(storage, w_data):
        """Write from user logic.

        Parameters
        ----------
        storage : :class:`Value`
            The value of this field in the register storage.
        w_data : :class:`Value`
            The value written to this field by user logic.

        Returns
        -------
        The :class:`Value` of this field written to the register storage.
        """


class FieldMap:
    """A mapping of CSR register fields.

    Parameters
    ----------
    fields : dict of :class:`str` to one of :class:`GenericField` or :class:`FieldMap`.

    Attributes
    ----------
    size : int
        The amount of bits required to store the field map.
    shape : :class:`StructLayout`
        Shape of the field map.
    reset : dict
        The reset value associated with the field map.
    """
    def __init__(self, fields):
        offset = 0
        self._fields = {}

        if not isinstance(fields, Mapping) or len(fields) == 0:
            raise TypeError("Fields must be provided as a non-empty mapping, not {!r}"
                            .format(fields))

        for key, field in fields.items():
            if not isinstance(key, str) or not key:
                raise TypeError("Field name must be a non-empty string, not {!r}"
                                .format(key))
            if not isinstance(field, (GenericField, FieldMap)):
                raise TypeError("Field must be a GenericField or a FieldMap, not {!r}"
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

    @property
    def shape(self):
        return data.StructLayout({name: field.shape for name, field in self})

    @property
    def reset(self):
        return {key: field.reset for key, field in self}

    def __getitem__(self, key):
        """Retrieve a field from the field map.

        Returns
        --------
        :class:`GenericField` or :class:`FieldMap`
            The field associated with ``key``.

        Raises
        ------
        :exc:`KeyError`
            If there is not field associated with ``key``.
        """
        return self._fields[key]

    def __iter__(self):
        """Iterate over the field map.

        Yields
        ------
        :class:`str`
            Key (name) for accessing the field.
        :class:`GenericField` or :class:`FieldMap`
            Field description.
        """
        for key, field in self._fields.items():
            yield key, field

    def all_fields(self):
        """Recursively iterate over the field map.

        Yields
        ------
        iter(:class:`str`)
            Name of the field. It is prefixed by the name of every nested field map.
        :class:`GenericField`
            Field description.
        """
        for key, field in self:
            if isinstance(field, GenericField):
                yield (key,), field
            elif isinstance(field, FieldMap):
                for sub_name, sub_field in field.all_fields():
                    yield (key, *sub_name), sub_field
            else:
                assert False # :nocov:

    def __eq__(self, other):
        """Compare field maps.

        Two field maps are equal if they have the same size and the same fields under the same name
        in the same order.
        """
        return isinstance(other, FieldMap) and self.size == other.size and \
                list(self) == list(other)


class FieldArray(FieldMap):
    """An array of CSR register fields.

    Parameters
    ----------
    field : :class:`GenericField`
    length : :class:`int`

    Attributes
    ----------
    size : int
        The amount of bits required to store the field array.
    shape : :class:`ArrayLayout`
        Shape of the field array.
    """
    def __init__(self, field, length):
        if not isinstance(field, (GenericField, FieldMap)):
            raise TypeError("Field must be a GenericField or a FieldMap, not {!r}"
                            .format(field))
        if not isinstance(length, int) or length <= 0:
            raise TypeError("Field array length must be a positive integer, not {!r}"
                            .format(length))

        self._field  = field
        self._length = length

        if isinstance(field, GenericField):
            self._size = Shape.cast(field.shape).width * length
        else:
            self._size = field.size * length

    @property
    def shape(self):
        return data.ArrayLayout(self._field.shape, self._length)

    @property
    def reset(self):
        return [self._field.reset for key in range(self._length)]

    def __getitem__(self, key):
        """Retrieve a field from the field array.

        Returns
        --------
        :class:`GenericField` or :class:`FieldMap`
            The field associated with ``key``.

        Raises
        ------
        :exc:`KeyError`
            If ``key`` is out of bounds.
        :exc:`TypeError`
            If ``key`` is not an :class:`int`.
        """
        if isinstance(key, int):
            if key not in range(-self._length, self._length):
                raise KeyError(key)
            return self._field
        raise TypeError("Cannot index field array with {!r}".format(key))

    def __iter__(self):
        """Iterate over the field array.

        Yields
        ------
        key : :class:`int`
            Key (index) for accessing the field.
        field : :class:`GenericField` or :class:`FieldMap`
            Field description.
        """
        for key in range(self._length):
            yield key, self._field


class RegisterInterface(Element):
    """CSR register interface.

    Parameters
    ----------
    field_map : :class:`FieldMap`
        Description of the register fields. If ``None`` (default), a :class:`FieldMap` is created
        from Python :term:`variable annotations <python:variable annotations>`.
    """
    def __init__(self, field_map=None):
        if field_map is None and hasattr(self, "__annotations__"):
            fields = {}
            for key, field in self.__annotations__.items():
                if isinstance(field, (GenericField, FieldMap)):
                    fields[key] = field

            field_map = FieldMap(fields)

        if not isinstance(field_map, FieldMap):
            raise TypeError("Field map must be a FieldMap, not {!r}"
                            .format(field_map))

        super().__init__(field_map.size)

        self._field_map = field_map
        self._readable  = False
        self._writable  = False

        for name, field in self.field_map.all_fields():
            if field.intr_read is not None:
                self._readable = True
            if field.intr_write is not None:
                self._writable = True

        self.w_data = Signal(self.field_map.shape)
        self.w_stb  = Signal()
        self.r_data = Signal(self.field_map.shape)
        self.r_stb  = Signal()

    @property
    def field_map(self):
        return self._field_map

    @property
    def readable(self):
        return self._readable

    @property
    def writable(self):
        return self._writable


class Register(RegisterInterface, Elaboratable):
    class UserPort:
        def __init__(self, field_map, name=""):
            assert isinstance(field_map, FieldMap)
            assert isinstance(name, str)

            self._fields = {}

            for key, field in field_map:
                orig_key = key

                # Indices are prefixed with 'n' to avoid names starting with a digit.
                if isinstance(key, int):
                    key = f"n{key}"

                field_name = "{}{}{}".format(name, "__" if name else "", key)

                if isinstance(field, GenericField):
                    port = Register.FieldPort(field, field_name)
                elif isinstance(field, FieldMap):
                    port = Register.UserPort(field, field_name)
                else:
                    assert False # :nocov:

                self._fields[orig_key] = port

        def __getitem__(self, key):
            return self._fields[key]

        def __getattr__(self, name):
            return self[name]

    class FieldPort:
        def __init__(self, field, name):
            assert isinstance(field, GenericField)
            assert isinstance(name, str)

            self.field = field
            self.name  = name

            if field.user_write is not None:
                self.w_mask = Signal(field.shape, name=f"{name}__w_mask")
                self.w_data = Signal(field.shape, name=f"{name}__w_data")
                self.w_ack  = Signal(name=f"{name}__w_ack")

            self.r_data = Signal(field.shape, name=f"{name}__r_data")
            self.r_stb  = Signal(name=f"{name}__r_stb")

    """CSR register.

    Attributes
    ----------
    field_map : :class:`FieldMap`
        Description of the register fields. See also :class:`RegisterInterface`.
    f : :class:`Register.UserPort`
        Port to user logic.
    """
    def __init__(self, field_map=None):
        super().__init__(field_map)
        self._f = Register.UserPort(field_map, name="")

    @property
    def f(self):
        return self._f

    def elaborate(self, platform):
        m = Module()

        storage = Signal(self.field_map.shape, reset=self.field_map.reset)

        def get_field(root, field_name):
            node = root
            for key in field_name:
                node = node[key]
            return node

        for name, field in self.field_map.all_fields():
            storage_slice = get_field(storage, name)
            r_data_slice  = get_field(self.r_data, name)
            w_data_slice  = get_field(self.w_data, name)
            user          = get_field(self.f, name)

            if field.intr_read is not None:
                m.d.comb += r_data_slice.eq(field.intr_read(storage_slice))

            m.d.comb += user.r_data.eq(storage_slice)

            # We assume no precedence rule between writes from initiator or user logic. Both write
            # values are masked with their enables then OR-ed together as a single value, which is
            # only written to storage if a write enable is asserted.
            #
            # A field can use this to implement its own precedence rule: one side (e.g. initiator)
            # can only set a bit, while the other (e.g. user logic) can only clear it. Setting the
            # bit would always have precedence. See csr.field.RW1C and RW1S for an example.

            if field.intr_write is not None:
                intr_w_data = field.intr_write(storage_slice, w_data_slice)
                m.d.sync += user.r_stb.eq(self.w_stb)

            if field.user_write is not None:
                user_w_data = field.user_write(storage_slice, user.w_data)
                m.d.comb += user.w_ack.eq(self.r_stb)

            for i, storage_bit in enumerate(storage_slice):
                storage_bit_en   = 0
                storage_bit_next = 0

                if field.intr_write is not None:
                    storage_bit_en   |= self.w_stb
                    storage_bit_next |= Mux(self.w_stb, intr_w_data[i], 0)

                if field.user_write is not None:
                    storage_bit_en   |= user.w_mask[i]
                    storage_bit_next |= Mux(user.w_mask[i], user_w_data[i], 0)

                with m.If(storage_bit_en):
                    m.d.sync += storage_bit.eq(storage_bit_next)

        return m
