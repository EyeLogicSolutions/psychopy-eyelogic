#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).
"""Utilities for extending PsychoPy with plugins."""

from __future__ import absolute_import
__all__ = ['loadPlugin', 'listPlugins', 'computeChecksum']

import sys
import inspect
import collections
import hashlib
import importlib
import pkg_resources

from psychopy import logging
import psychopy.experiment.components as components

# Keep track of plugins that have been loaded. Keys are plugin names and values
# are their entry point mappings.
_plugins_ = collections.OrderedDict()  # use OrderedDict for Py2 compatibility

# Allowed subclasses for each group, this can be used to enforce what kinds of
# objects are allowed in a given module's namespace. For instance, to restrict
# plugins from creating classes in `psychopy.visual` that are not subclasses of
# `psychopy.visual.BaseVisualStim` use the following line:
#_allowed_subclasses_ = {'psychopy.visual': ('psychopy.visual.BaseVisualStim',)}
_allowed_subclasses_ = {}


def resolveObjectFromName(name, basename=None, resolve=True, error=True):
    """Get an object within a module's namespace using a fully-qualified or
    relative dotted name.

    This function is mainly used to get objects associated with entry point
    groups, so entry points can be assigned to them. It traverses through
    objects in `name` until it reaches the end, then returns a reference to
    that object. Other uses of this function is to import objects by using their
    string names and check if an attribute is defined at `name`.

    Parameters
    ----------
    name : str
        Fully-qualified or relative name to the object (eg.
        `psychopy.visual.Window` or `.Window`). If name is relative, `basename`
        must be specified.
    basename : str, ModuleType or None
        If `name` is relative (starts with '.'), `basename` should be the
        `__name__` of the module or reference to the module itself `name` is
        relative to. Leave `None` if `name` is already fully qualified.
    resolve : bool
        If `resolve=True`, any name encountered along the way that isn't present
        will be assumed to be a module and imported. This guarantees the target
        object is fully-realized and reachable if the target is valid. If
        `False`, this function will will fail if the `name` is not reachable.
        This is used in cases where you just need to check if an object already
        exists.
    error : bool
        Raise an error if an object is not reachable. If `False`, this function
        will return `None` instead and suppress the error.

    Returns
    -------
    object
        Object referred to by the name. Returns `None` if the object is not
        reachable and `error=False`.

    Raises
    ------
    ModuleNotFoundError
        The base module the FQN is referring to has not been imported.
    NameError
        The provided name does not point to a valid object.
    ValueError
        A relative name was given to `name` but `basename` was not specified.

    Examples
    --------
    Get a reference to the `psychopy.visual.Window` class (will import `visual`
    in doing so)::

        Window = resolveObjectFromName('psychopy.visual.Window')

    Get the `Window` class if `name` is relative to `basename`::

        import psychopy.visual as visual
        Window = resolveObjectFromName('.Window', visual)

    Check if an object exists::

        Window = resolveObjectFromName(
            'psychopy.visual.Window',
            resolve=False,  # False since we don't want to import anything
            error=False)  # suppress error, makes function return None

        if Window is None:
            print('Window has not been imported yet!')

    """
    # make sure a basename is given if relative
    if name.startswith('.') and basename is None:
        raise ValueError('`name` specifies a relative name but `basename` is '
                         'not specified.')

    # if basename is a module object
    if inspect.ismodule(basename):
        basename = basename.__name__

    # get fqn and split
    fqn = (basename + name if basename is not None else name).split(".")

    # get the object the fqn refers to
    try:
        objref = sys.modules[fqn[0]]  # base name
    except KeyError:
        raise ModuleNotFoundError(
            'Base module cannot be found, has it been imported yet?')

    # walk through the FQN to get the object it refers to
    path = fqn[0]
    for attr in fqn[1:]:
        path += '.' + attr
        if not hasattr(objref, attr):
            # try importing the module
            if resolve:
                try:
                    importlib.import_module(path)
                except ImportError:
                    if not error:  # return if suppressing error
                        return None
                    raise NameError(
                        "Specified `name` does not reference a valid object or "
                        "is unreachable.")
            else:
                if not error:  # return None if we want to suppress errors
                    return None
                raise NameError(
                    "Specified `name` does not reference a valid object or is "
                    "unreachable.")

        objref = getattr(objref, attr)

    return objref


