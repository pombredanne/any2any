# -*- coding: utf-8 -*-
import copy
try:
    import abc
except ImportError:
    from compat import abc
from base import Cast, Setting, CopiedSetting
from utils import closest_parent, Wrapped, Mm, memoize


# Abstract DivideAndConquerCast
#======================================
class DivideAndConquerCast(Cast):
    """
    Abstract base cast for metamorphosing `from` and `to` any complex object or container.

    In order to achieve casting, this class implements a "divide and conquer" strategy :

        1. `Divide into sub-problems` - :meth:`iter_input`
        2. `Solve sub-problems` - :meth:`iter_output`
        3. `Combine solutions` - :meth:`build_output`
    """

    @abc.abstractmethod
    def iter_input(self, inpt):
        """
        Divides a complex casting into several simpler castings.
 
        Args:
            inpt(object). The cast's input.

        Returns:
            iterator. ``(<key>, <value_to_cast>)``. An iterator on all items to cast in order to completely cast `inpt`.
        """
        return

    @abc.abstractmethod
    def iter_output(self, items_iter):
        """
        Casts all the items from `items_iter`.

        Args:
            items_iter(iterator). ``(<key>, <value_to_cast>)``. An iterator on items to cast.

        Returns:
            iterator. ``(<key>, <casted_value>)``. An iterator on casted items.
        """
        return

    @abc.abstractmethod
    def build_output(self, items_iter):
        """
        Combines all the items from `items_iter` into a final output.

        Args:
            items_iter(iterator). ``(<key>, <casted_value>)``. Iterator on casted items.

        Returns:
            object. The casted object in its final shape.
        """
        return

    def get_item_from(self, key):
        """
        Returns the type of the value associated with `key` if it is known "a priori" (without knowing the input), or `NotImplemented` to let the cast guess.
        """
        return NotImplemented

    def get_item_to(self, key):
        """
        Returns the type the value associated with `key` must be casted to, if it is known `a priori` (without knowing the input), or `NotImplemented` to let the cast guess.
        """
        return NotImplemented

    def call(self, inpt):
        iter_input = self.iter_input(inpt)
        iter_ouput = self.iter_output(iter_input)
        return self.build_output(iter_ouput)


# Wrappeds
#======================================
class WrappedObject(Wrapped):
    """
    A subclass of :class:`utils.Wrapped` providing informations on the wrapped type's instances' :

        - attribute schema - :meth:`default_schema`
        - attribute access - :meth:`setattr` and :meth:`getattr`
        - creation of new instances - :meth:`new`
    """

    extra_schema = {}
    """dict. ``{<attribute_name>: <attribute_type>}``. Allows to update the default schema, see :meth:`get_schema`."""

    include = []
    """list. The list of attributes to include in the schema see, :meth:`get_schema`."""

    exclude = []
    """list. The list of attributes to exclude from the schema see, :meth:`get_schema`."""
    
    def __new__(cls, *args, **kwargs):
        return cls.new(**kwargs)

    @classmethod
    def get_class(cls, key):
        """
        Returns the class of attribute `key`, as found from the schema, see :meth:`get_schema`.
        """
        schema = cls.get_schema()
        if key in schema:
            return schema[key]
        else:
            raise KeyError("'%s' not in schema" % key)
    
    @classmethod
    def get_schema(cls):
        """
        Returns the full schema ``{<attribute_name>: <attribute_type>}`` of an instance, taking into account (respectively) : `default_schema`, `extra_schema`, `include` and `exclude`.
        """
        schema = cls.default_schema()
        schema.update(cls.extra_schema)
        if cls.include:
            [schema.setdefault(k, NotImplemented) for k in cls.include]
            [schema.pop(k) for k in schema.keys() if k not in cls.include]
        if cls.exclude:
            [schema.pop(k, None) for k in cls.exclude]
        for key, cls in schema.iteritems():
            schema[key] = cls
        return schema

    @classmethod
    def default_schema(cls):
        """
        Returns the schema - known a priori - of an instance. Must return a dictionary with the format ``{<attribute_name>: <attribute_type>}``. 
        """
        return {}

    @classmethod
    def setattr(cls, instance, name, value):
        """
        Sets the attribute `name` on `instance`, with value `value`. If the calling :class:`WrappedObject` has a method `set_<name>`, this method will be used to set the attribute.
        """
        if hasattr(cls, 'set_%s' % name):
            getattr(cls, 'set_%s' % name)(instance, value)
        else:
            setattr(instance, name, value)

    @classmethod
    def getattr(cls, instance, name):
        """
        Gets the attribute `name` from `instance`. If the calling :class:`WrappedObject` has a method `get_<name>`, this method will be used to get the attribute.
        """
        if hasattr(cls, 'get_%s' % name):
            return getattr(cls, 'get_%s' % name)(instance)
        else:
            return getattr(instance, name)

    @classmethod
    def new(cls, **kwargs):
        """
        Creates and returns a new instance of the wrapped type.
        """
        return (cls.factory or cls.klass)(**kwargs)


