from .reg import GenericField


__all__ = ["R", "W", "RW", "RW1C", "RW1S"]


class R(GenericField):
    def intr_read(self, field):
        return field

    def intr_write(self, field, value):
        return None

    def user_read(self, field):
        return field

    def user_write(self, field, value):
        return value


class W(GenericField):
    def intr_read(self, field):
        return None

    def intr_write(self, field, value):
        return value

    def user_read(self, field):
        return field

    def user_write(self, field):
        return None


class RW(GenericField):
    def intr_read(self, field):
        return field

    def intr_write(self, field, value):
        return value

    def user_read(self, field):
        return field

    def user_write(self, field):
        return None


class RW1C(GenericField):
    def intr_read(self, field):
        return field

    def intr_write(self, field, value):
        return field & ~value

    def user_read(self, field):
        return field

    def user_write(self, field):
        return field | value


class RW1S(GenericField):
    def intr_read(self, field):
        return field

    def intr_write(self, field, value):
        return field | value

    def user_read(self, field):
        return field

    def user_write(self, field):
        return field & ~value
