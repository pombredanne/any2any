"""
..
    >>> import os, sys
    >>> sys.path.append(os.path.abspath('../..'))
    >>> from spiteat.base import *

.. currentmodule:: spiteat.base

Getting a serializer for a given class
----------------------------------------

To get a serializer for a class use the method :func:`Cast.cast_for` :

    >>> cast = Cast()
    >>> class Dumb(object): pass
    >>> dumb_cast = cast.cast_for((Dumb, object))
    >>> isinstance(dumb_cast, Identity)
    True
    >>> obj_cast = cast.cast_for((object, object))
    >>> isinstance(obj_cast, Identity)
    True
    >>> list_cast = cast.cast_for((list, list))
    >>> isinstance(list_cast, SequenceCast)
    True

You can also pass a second argument in order to get a customized serializer :

    >>> custom_cast = cast.cast_for((list, list), {'conversion': (object, object)})
    >>> custom_cast.conversion == (object, object)
    True

Defining settings of a serializer
-----------------------------------

Configuring the behaviour of :meth:`Cast.cast_for`
--------------------------------------------------

Of course, there wouldn't be much fun if you couldn't configure what serializer :meth:`Cast.cast_for` should pick for a given class. There is actually two ways to do this.

You can set a serializer class as global default for a Python class, using the attribute :attr:`Cast.conversions` :

    >>> class DumbCast(Cast): pass
    >>> dumb_cast = DumbCast()
    >>> register(dumb_cast, conversions=[(Dumb, object)])
    >>> cast = Cast()
    >>> isinstance(cast.cast_for((Dumb, object)), DumbCast)
    True

..
    Testing that default for 'object' is still the same :
    >>> isinstance(cast.cast_for((object, object)), Identity)
    True

Second solution is to change the setting :attr:`Cast.Settings.cast_map`. This won't modify global defaults, but rather override them on the serializer level :
 
    >>> class MyCast(Cast): pass
    >>> cast = Cast()
    >>> mycast = MyCast()
    >>> custom_cast = Cast(cast_map={(int, object): mycast})
    >>> isinstance(custom_cast.cast_for((int, object)), MyCast)
    True
    >>> isinstance(cast.cast_for((int, object)), Identity) #Only the map of custom_cast is affected
    True
    >>> isinstance(custom_cast.cast_for((Dumb, object)), DumbCast) #However the global defaults still work 
    True

Validators
------------

    >>> int_cast = Identity(conversion=(int, object))
    >>> int_cast(1)
    1
    >>> int_cast('some string')#doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ValidationError: message

   

Debugging
-----------

SpitEat logs all the calls to :meth:`spit` or :meth:`eat` to help debugging. By default, the logger's handler is :class:`NullHandler`, so no message is logged. To activate SpitEat's logging, just add any handler to :attr:`logger`, and set the logger's level to :attr:`DEBUG`.

For example, here we create a temporary file, and a :class:`StreamHandler` that will write to this file :

    >>> from tempfile import TemporaryFile
    >>> import logging
    >>> fd = TemporaryFile()
    >>> h = logging.StreamHandler(fd)

Then we set the handler's formatter (optional), add our handler to **SpitEat**'s logger and set the logging level to :attr:`DEBUG`.

    >>> from spiteat.base import logger, formatter
    >>> h.setFormatter(formatter)
    >>> logger.addHandler(h)
    >>> logger.setLevel(logging.DEBUG)

Finally, after a few spit/eat operations, we can chack that the logging worked : 

    >>> cast = Identity()
    >>> spitted = cast(1)
    >>> eat = cast(1)
    >>> fd.seek(0)
    >>> print fd.read()
    spiteat.base.Identity((<type 'object'>, <type 'object'>)) <= 1
    spiteat.base.Identity((<type 'object'>, <type 'object'>)) => 1
    <BLANKLINE>
    spiteat.base.Identity((<type 'object'>, <type 'object'>)) <= 1
    spiteat.base.Identity((<type 'object'>, <type 'object'>)) => 1
    <BLANKLINE>
    <BLANKLINE>

..
    >>> logger.removeHandler(h)
"""

if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.REPORT_ONLY_FIRST_FAILURE)
