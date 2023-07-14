from .reg import GenericField


__all__ = ["R", "W", "RW", "RW1C", "RW1S"]


# Capabilities

class _IntrRead:
    @staticmethod
    def intr_read(storage):
        return storage


class _IntrWrite:
    @staticmethod
    def intr_write(storage, w_data):
        return w_data


class _IntrSet:
    @staticmethod
    def intr_write(storage, w_data):
        return storage | w_data


class _IntrClear:
    @staticmethod
    def intr_write(storage, w_data):
        return storage & ~w_data


class _UserWrite:
    @staticmethod
    def user_write(storage, w_data):
        return w_data


class _UserSet:
    @staticmethod
    def user_write(storage, w_data):
        return storage | w_data


class _UserClear:
    @staticmethod
    def user_write(storage, w_data):
        return storage & ~w_data


# Field types

class R   (_IntrRead,             _UserWrite, GenericField): intr_write = None
class W   (           _IntrWrite,             GenericField): intr_read  = None; user_write = None
class RW  (_IntrRead, _IntrWrite,             GenericField): user_write = None
class RW1C(_IntrRead, _IntrClear, _UserSet,   GenericField): pass
class RW1S(_IntrRead, _IntrSet,   _UserClear, GenericField): pass
