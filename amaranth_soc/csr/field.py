from .reg import GenericField


__all__ = ["R", "W", "RW", "RW1C", "RW1S"]


# Capabilities

class _InitiatorReadable:
    def intr_read(self, storage):
        return storage


class _InitiatorWritable:
    def intr_write(self, storage, w_data):
        return w_data


class _InitiatorSettable:
    def intr_write(self, storage, w_data):
        return storage | w_data


class _InitiatorClearable:
    def intr_write(self, storage, w_data):
        return storage & ~w_data


class _UserWritable:
    def user_write(self, storage, w_data):
        return w_data


# Field types

class R   (_InitiatorReadable,                      _UserWritable, GenericField): intr_write = None
class W   (                    _InitiatorWritable,                 GenericField): intr_read  = None; user_write = None
class RW  (_InitiatorReadable, _InitiatorWritable,                 GenericField): user_write = None
class RW1C(_InitiatorReadable, _InitiatorClearable, _UserWritable, GenericField): pass
class RW1S(_InitiatorReadable, _InitiatorSettable,  _UserWritable, GenericField): pass