def computeChecksum(fpath, method='sha256'):
    """Compute the checksum hash/key for a given package.

    Authors of PsychoPy plugins can use this function to compute a checksum
    hash and users can use it to check the integrity of their packages.

    Parameters
    ----------
    fpath : str
        Path to the plugin package or file.
    method : str
        Hashing method to use, values are 'md5' or 'sha256'. Default is
        'sha256'.

    Returns
    -------
    str
        Checksum hash digested to hexadecimal format.

    Examples
    --------
    Compute a checksum for a package and write it to a file::

        with open('checksum.txt', 'w') as f:
            f.write(computeChecksum(
                '/path/to/plugin/psychopy_plugin-1.0-py3.6.egg'))

    """
    methodObj = {'md5': hashlib.md5,
                 'sha256': hashlib.sha256}

    hashobj = methodObj[method]()
    with open(fpath, "rb") as f:
        chunk = f.read(4096)
        while chunk != b"":
            chunk = f.read(4096)
            hashobj.update(chunk)

    return hashobj.hexdigest()


def listPlugins(onlyLoaded=False):
    """Get a list of installed or loaded PsychoPy plugins.

    This function searches for potential plugin packages installed or loaded.
    When searching for installed plugin packages, only those the names of those
    which advertise entry points specifically for PsychoPy, the version of
    Python its currently running on, and operating system are returned.

    Parameters
    ----------
    onlyLoaded : bool
        If `False`, this function will return all installed packages which can
        be potentially loaded as plugins, regardless if they have been already
        loaded. If `True`, the returned values will only be names of plugins
        that have been successfully loaded previously in this session by
        `loadPlugin`. They will appear in the order of which they were loaded.

    Returns
    -------
    list
        Names of PsychoPy related plugins as strings. You can load all installed
        plugins by passing list elements to `loadPlugin`.

    Examples
    --------
    Load all plugins installed on the system into the current session (assumes
    all plugins don't require any additional arguments passed to them)::

        for plugin in plugins.listPlugins():
            plugins.loadPlugin(plugin)

    If certain plugins take arguments, you can do this give specific arguments
    when loading all plugins::

        pluginArgs = {'some-plugin': (('someArg',), {'setup': True, 'spam': 10})}
        for plugin in plugins.listPlugins():
            try:
                args, kwargs = pluginArgs[plugin]
                plugins.loadPlugin(plugin, *args, **kwargs)
            except KeyError:
                plugins.loadPlugin(plugin)

    Check if a plugin package named `plugin-test` is installed on the system and
    has entry points into PsychoPy::

        if 'plugin-test' in plugins.listPlugins():
            print("Plugin installed!")

    """
    if onlyLoaded:  # only list plugins we have already loaded
        return list(_plugins_.keys())

    # find all packages with entry points defined
    pluginEnv = pkg_resources.Environment()  # supported by the platform
    dists, _ = pkg_resources.working_set.find_plugins(pluginEnv)

    installed = []
    for dist in dists:
        if any([i.startswith('psychopy') for i in dist.get_entry_map().keys()]):
            installed.append(dist.project_name)

    return installed