class WrappedContainer(Wrapped):
    """
    A subclass of :class:`utils.Wrapped` providing informations on a container type.
    """

    value_type = NotImplemented
    """type. The type of value contained."""

    @classmethod
    def get_class(cls, key):
        return cls.value_type

    @classmethod
    def __superclasshook__(cls, C):
        # this allows to implement the following behaviour :
        # >>> Wrapped.issubclass(ListOfStr, ListOfBaseString)
        # True
        if super(WrappedContainer, cls).__superclasshook__(C):
            if issubclass(C, WrappedContainer):
                return Wrapped.issubclass(cls.value_type, C.value_type)
            else:
                return True
        else:
            return False


# Mixins for DivideAndConquerCast
#========================================
class CastItems(object):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_output`.
    """

    key_to_cast = Setting(default={})
    """dict. ``{<key>: <cast>}``. Maps a key with the cast to use."""

    value_cast = Setting()
    """Cast. The cast to use on all values."""

    key_cast = Setting()
    """Cast. The cast to use on all keys."""

    def iter_output(self, items_iter):
        """
        Casts each item. The cast is looked-up for in the following order :

            #. setting :attr:`key_to_cast`
            #. setting :attr:`value_cast`
            #. finally, using :meth:`any2any.base.Cast.cast_for`
        """
        for key, value in items_iter:
            if self.strip_item(key, value): continue
            cast = self.cast_for_item(key, value)
            if self.key_cast: key = self.key_cast(key)
            yield key, cast(value)

    def get_item_mm(self, key, value):
        # Returns the metamorphosis `mm` to apply on item `key`, `value`.
        from_ = self.get_item_from(key)
        to = self.get_item_to(key)
        # If NotImplemented, we make guesses
        if from_ == NotImplemented:
            from_ = type(value)
        if to == NotImplemented:
            return Mm(from_=from_, to_any=object)
        return Mm(from_, to)

    def cast_for_item(self, key, value):
        # Returns the cast to use for item `key`, `value`.
        # The lookup order is the following :
        #   1. setting `key_to_cast`
        #   2. setting `value_cast`
        #   3. finally, the method gets the metamorphosis to apply on the item
        #       and a suitable cast by calling `Cast.cast_for`.
        self.log('Item %s' % key)
        mm = self.get_item_mm(key, value)
        # try to get cast with the per-key map
        if key in self.key_to_cast:
            cast = self.key_to_cast.get(key)
            cast = self.build_customized(cast, mm)
        elif self.value_cast:
            cast = self.value_cast
            cast = self.build_customized(cast, mm)
        # otherwise try to get it by getting item's `mm` and calling `cast_for`.
        else:
            cast = self.cast_for(mm)
        return cast

    def strip_item(self, key, value):
        """
        Override for use. If `True` is returned, the item ``<key>, <value>`` will be stripped from the output.
        """
        return False


class FromMapping(object):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_input`.
    
    Note that `FromMapping` is more clever when `from_` is a subclass of :class:`WrappedContainer`.
    """

    from_wrapped = Setting(default=WrappedContainer)

    def get_item_from(self, key):
        return self.from_.get_class(key)

    def iter_input(self, inpt):
        return inpt.iteritems()


class ToMapping(object):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.build_output`.
    
    Note that `ToMapping` is more clever when `to` is a subclass of :class:`WrappedContainer`.
    """

    to_wrapped = Setting(default=WrappedContainer)

    def get_item_to(self, key):
        return self.to.get_class(key)

    def build_output(self, items_iter):
        return self.to(items_iter)


class FromIterable(object):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_input`.
    
    Note that `FromIterable` is more clever when `from_` is a subclass of :class:`WrappedContainer`.
    """

    from_wrapped = Setting(default=WrappedContainer)

    def get_item_from(self, key):
        return self.from_.get_class(key)

    def iter_input(self, inpt):
        return enumerate(inpt)


class ToIterable(object):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.build_output`.
    
    Note that `ToIterable` is more clever when `to` is a subclass of :class:`WrappedContainer`.
    """

    to_wrapped = Setting(default=WrappedContainer)

    def get_item_to(self, key):
        return self.to.get_class(key)

    def build_output(self, items_iter):
        return self.to((value for key, value in items_iter))


class FromObject(object):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_input`.
    
    Note that `FromObject` is more clever when `from_` is a subclass of :class:`WrappedObject`.
    """

    from_wrapped = Setting(default=WrappedObject)

    def get_item_from(self, key):
        return self.from_.get_class(key)

    def iter_input(self, inpt):
        for name in self.from_.get_schema().keys():
            yield name, self.from_.getattr(inpt, name)


class ToObject(object):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.build_output`.
    
    Note that `ToObject` is more clever when `to` is a subclass of :class:`WrappedObject`.
    """

    to_wrapped = Setting(default=WrappedObject)

    def get_item_to(self, key):
        return self.to.get_class(key)

    def build_output(self, items_iter):
        return self.to(**dict(items_iter))

