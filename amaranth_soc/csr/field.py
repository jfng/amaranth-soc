from amaranth import *

from .reg import Field


__all__ = ["R", "W", "RW", "RW1C", "RW1S"]


class R(Field):
    def __init__(self, shape):
        super().__init__(shape, access="r")

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.port.r_data.eq(self.data)
        return m


class W(Field):
    def __init__(self, shape):
        super().__init__(shape, access="w")

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.data.eq(self.port.w_data)
        return m


class RW(Field):
    def __init__(self, shape, *, reset=0):
        super().__init__(shape, access="rw")
        self._storage = Signal(shape, reset=reset)
        self._reset   = reset

    @property
    def reset(self):
        return self._reset

    def elaborate(self, platform):
        m = Module()

        with m.If(self.port.w_stb):
            m.d.sync += self._storage.eq(self.port.w_data)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class RW1C(Field):
    def __init__(self, shape, *, reset=0):
        super().__init__(shape, access="rw")
        self.set      = Signal(shape)
        self._storage = Signal(shape, reset=reset)
        self._reset   = reset

    @property
    def reset(self):
        return self._reset

    def elaborate(self, platform):
        m = Module()

        for i, storage_bit in enumerate(self._storage):
            with m.If(self.port.w_stb & self.port.w_data[i]):
                m.d.sync += storage_bit.eq(0)
            with m.If(self.set[i]):
                m.d.sync += storage_bit.eq(1)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class RW1S(Field):
    def __init__(self, shape, *, reset=0):
        super().__init__(shape, access="rw")
        self.clear    = Signal(shape)
        self._storage = Signal(shape, reset=reset)

    @property
    def reset(self):
        return self._reset

    def elaborate(self, platform):
        m = Module()

        for i, storage_bit in enumerate(self._storage):
            with m.If(self.clear[i]):
                m.d.sync += storage_bit.eq(0)
            with m.If(self.port.w_stb & self.port.w_data[i]):
                m.d.sync += storage_bit.eq(1)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m