def loadPlugin(plugin, *args, **kwargs):
    """Load a plugin to extend PsychoPy.

    Plugins are packages which extend upon PsychoPy's existing functionality by
    dynamically importing code at runtime, without modifying the existing
    installation files. Plugins create or redefine objects into the namespaces
    of modules (eg. `psychopy.visual`) and unbound classes, allowing them to be
    used as if they were part of PsychoPy.

    Plugins are simply Python packages,`loadPlugin` will search for them in
    directories specified in `sys.path`. Only packages which define entry points
    in their metadata which pertain to PsychoPy can be loaded with this
    function. This function also permits passing optional arguments to a
    callable object in the plugin module to run any initialization routines
    prior to loading entry points.

    Parameters
    ----------
    plugin : str
        Name of the plugin package to load. This usually refers to the package
        or project name.
    *args, **kwargs
        Optional arguments and keyword arguments to pass to the plugin's
        `register` function.

    Returns
    -------
    bool
        `True` if the plugin has valid entry points and was loaded successfully.
        Also returns `True` if the plugin was already loaded by a previous
        `loadPlugin` call this session, this function will have no effect in
        this case. `False` is returned if the plugin defines no entry points
        specific to PsychoPy (a warning is logged).

    Raises
    ------
    NameError
        The plugin attempted to overwrite an entire extant module or modify
        `psychopy.plugins`. Also raised if the plugin module defines
        `__register__` but the specified object is not valid or present.
    TypeError
        Plugin defines `__register__` which specifies an object that is not
        callable.

    Warnings
    --------
    Make sure that plugins installed on your system are from reputable sources,
    as they may contain malware! PsychoPy is not responsible for undefined
    behaviour or bugs associated with the use of 3rd party plugins.

    See Also
    --------
    listPlugins : Search for and list installed or loaded plugins.

    Examples
    --------
    Load a plugin by specifying its package/project name::

        loadPlugin('psychopy-hardware-box')

    You can give arguments to this function which are passed on to the plugin::

        loadPlugin('psychopy-hardware-box', switchOn=True, baudrate=9600)

    You can use the value returned from `loadPlugin` to determine if the plugin
    is installed and supported by the platform::

        hasPlugin = loadPlugin('psychopy-hardware-box')
        if hasPlugin:
            # initialize objects which require the plugin here ...

    """
    global _plugins_
    if plugin in _plugins_.keys():
        return True  # already loaded, return True

    # find all plugins installed on the system
    pluginEnv = pkg_resources.Environment()  # supported by the platform
    dists, _ = pkg_resources.working_set.find_plugins(pluginEnv)

    # check if the plugin is in the distribution list
    try:
        pluginDist = dists[[dist.project_name for dist in dists].index(plugin)]
    except ValueError:
        logging.warning(
            'Package `{}` does not appear to be a valid plugin. '
            'Skipping.'.format(plugin))

        return False

    # get entry point map and check if there are any for PsychoPy
    entryMap = pluginDist.get_entry_map()
    if not any([i.startswith('psychopy') for i in entryMap.keys()]):
        logging.warning(
            'Specified package `{}` defines no entry points for PsychoPy. '
            'Skipping.'.format(pluginDist.project_name))

        return False  # can't do anything more here, so return

    # go over entry points, looking for objects explicitly for psychopy
    for fqn, attrs in entryMap.items():
        if not fqn.startswith('psychopy'):
            continue

        # forbid plugins from modifying this module
        if fqn.startswith('psychopy.plugins') or \
                (fqn == 'psychopy' and 'plugins' in attrs):
            raise NameError(
                "Plugins declaring entry points into the `psychopy.plugins` "
                "module is forbidden.")

        # Special case where the group has entry points for builder components.
        # Note, this does not create any objects inside the namespace of that
        # module for now to maintain compatibility with the present system. In
        # the future, component classes may be loaded and assigned attributes
        # like any other plugin entry point.
        if fqn.startswith('psychopy.experiment.components'):
            for attr, ep in attrs.items():
                compModule = ep.load()
                # make sure that we only use modules to add builder components
                if not inspect.ismodule(compModule):
                    raise TypeError(
                        "Entry points into `psychopy.experiment.components` "
                        "must be modules.")

                _registerComponent(compModule)  # add the component

            continue

        # Get the object the fully-qualified name points to the group which the
        # plugin wants to modify.
        targObj = resolveObjectFromName(fqn)

        # if there are any sub-classes that are restricted
        if fqn in _allowed_subclasses_.keys():
            allowedTypes = \
                tuple([resolveObjectFromName(i) for i in _allowed_subclasses_[fqn]])
        else:
            allowedTypes = None

        # add and replace names with the plugin entry points
        for attr, ep in attrs.items():
            # Load the module the entry point belongs to, this happens
            # anyways when .load() is called, but we get to access it before
            # we start binding. If the module has already been loaded, don't
            # do this again.
            if ep.module_name not in sys.modules:
                # Do stuff before loading entry points here, any executable code
                # in the module will run to configure it.
                imp = importlib.import_module(ep.module_name)

                # call the register function, check if exists and valid
                if hasattr(imp, '__register__') and imp.__register__ is not None:
                    if isinstance(imp.__register__, str):
                        if hasattr(imp, imp.__register__):  # local to module
                            func = getattr(imp, imp.__register__)
                        else:  # could be a FQN?
                            func = resolveObjectFromName(imp.__register__)
                        # check if the reference object is callable
                        if not callable(func):
                            raise TypeError(
                                'Plugin module defines `__register__` but the '
                                'specified object is not a callable type.')
                    elif callable(imp.__register__):  # a function was supplied
                        func = imp.__register__
                    else:
                        raise TypeError(
                            'Plugin module defines `__register__` but is not '
                            '`str` or callable type.')

                    # call the register function with arguments
                    func(*args, **kwargs)

            # Ensure that we are not wholesale replacing an existing module.
            # We want plugins to be explicit about what they are changing.
            # This makes sure plugins play nice with each other, only
            # making changes to existing code where needed. However, plugins
            # are allowed to add new modules to the namespaces of existing
            # ones.
            if hasattr(targObj, attr):
                # handle what to do if an attribute exists already here ...
                if inspect.ismodule(getattr(targObj, attr)):
                    raise NameError(
                        "Plugin `{}` attempted to override module `{}`.".format(
                            plugin, fqn + '.' + attr))

            ep = ep.load()  # load the entry point

            # allow only adding classes that are of a particular subclass
            if allowedTypes is not None and inspect.isclass(ep):
                if not issubclass(ep, allowedTypes):
                    typestr = _allowed_subclasses_[fqn]
                    raise TypeError(
                        "Class had invalid subclass type for module `{}`. Must "
                        "be `{}`.".format(fqn, '`, `'.join(typestr)))

            # add the object to the module or unbound class
            setattr(targObj, attr, ep)
            logging.debug(
                "Assigning to entry point `{}` to `{}`.".format(
                    ep.__name__, fqn + '.' + attr))

            # --- handle special cases ---
            if fqn == 'psychopy.visual.backends':  # if window backend
                _registerWindowBackend(attr, ep)


    # retain information about the plugin's entry points, we will use this for
    # conflict resolution
    _plugins_[pluginDist.project_name] = entryMap

    return True


