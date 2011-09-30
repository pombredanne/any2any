# -*- coding: utf-8 -*-
import copy
try:
    import abc
except ImportError:
    from compat import abc
from base import Cast, Setting, CopiedSetting
from utils import closest_parent, TypeWrap, Mm, memoize

# Abstract DivideAndConquerCast
#======================================

class DivideAndConquerCast(Cast):
    """
    Abstract base cast for metamorphosing `from` and `to` any complex object or container.

    In order to achieve casting, this class uses a "divide and conquer" strategy :

        1. `Divide into sub-problems` - :meth:`DivideAndConquerCast.iter_input`
        2. `Solve sub-problems` - :meth:`DivideAndConquerCast.iter_output`
        3. `Combine solutions` - :meth:`DivideAndConquerCast.build_output`
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
        Returns:
            type or NotImplemented. The type of the value associated with `key` if it is known "a priori" (without knowing the input), or `NotImplemented` to let the cast guess.
        """
        return NotImplemented

    def get_item_to(self, key):
        """
        Returns:
            type or NotImplemented. Type the value associated with `key` must be casted to, if it is known `a priori` (without knowing the input), or NotImplemented.
        """
        return NotImplemented

    def call(self, inpt):
        iter_input = self.iter_input(inpt)
        iter_ouput = self.iter_output(iter_input)
        return self.build_output(iter_ouput)

# Type wraps
#======================================
class ObjectWrap(TypeWrap):
    #TODO: for looking-up best mm, when several superclasses in ObjectWrap, when several Mm match, choose the best one.
    # ex : Journal, ForeignKey
    #TODO: Wrap(atype) doesn't match to Mm(atype), but Mm(from_any=atype) -> change Wrap.__eq__
    #TODO: if Mm(aspztype) matches Mm(atype): cast, then cast's from_ will be overriden, along with its schema.
    #TODO: put attribute access in there
    #TODO: Mm, from_ and to maybe don't make sense anymore... only from_any and to_any
    #TODO: document

    defaults = dict(
        extra_schema = {},
        include = [],
        exclude = [],
        factory = None,
    )

    def get_class(self, key):
        schema = self.get_schema()
        if key in schema:
            return schema[key]
        else:
            raise KeyError("'%s' not in schema" % key)
    
    def get_schema(self):
        schema = self.default_schema()
        schema.update(self.extra_schema)
        if self.include:
            [schema.setdefault(k, NotImplemented) for k in self.include]
            [schema.pop(k) for k in schema.keys() if k not in self.include]
        if self.exclude:
            [schema.pop(k, None) for k in self.exclude]
        for key, cls in schema.iteritems():
            # If NotImplemented, we make a guess.
            if cls == NotImplemented:
                cls = self.guess_class(key)
            schema[key] = cls
        return schema

    def guess_class(self, key):
        """
        """
        return NotImplemented

    def default_schema(self):
        """
        """
        return {}

    def setattr(self, obj, name, value):
        setattr(obj, name, value)

    def getattr(self, obj, name):
        return getattr(obj, name)

    def __call__(self, *args, **kwargs):
        return self.new_object(*args, **kwargs)

    def new_object(self, *args, **kwargs):
        return self.factory(*args, **kwargs), kwargs.keys()

class ContainerWrap(TypeWrap):
    #TODO: document

    defaults = dict(
        value_type = NotImplemented,
        factory = None,
    )

    def __superclasshook__(self, C):
        if super(ContainerWrap, self).__superclasshook__(C):
            if isinstance(C, ContainerWrap):
                return TypeWrap.issubclass(self.value_type, C.value_type)
            else:
                return True
        else:
            return False

    def __repr__(self):
        return 'Wrapped%s%s' % (self.base.__name__.capitalize(),
        '' if self.value_type == NotImplemented else 'Of%s' % self.value_type)

# Mixins
#========================================

class CastItems(DivideAndConquerCast):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_output`.
    """

    key_to_cast = Setting(default={})
    """key_to_cast(dict). ``{<key>: <cast>}``. Maps a key with the cast to use."""
    value_cast = CopiedSetting()
    """value_cast(Cast). The cast to use on all values."""
    key_cast = CopiedSetting()
    """key_cast(Cast). The cast to use on all keys."""

    def iter_output(self, items_iter):
        for key, value in items_iter:
            if self.strip_item(key, value): continue
            if self.key_cast: key = self.key_cast(key)
            cast = self.cast_for_item(key, value)
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
            cast = copy.copy(cast)
            cast.customize(**self.settings)
            cast.customize_mm(mm)
        elif self.value_cast:
            cast = self.value_cast
            cast.customize(**self.settings)
            cast.customize_mm(mm)
        # otherwise try to get it by getting item's `mm` and calling `cast_for`.
        else:
            cast = self.cast_for(mm)
        cast._depth = self._depth + 1
        return cast

    def strip_item(self, key, value):
        """
        Override for use. If `True` is returned, the item ``<key>, <value>`` will be stripped from the output.
        """
        return False

class FromMapping(DivideAndConquerCast):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_input`.
    :meth:`get_item_from` can guess the type of values if `from_` is a :class:`ContainerWrap`.    
    """

    from_wrap = Setting(default=ContainerWrap)

    def get_item_from(self, key):
        return self.from_.value_type

    def iter_input(self, inpt):
        return inpt.iteritems()

class ToMapping(DivideAndConquerCast):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.build_output`.
    :meth:`get_item_to` can guess the type of values if `to` is a :class:`ContainerWrap`.    
    """

    to_wrap = Setting(default=ContainerWrap)

    def get_item_to(self, key):
        return self.to.value_type

    def build_output(self, items_iter):
        return self.to(items_iter)

class FromIterable(DivideAndConquerCast):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_input`.
    :meth:`get_item_from` can guess the type of values if `from_` is a :class:`ContainerWrap`.    
    """

    from_wrap = Setting(default=ContainerWrap)

    def get_item_from(self, key):
        return self.from_.value_type

    def iter_input(self, inpt):
        return enumerate(inpt)

class ToIterable(DivideAndConquerCast):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.build_output`.
    :meth:`get_item_to` can guess the type of values if `to` is a :class:`ContainerWrap`.
    """

    to_wrap = Setting(default=ContainerWrap)

    def get_item_to(self, key):
        return self.to.value_type

    def build_output(self, items_iter):
        return self.to((value for key, value in items_iter))

class FromObject(DivideAndConquerCast):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.iter_input`.
    :meth:`get_item_from` can guess the type of values if `from` is an :class:`ObjectWrap`.    
    """

    from_wrap = Setting(default=ObjectWrap)

    def get_item_from(self, key):
        return self.from_.get_class(key)

    def iter_input(self, inpt):
        for name in self.from_.get_schema().keys():
            yield name, self.from_.getattr(inpt, name)

class ToObject(DivideAndConquerCast):
    """
    Mixin for :class:`DivideAndConquerCast`. Implements :meth:`DivideAndConquerCast.build_output`.
    :meth:`get_item_to` can guess the type of values if `to` is a :class:`ObjectWrap`.
    """

    to_wrap = Setting(default=ObjectWrap)

    def get_item_to(self, key):
        return self.to.get_class(key)

    def build_output(self, items_iter):
        return self.to(**items)

