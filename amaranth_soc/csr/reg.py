from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from amaranth import *
from amaranth.lib import data

from .bus import Element


__all__ = ["GenericField", "FieldMap", "FieldArray", "Register"]


class GenericField(metaclass=ABCMeta):
    """A generic register field.

    Attributes
    ----------
    shape : :ref:`shape-castable <lang-shapecasting>`
        Shape of the field.
    reset : int or integral Enum
        Reset or default value. Defaults to 0.
    """

    def __init_subclass__(cls, *, intr_read, intr_write, user_read, user_write, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.intr_read  = intr_read
        cls.intr_write = intr_write
        cls.user_read  = user_read
        cls.user_write = user_write

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


class FieldMap:
    """A mapping of CSR register fields.

    Parameters
    ----------
    fields : dict of :class:`str` to one of :class:`GenericField` or :class:`FieldMap` or :class:`FieldArray`
    """
    def __init__(self, fields):
        offset = 0
        self._fields = {}

        if not isinstance(fields, Mapping):
            raise TypeError("Fields must be provided as a mapping, not {!r}"
                            .format(fields))

        for key, field in fields.items():
            if not isinstance(key, str):
                raise TypeError("Field name must be a string, not {!r}"
                                .format(key))
            if not isinstance(field, (GenericField, FieldMap)):
                raise TypeError("Field must be a GenericField, a FieldMap or a FieldArray, "
                                "not {!r}"
                                .format(field))
            self._fields[key] = field

            if isinstance(field, GenericField):
                offset += Shape.cast(field.shape).width
            else:
                offset += field.size

        self._size = offset

    def __getitem__(self, key):
        return self._fields[key]

    def __iter__(self):
        """Iterate over the field map.

        Yields
        ------
        key : :class:`str`
        field : :class:`GenericField` or :class:`FieldMap` or :class:`FieldArray`
        """
        for key, field in self._fields.items():
            yield key, field

    @property
    def size(self):
        """Total size of the field map.

        Returns
        -------
        :class:`int`
            The amount of bits required to store every field of the mapping.
        """
        return self._size

    @property
    def shape(self):
        return data.StructLayout({
            name: field.shape for name, field in iter(self)
        })

    def all_fields(self):
        """Recursively iterate over the field map.
        """
        for key, field in iter(self):
            if isinstance(field, GenericField):
                yield (str(key),), field
            elif isinstance(field, FieldMap):
                for sub_name, sub_field in field.all_fields():
                    yield (str(key), *sub_name), sub_field
            else:
                assert False

    def resets(self):
        resets = dict()
        for key, field in iter(self):
            if isinstance(field, GenericField):
                resets[str(key)] = field.reset
            elif isinstance(field, FieldMap):
                for sub_name, sub_field in field.all_fields():
                    resets[str(key)] = field.resets()
            else:
                assert False
        return resets


class FieldArray(FieldMap):
    def __init__(self, field, length):
        if not isinstance(field, (GenericField, FieldMap)):
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

    def __getitem__(self, key):
        if isinstance(key, int):
            if key not in range(-self._length, self._length):
                raise KeyError(key)
            return self._field
        raise TypeError("Cannot index field array with {!r}".format(key))

    def __iter__(self):
        """Iterate over fields of the array.

        Yields
        ------
        key : :class:`int`
        field : :class:`GenericField` or :class:`FieldMap` or :class:`FieldArray`
        """
        for key in range(self._length):
            yield key, self._field

    @property
    def shape(self):
        return data.ArrayLayout(data.Field(self._field.shape))


class Register(Element, Elaboratable):
    def __init__(self, field_map=None):
        if field_map is None:
            if not hasattr(self, "__annotations__"):
                raise ValueError("Register {!r} doesn't have any fields"
                                 .format(self))
            field_map = FieldMap(self.__annotations__)

        if not isinstance(field_map, FieldMap):
            raise TypeError("Register fields must be provided as a FieldMap or a FieldArray, "
                            "not {!r}"
                            .format(field_map))

        super().__init__(field_map.size)

        class _FieldPort(object):
            pass

        self._field_map = field_map
        self._fields    = _FieldPort()
        self._readable  = False
        self._writable  = False

        def field_port(field, field_name):
            obj = _FieldPort()
            if field.user_write is not None:
                obj.w_data = Signal(field.shape, name=f"{field_name}__w_data")
                obj.w_stb  = Signal(name=f"{field_name}__w_stb")
                obj.w_ack  = Signal(name=f"{field_name}__w_ack")
            if field.user_read is not None:
                obj.r_data = Signal(field.shape, name=f"{field_name}__r_data")
                obj.r_stb  = Signal(name=f"{field_name}__r_stb")
            return obj

        for name, field in self.field_map.all_fields():
            field_name = "__".join(name)
            setattr(self._fields, field_name, field_port(field, field_name))

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

    @property
    def f(self):
        return self._fields

    def elaborate(self, platform):
        m = Module()

        storage = Signal(self.field_map.shape) # FIXME reset=self.field_map.resets()

        def get_slice(view, field_name):
            view_slice = view
            for key in field_name:
                view_slice = view_slice[key]
            return view_slice

        def get_user_port(field_name):
            port_field = self.f
            for key in field_name:
                port_field = getattr(port_field, key)
            return port_field

        for field_name, field in self.field_map.all_fields():
            storage_field = get_slice(storage,     field_name)
            r_data_field  = get_slice(self.r_data, field_name)
            w_data_field  = get_slice(self.w_data, field_name)
            user_port     = get_user_port(field_name)

            if field.intr_read is not None:
                m.d.comb += r_data_field.eq(field.intr_read(storage_field))

            if field.intr_write is not None:
                with m.If(self.w_stb):
                    m.d.sync += storage_field.eq(field.intr_write(storage_field, w_data_field))

            if field.user_read is not None:
                m.d.sync += user_port.r_stb .eq(self.w_stb)
                m.d.comb += user_port.r_data.eq(field.user_read(storage_field))

            if field.user_write is not None:
                m.d.comb += user_port.w_ack.eq(self.r_stb)
                with m.If(user_port.w_stb):
                    m.d.sync += storage_field.eq(field.user_write(storage_field, user_port.w_data))

        return m