def _registerWindowBackend(attr, ep):
    """Make an entry point discoverable as a window backend. This allows it to
    be used by specifying `winType`. All window backends must be subclasses of
    `BaseBackend` and define a `winTypeName` attribute. The value of
    `winTypeName` will be used for selecting `winType`.

    Parameters
    ----------
    attr : str
        Attribute name the backend is being assigned in
        'psychopy.visual.backends'.
    ep : ModuleType of ClassType
        Entry point which defines an object with window backends. Can be a class
        or module. If a module, the module will be scanned for subclasses of
        `BaseBackend` and they will be added as backends.

    """
    # get reference to the backend class
    fqn = 'psychopy.visual.backends'
    backend = resolveObjectFromName(fqn, resolve=(fqn not in sys.modules))

    # if a module, scan it for valid backends
    foundBackends = {}
    if inspect.ismodule(ep):  # if the backend is a module
        for attrName in dir(ep):
            _attr = getattr(ep, attrName)
            if not inspect.isclass(_attr):  # skip if not class
                continue
            if not issubclass(_attr, backend._base.BaseBackend):  # not backend
                continue
            # check if the class defines a name for `winType`
            if not hasattr(_attr, 'winTypeName'):  # has no backend name
                continue
            # found something that can be a backend
            foundBackends[_attr.winTypeName] = '.' + attr + '.' + attrName
            logging.debug(
                "Registered window backend class `{}` for `winType={}`.".format(
                    foundBackends[_attr.winTypeName], _attr.winTypeName))
    elif inspect.isclass(ep):  # backend passed as a class
        if not issubclass(ep, backend._base.BaseBackend):
            return
        if not hasattr(ep, 'winTypeName'):
            return
        foundBackends[ep.winTypeName] = '.' + attr
        logging.debug(
            "Registered window backend class `{}` for `winType={}`.".format(
                foundBackends[ep.winTypeName], ep.winTypeName))

    backend.winTypes.update(foundBackends)  # update installed backends


def _registerComponent(module):
    """Register a PsychoPy builder component module.

    Parameters
    ----------
    module : ModuleType
        Module containing the builder component to register.

    """
    # give a default category
    if not hasattr(module, 'categories'):
        module.categories = ['Custom']

    # check if module contains a component
    for attrib in dir(module):
        # fetch the attribs that end with 'Component'
        if not attrib.endswith('omponent'):
            continue

        # name and reference to component class
        name = attrib
        cls = getattr(module, attrib)

        # check if subclass of component type
        if not issubclass(cls, components.BaseComponent):
            raise TypeError(
                'Component class `{}` is not subclass of `BaseComponent`.')

        components.pluginComponents[attrib] = getattr(module, attrib)

        # skip if this class was imported, not defined here
        if module.__name__ != components.pluginComponents[attrib].__module__:
            continue  # class was defined in different module

        if hasattr(module, 'tooltip'):
            components.tooltips[name] = module.tooltip

        if hasattr(module, 'iconFile'):
            components.iconFiles[name] = module.iconFile

        # assign the module categories to the Component
        if not hasattr(components.pluginComponents[attrib], 'categories'):
            components.pluginComponents[attrib].categories = ['Custom']
