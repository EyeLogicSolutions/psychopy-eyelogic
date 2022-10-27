#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2022 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).
"""Utilities for extending PsychoPy with plugins."""

__all__ = ['loadPlugin', 'listPlugins', 'computeChecksum', 'startUpPlugins',
           'pluginMetadata', 'pluginEntryPoints', 'scanPlugins',
           'requirePlugin', 'isPluginLoaded', 'isStartUpPlugin']

import json
import sys
import inspect
import collections
import hashlib
import importlib
from pathlib import Path

import pkg_resources
import requests
import wx

from psychopy import logging
from psychopy.app import utils
from psychopy.app.themes import icons, handlers
from psychopy.preferences import prefs
from psychopy.localization import _translate
import psychopy.experiment.components as components
from psychopy.tools import stringtools as strtools
import subprocess as sp

# Keep track of plugins that have been loaded. Keys are plugin names and values
# are their entry point mappings.
_loaded_plugins_ = collections.OrderedDict()  # use OrderedDict for Py2 compatibility

# Entry points for all plugins installed on the system, this is populated by
# calling `scanPlugins`. We are caching entry points to avoid having to rescan
# packages for them.
_installed_plugins_ = collections.OrderedDict()

# Keep track of plugins that failed to load here
_failed_plugins_ = []


def resolveObjectFromName(name, basename=None, resolve=True, error=True):
    """Get an object within a module's namespace using a fully-qualified or
    relative dotted name.

    This function is mainly used to get objects associated with entry point
    groups, so entry points can be assigned to them. It traverses through
    objects along `name` until it reaches the end, then returns a reference to
    that object.

    You can also use this function to dynamically import modules and fully
    realize target names without needing to call ``import`` on intermediate
    modules. For instance, by calling the following::

        Window = resolveObjectFromName('psychopy.visual.Window')

    The function will first import `psychopy.visual` then get a reference to the
    unbound `Window` class within it and assign it to `Window`.

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
        `False`, this function will fail if the `name` is not reachable and
        raise an error or return `None` if `error=False`.
    error : bool
        Raise an error if an object is not reachable. If `False`, this function
        will return `None` instead and suppress the error. This may be useful in
        cases where having access to the target object is a "soft" requirement
        and the program can still operate without it.

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


def computeChecksum(fpath, method='sha256', writeOut=None):
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
    writeOut : str
        Path to a text file to write checksum data to. If the file exists, the
        data will be written as a line at the end of the file.

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

    checksumStr = hashobj.hexdigest()

    if writeOut is not None:
        with open(writeOut, 'a') as f:
            f.write('\n' + checksumStr)

    return checksumStr


class PluginInfo:
    """
    Minimal class to store info about a plugin.

    Parameters
    ----------
    source : str
        Is this a community plugin ("community") or one curated by us ("curated")?
    pipname : str
        Name of plugin on pip, e.g. "psychopy-legacy"
    name : str
        Plugin name for display, e.g. "Psychopy Legacy"
    icon : wx.Bitmap, path or None
        Icon for the plugin, if any (if None, will use blank bitmap)
    description : str
        Description of the plugin
    installed : bool or None
        Whether or not the plugin in installed on this system
    active : bool
        Whether or not the plug is enabled on this system (if not installed, will always be False)
    """
    def __init__(self, source,
                 pipname, name="",
                 author=None, homepage="", docs="", repo="",
                 keywords=None,
                 icon=None, description=""):
        self.source = source
        self.pipname = pipname
        self.name = name
        self.author = author
        self.homepage = homepage
        self.docs = docs
        self.repo = repo
        self.icon = icon
        self.description = description
        self.keywords = keywords or []

    def __repr__(self):
        return f"<psychopy.plugins.PluginInfo: {self.name} [{self.pipname}] by {self.author} ({self.source})>"

    def __eq__(self, other):
        if isinstance(other, PluginInfo):
            return self.pipname == other.pipname
        else:
            return self.pipname == str(other)

    @property
    def icon(self):
        if hasattr(self, "_icon"):
            return self._icon

    @icon.setter
    def icon(self, value):
        self._requestedIcon = value
        self._icon = utils.ImageData(value)

    @property
    def active(self):
        """
        Is this plugin active? If so, it is loaded when the app starts. Otherwise, it remains installed but is not
        loaded.
        """
        return isStartUpPlugin(self.pipname)

    @active.setter
    def active(self, value):
        if value is None:
            # Setting active as None skips the whole process - useful for avoiding recursion
            return

        if value:
            # If active, add to list of startup plugins
            startUpPlugins(self.pipname, add=True)
        else:
            # If active and changed to inactive, remove from list of startup plugins
            current = listPlugins(which='startup')
            if self.pipname in current:
                current.remove(self.pipname)
            startUpPlugins(current, add=False)

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

    @property
    def installed(self):
        current = listPlugins(which='all')
        return self.pipname in current

    @installed.setter
    def installed(self, value):
        if value is None:
            # Setting installed as None skips the whole process - useful for avoiding recursion
            return
        # Get action string from value
        if value:
            act = "install"
        else:
            act = "uninstall"
        # Install/uninstall
        emts = [sys.executable, "-m", "pip", act, self.pipname]
        cmd = " ".join(emts)
        output = sp.Popen(cmd,
                          stdout=sp.PIPE,
                          stderr=sp.PIPE,
                          shell=True,
                          universal_newlines=True)
        stdout, stderr = output.communicate()
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        # Throw up error dlg if needed
        if stderr:
            dlg = InstallErrorDlg(
                cmd=" ".join(emts[2:]),
                stdout=stdout,
                stderr=stderr
            )
            dlg.ShowModal()

    def install(self):
        self.installed = True

    def uninstall(self):
        self.installed = False

    @property
    def author(self):
        if hasattr(self, "_author"):
            return self._author

    @author.setter
    def author(self, value):
        if isinstance(value, AuthorInfo):
            # If given an AuthorInfo, use it directly
            self._author = value
        elif isinstance(value, dict):
            # If given a dict, make an AuthorInfo from it
            self._author = AuthorInfo(**value)
        else:
            # Otherwise, assume no author
            self._author = AuthorInfo()


class AuthorInfo:
    def __init__(self,
                 name="",
                 email="",
                 github="",
                 avatar=None):
        self.name = name
        self.email = email
        self.github = github
        self.avatar = avatar

    @property
    def avatar(self):
        if hasattr(self, "_avatar"):
            return self._avatar

    @avatar.setter
    def avatar(self, value):
        self._requestedAvatar = value
        self._avatar = utils.ImageData(value)

    def __repr__(self):
        return f"<psychopy.plugins.AuthorInfo: {self.name} (@{self.github}, {self.email})>"


class InstallErrorDlg(wx.Dialog, handlers.ThemeMixin):
    def __init__(self, cmd="", stdout="", stderr=""):
        from psychopy.app.themes import fonts

        wx.Dialog.__init__(
            self, None,
            size=(480, 620),
            title=_translate("Plugin install error"),
            style=wx.RESIZE_BORDER | wx.CLOSE_BOX | wx.CAPTION
        )
        # Setup sizer
        self.border = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.border)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.border.Add(self.sizer, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)
        # Create title sizer
        self.title = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.title, border=6, flag=wx.ALL | wx.EXPAND)
        # Create icon
        self.icon = wx.StaticBitmap(
            self, size=(32, 32),
            bitmap=icons.ButtonIcon(stem="stop", size=32).bitmap
        )
        self.title.Add(self.icon, border=6, flag=wx.ALL | wx.EXPAND)
        # Create title
        self.titleLbl = wx.StaticText(self, label=_translate("Plugin could not be installed."))
        self.titleLbl.SetFont(fonts.appTheme['h3'].obj)
        self.title.Add(self.titleLbl, proportion=1, border=6, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        # Show what we tried
        self.inLbl = wx.StaticText(self, label=_translate("We tried:"))
        self.sizer.Add(self.inLbl, border=6, flag=wx.ALL | wx.EXPAND)
        self.inCtrl = wx.TextCtrl(self, value=cmd, style=wx.TE_READONLY)
        self.inCtrl.SetBackgroundColour("white")
        self.inCtrl.SetFont(fonts.appTheme['code'].obj)
        self.sizer.Add(self.inCtrl, border=6, flag=wx.ALL | wx.EXPAND)
        # Show what we got
        self.outLbl = wx.StaticText(self, label=_translate("We got:"))
        self.sizer.Add(self.outLbl, border=6, flag=wx.ALL | wx.EXPAND)
        self.outCtrl = wx.TextCtrl(self, value=f"{stdout}\n{stderr}",
                                   size=(-1, 620), style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.outCtrl.SetFont(fonts.appTheme['code'].obj)
        self.sizer.Add(self.outCtrl, proportion=1, border=6, flag=wx.ALL | wx.EXPAND)

        # Make buttons
        self.btns = self.CreateStdDialogButtonSizer(flags=wx.OK)
        self.border.Add(self.btns, border=6, flag=wx.ALIGN_RIGHT | wx.ALL)

        self.Layout()
        self._applyAppTheme()

    def ShowModal(self):
        # Make error noise
        wx.Bell()
        # Show as normal
        wx.Dialog.ShowModal(self)


def getAllPluginDetails():
    """
    Placeholder function - returns an example list of objects with desired structure.
    """
    # Request plugin info list from server
    resp = requests.get("https://psychopy.org/plugins.json")
    # If 404, return None so the interface can handle this nicely rather than an unhandled error
    if resp.status_code == 404:
        return
    # Create PluginInfo objects from info list
    objs = []
    for info in resp.json():
        objs.append(
            PluginInfo(**info)
        )
    # Add info objects for local plugins which aren't found online
    localPlugins = listPlugins(which='all')
    for name in localPlugins:
        # Check whether plugin is accounted for
        if name not in objs:
            # If not, get its metadata
            data = pluginMetadata(name)
            # Create best representation we can from metadata
            author = AuthorInfo(
                name=data['Author'],
                email=data['Author-email']
            )
            info = PluginInfo(
                source="unknown",
                pipname=name, name=name,
                author=author,
                homepage=data['Home-page'],
                keywords=data['Keywords'],
                description=data['Summary']
            )
            # Add to list
            objs.append(info)

    return objs


def scanPlugins():
    """Scan the system for installed plugins.

    This function scans installed packages for the current Python environment
    and looks for ones that specify PsychoPy entry points in their metadata.
    Afterwards, you can call :func:`listPlugins()` to list them and
    `loadPlugin()` to load them into the current session. This function is
    called automatically when PsychoPy starts, so you do not need to call this
    unless packages have been added since the session began.

    Returns
    -------
    int
        Number of plugins found during the scan. Calling `listPlugins()` will
        return the names of the found plugins.

    """
    global _installed_plugins_
    _installed_plugins_ = {}  # clear installed plugins

    # find all packages with entry points defined
    pluginEnv = pkg_resources.Environment()  # supported by the platform
    dists, _ = pkg_resources.working_set.find_plugins(pluginEnv)

    for dist in dists:
        entryMap = dist.get_entry_map()
        if any([i.startswith('psychopy') for i in entryMap.keys()]):
            logging.debug('Found plugin `{}` at location `{}`.'.format(
                dist.project_name, dist.location))
            _installed_plugins_[dist.project_name] = entryMap

    return len(_installed_plugins_)


def listPlugins(which='all'):
    """Get a list of installed or loaded PsychoPy plugins.

    This function lists either all potential plugin packages installed on the
    system, those registered to be loaded automatically when PsychoPy starts, or
    those that have been previously loaded successfully this session.

    Parameters
    ----------
    which : str
        Category to list plugins. If 'all', all plugins installed on the system
        will be listed, whether they have been loaded or not. If 'loaded', only
        plugins that have been previously loaded successfully this session will
        be listed. If 'startup', plugins registered to be loaded when a PsychoPy
        session starts will be listed, whether or not they have been loaded this
        session. If 'unloaded', plugins that have not been loaded but are
        installed will be listed. If 'failed', returns a list of plugin names
        that attempted to load this session but failed for some reason.

    Returns
    -------
    list
        Names of PsychoPy related plugins as strings. You can load all installed
        plugins by passing list elements to `loadPlugin`.

    See Also
    --------
    loadPlugin : Load a plugin into the current session.

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

    Check if all plugins registered to be loaded on startup are currently
    active::

        if not all([p in listPlugins('loaded') for p in listPlugins('startup')]):
            print('Please restart your PsychoPy session for plugins to take effect.')

    """
    if which not in ('all', 'startup', 'loaded', 'unloaded', 'failed'):
        raise ValueError("Invalid value specified to argument `which`.")

    if which == 'loaded':  # only list plugins we have already loaded
        return list(_loaded_plugins_.keys())
    elif which == 'startup':
        return list(prefs.general['startUpPlugins'])  # copy this
    elif which == 'unloaded':
        return [p for p in listPlugins('all') if p in listPlugins('loaded')]
    elif which == 'failed':
        return list(_failed_plugins_)  # copy
    else:
        return list(_installed_plugins_.keys())


def isPluginLoaded(plugin):
    """Check if a plugin has been previously loaded successfully by a
    :func:`loadPlugin` call.

    Parameters
    ----------
    plugin : str
        Name of the plugin package to check if loaded. This usually refers to
        the package or project name.

    Returns
    -------
    bool
        `True` if a plugin was successfully loaded and active, else `False`.

    See Also
    --------
    loadPlugin : Load a plugin into the current session.

    """
    return plugin in listPlugins(which='loaded')


def isStartUpPlugin(plugin):
    """Check if a plugin is registered to be loaded when PsychoPy starts.

    Parameters
    ----------
    plugin : str
        Name of the plugin package to check. This usually refers to the package
        or project name.

    Returns
    -------
    bool
        `True` if a plugin is registered to be loaded when a PsychoPy session
        starts, else `False`.

    Examples
    --------
    Check if a plugin was loaded successfully at startup::

        pluginName = 'psychopy-plugin'
        if isStartUpPlugin(pluginName) and isPluginLoaded(pluginName):
            print('Plugin successfully loaded at startup.')

    """
    return plugin in listPlugins(which='startup')


def loadPlugin(plugin, *args, **kwargs):
    """Load a plugin to extend PsychoPy.

    Plugins are packages which extend upon PsychoPy's existing functionality by
    dynamically importing code at runtime, without modifying the existing
    installation files. Plugins create or redefine objects in the namespaces
    of modules (eg. `psychopy.visual`) and unbound classes, allowing them to be
    used as if they were part of PsychoPy. In some cases, objects exported by
    plugins will be registered for a particular function if they define entry
    points into specific modules.

    Plugins are simply Python packages,`loadPlugin` will search for them in
    directories specified in `sys.path`. Only packages which define entry points
    in their metadata which pertain to PsychoPy can be loaded with this
    function. This function also permits passing optional arguments to a
    callable object in the plugin module to run any initialization routines
    prior to loading entry points.

    This function is robust, simply returning `True` or `False` whether a
    plugin has been fully loaded or not. If a plugin fails to load, the reason
    for it will be written to the log as a warning or error, and the application
    will continue running. This may be undesirable in some cases, since features
    the plugin provides may be needed at some point and would lead to undefined
    behavior if not present. If you want to halt the application if a plugin
    fails to load, consider using :func:`requirePlugin`.

    It is advised that you use this function only when using PsychoPy as a
    library. If using the builder or coder GUI, it is recommended that you use
    the plugin dialog to enable plugins for PsychoPy sessions spawned by the
    experiment runner. However, you can still use this function if you want to
    load additional plugins for a given experiment, having their effects
    isolated from the main application and other experiments.

    Parameters
    ----------
    plugin : str
        Name of the plugin package to load. This usually refers to the package
        or project name.
    *args, **kwargs
        Optional arguments and keyword arguments to pass to the plugin's
        `__register__` function.

    Returns
    -------
    bool
        `True` if the plugin has valid entry points and was loaded successfully.
        Also returns `True` if the plugin was already loaded by a previous
        `loadPlugin` call this session, this function will have no effect in
        this case. `False` is returned if the plugin defines no entry points
        specific to PsychoPy or crashed (an error is logged).

    Warnings
    --------
    Make sure that plugins installed on your system are from reputable sources,
    as they may contain malware! PsychoPy is not responsible for undefined
    behaviour or bugs associated with the use of 3rd party plugins.

    See Also
    --------
    listPlugins : Search for and list installed or loaded plugins.
    requirePlugin : Require a plugin be previously loaded.

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
    global _loaded_plugins_, _failed_plugins_

    if isPluginLoaded(plugin):
        logging.info('Plugin `{}` already loaded. Skipping.'.format(plugin))
        return True  # already loaded, return True

    try:
        entryMap = _installed_plugins_[plugin]
    except KeyError:
        logging.warning(
            'Package `{}` does not appear to be a valid plugin. '
            'Skipping.'.format(plugin))
        if plugin not in _failed_plugins_:
            _failed_plugins_.append(plugin)

        return False

    if not any([i.startswith('psychopy') for i in entryMap.keys()]):
        logging.warning(
            'Specified package `{}` defines no entry points for PsychoPy. '
            'Skipping.'.format(plugin))

        if plugin not in _failed_plugins_.keys():
            _failed_plugins_.append(plugin)

        return False  # can't do anything more here, so return

    # go over entry points, looking for objects explicitly for psychopy
    validEntryPoints = collections.OrderedDict()  # entry points to assign
    for fqn, attrs in entryMap.items():
        if not fqn.startswith('psychopy'):
            continue

        # forbid plugins from modifying this module
        if fqn.startswith('psychopy.plugins') or \
                (fqn == 'psychopy' and 'plugins' in attrs):
            logging.error(
                "Plugin `{}` declares entry points into the `psychopy.plugins` "
                "module which is forbidden. Skipping.".format(plugin))

            if plugin not in _failed_plugins_:
                _failed_plugins_.append(plugin)

            return False

        # Get the object the fully-qualified name points to the group which the
        # plugin wants to modify.
        targObj = resolveObjectFromName(fqn, error=False)
        if targObj is None:
            logging.error(
                "Plugin `{}` specified entry point group `{}` that does not "
                "exist or is unreachable.".format(plugin, fqn))

            if plugin not in _failed_plugins_:
                _failed_plugins_.append(plugin)

            return False

        validEntryPoints[fqn] = []

        # Import modules assigned to entry points and load those entry points.
        # We don't assign anything to PsychoPy's namespace until we are sure
        # that the entry points are valid. This prevents plugins from being
        # partially loaded which can cause all sorts of undefined behaviour.
        for attr, ep in attrs.items():
            # Load the module the entry point belongs to, this happens
            # anyways when .load() is called, but we get to access it before
            # we start binding. If the module has already been loaded, don't
            # do this again.
            if ep.module_name not in sys.modules:
                # Do stuff before loading entry points here, any executable code
                # in the module will run to configure it.
                try:
                    imp = importlib.import_module(ep.module_name)
                except (ModuleNotFoundError, ImportError):
                    logging.error(
                        "Plugin `{}` entry point requires module `{}`, but it"
                        "cannot be imported.".format(plugin, ep.module_name))

                    if plugin not in _failed_plugins_:
                        _failed_plugins_.append(plugin)

                    return False

                # call the register function, check if exists and valid
                if hasattr(imp, '__register__') and imp.__register__ is not None:
                    if isinstance(imp.__register__, str):
                        if hasattr(imp, imp.__register__):  # local to module
                            func = getattr(imp, imp.__register__)
                        else:  # could be a FQN?
                            func = resolveObjectFromName(
                                imp.__register__, error=False)
                        # check if the reference object is callable
                        if not callable(func):
                            logging.error(
                                "Plugin `{}` module defines `__register__` but "
                                "the specified object is not a callable type. "
                                "Skipping.".format(plugin))

                            if plugin not in _failed_plugins_:
                                _failed_plugins_.append(plugin)

                            return False

                    elif callable(imp.__register__):  # a function was supplied
                        func = imp.__register__
                    else:
                        logging.error(
                            "Plugin `{}` module defines `__register__` but "
                            "is not `str` or callable type. Skipping.".format(
                                plugin))

                        if plugin not in _failed_plugins_:
                            _failed_plugins_.append(plugin)

                        return False

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
                    logging.warning(
                        "Plugin `{}` attempted to override module `{}`.".format(
                            plugin, fqn + '.' + attr))

                    # if plugin not in _failed_plugins_:
                    #     _failed_plugins_.append(plugin)
                    #
                    # return False
            try:
                ep = ep.load()  # load the entry point
            except ImportError as e:
                logging.error(
                    "Failed to load entry point `{}` of plugin `{}`. "
                    "(`{}: {}`) "
                    "Skipping.".format(str(ep), plugin, e.name, e.msg))

                if plugin not in _failed_plugins_:
                    _failed_plugins_.append(plugin)

                return False

            # If we get here, the entry point is valid and we can safely add it
            # to PsychoPy's namespace.
            validEntryPoints[fqn].append((targObj, attr, ep))

    # Assign entry points that have been successfully loaded. We defer
    # assignment until all entry points are deemed valid to prevent plugins
    # from being partially loaded.
    for fqn, vals in validEntryPoints.items():
        for targObj, attr, ep in vals:
            # add the object to the module or unbound class
            setattr(targObj, attr, ep)
            logging.debug(
                "Assigning to entry point `{}` to `{}`.".format(
                    ep.__name__, fqn + '.' + attr))

            # --- handle special cases ---
            if fqn == 'psychopy.visual.backends':  # if window backend
                _registerWindowBackend(attr, ep)
            elif fqn == 'psychopy.experiment.components':  # if component
                _registerBuilderComponent(ep)

    # Retain information about the plugin's entry points, we will use this for
    # conflict resolution.
    _loaded_plugins_[plugin] = entryMap

    # If we made it here on a previously failed plugin, it was likely fixed and
    # can be removed from the list.
    if plugin not in _failed_plugins_:
        try:
            _failed_plugins_.remove(plugin)
        except ValueError:
            pass

    return True


def requirePlugin(plugin):
    """Require a plugin to be already loaded.

    This function can be used to ensure if a plugin has already been loaded and
    is ready for use, raising an exception and ending the session if not.

    This function compliments :func:`loadPlugin`, which does not halt the
    application if plugin fails to load. This allows PsychoPy to continue
    working, giving the user a chance to deal with the problem (either by
    disabling or fixing the plugins). However, :func:`requirePlugin` can be used
    to guard against undefined behavior caused by a failed or partially loaded
    plugin by raising an exception before any code that uses the plugin's
    features is executed.

    Parameters
    ----------
    plugin : str
        Name of the plugin package to require. This usually refers to the package
        or project name.

    Raises
    ------
    RuntimeError
        Plugin has not been previously loaded this session.

    See Also
    --------
    loadPlugin : Load a plugin into the current session.

    Examples
    --------
    Ensure plugin `psychopy-plugin` is loaded at this point in the session::

        requirePlugin('psychopy-plugin')  # error if not loaded

    You can catch the error and try to handle the situation by::

        try:
            requirePlugin('psychopy-plugin')
        except RuntimeError:
            # do something about it ...

    """
    if not isPluginLoaded(plugin):
        raise RuntimeError('Required plugin `{}` has not been loaded.'.format(
            plugin))


def startUpPlugins(plugins, add=True, verify=True):
    """Specify which plugins should be loaded automatically when a PsychoPy
    session starts.

    This function edits ``psychopy.preferences.prefs.general['startUpPlugins']``
    and provides a means to verify if entries are valid. The PsychoPy session
    must be restarted for the plugins specified to take effect.

    If using PsychoPy as a library, this function serves as a convenience to
    avoid needing to explicitly call :func:`loadPlugin` every time to use your
    favorite plugins.

    Parameters
    ----------
    plugins : `str`, `list` or `None`
        Name(s) of plugins to have load on startup.
    add : bool
        If `True` names of plugins will be appended to `startUpPlugins` unless a
        name is already present. If `False`, `startUpPlugins` will be set to
        `plugins`, overwriting the previous value. If `add=False` and
        `plugins=[]` or `plugins=None`, no plugins will be loaded in the next
        session.
    verify : bool
        Check if `plugins` are installed and have valid entry points to
        PsychoPy. Raises an error if any are not. This prevents undefined
        behavior arsing from invalid plugins being loaded in the next session.
        If `False`, plugin names will be added regardless if they are installed
        or not.

    Raises
    ------
    RuntimeError
        If `verify=True`, any of `plugins` is not installed or does not have
        entry points to PsychoPy. This is raised to prevent issues in future
        sessions where invalid plugins are written to the config file and are
        automatically loaded.

    Warnings
    --------
    Do not use this function within the builder or coder GUI! Use the plugin
    dialog to specify which plugins to load on startup. Only use this function
    when using PsychoPy as a library!

    Examples
    --------
    Adding plugins to load on startup::

        startUpPlugins(['plugin1', 'plugin2'])

    Clearing the startup plugins list, no plugins will be loaded automatically
    at the start of the next session::

        plugins.startUpPlugins([], add=False)
        # or ..
        plugins.startUpPlugins(None, add=False)

    If passing `None` or an empty list with `add=True`, the present value of
    `prefs.general['startUpPlugins']` will remain as-is.

    """
    # check if there is a config entry
    if 'startUpPlugins' not in prefs.general.keys():
        logging.warning(
            'Config file does not define `startUpPlugins`. Skipping.')

        return

    # if a string is specified
    if isinstance(plugins, str):
        plugins = [plugins]

    # if the list is empty or None, just clear
    if not plugins or plugins is None:
        if not add:  # adding nothing gives the original
            prefs.general['startUpPlugins'] = []
            prefs.saveUserPrefs()

        return

    # check if the plugins are installed before adding to `startUpPlugins`
    installedPlugins = listPlugins()
    if verify:
        notInstalled = [plugin not in installedPlugins for plugin in plugins]
        if any(notInstalled):
            missingIdx = [i for i, x in enumerate(notInstalled) if x]
            errStr = ''  # build up an error string
            for i, idx in enumerate(missingIdx):
                if i < len(missingIdx) - 1:
                    errStr += '`{}`, '.format(plugins[idx])
                else:
                    errStr += '`{}`;'.format(plugins[idx])

            raise RuntimeError(
                "Cannot add startup plugin(s): {} either not installed or has "
                "no PsychoPy entry points.".format(errStr))

    if add:  # adding plugin names to existing list
        for plugin in plugins:
            if plugin not in prefs.general['startUpPlugins']:
                prefs.general['startUpPlugins'].append(plugin)
    else:
        prefs.general['startUpPlugins'] = plugins  # overwrite

    prefs.saveUserPrefs()  # save after loading


def pluginMetadata(plugin):
    """Get metadata from a plugin package.

    Reads the package's PKG_INFO and gets fields as a dictionary. Only packages
    that have valid entry points to PsychoPy can be queried.

    Parameters
    ----------
    plugin : str
        Name of the plugin package to retrieve metadata from.

    Returns
    -------
    dict
        Metadata fields.

    """
    installedPlugins = listPlugins()
    if plugin not in installedPlugins:
        raise ModuleNotFoundError(
            "Plugin `{}` is not installed or does not have entry points for "
            "PsychoPy.".format(plugin))

    pkg = pkg_resources.get_distribution(plugin)
    metadata = pkg.get_metadata(pkg.PKG_INFO)

    metadict = {}
    for line in metadata.split('\n'):
        if not line:
            continue

        line = line.strip().split(': ')
        if len(line) == 2:
            field, value = line
            metadict[field] = value

    return metadict


def pluginEntryPoints(plugin, parse=False):
    """Get the entry point mapping for a specified plugin.

    You must call `scanPlugins` before calling this function to get the entry
    points for a given plugin.

    Note this function is intended for internal use by the PsychoPy plugin
    system only.

    Parameters
    ----------
    plugin : str
        Name of the plugin package to get advertised entry points.
    parse : bool
        Parse the entry point specifiers and convert them to fully-qualified
        names.

    Returns
    -------
    dict
        Dictionary of target groups/attributes and entry points objects.

    """
    global _installed_plugins_
    if plugin in _installed_plugins_.keys():
        if not parse:
            return _installed_plugins_[plugin]
        else:
            toReturn = {}
            for group, val in _installed_plugins_[plugin].items():
                if group not in toReturn.keys():
                    toReturn[group] = {}  # create a new group entry

                for attr, ep in val.items():
                    # parse the entry point specifier
                    ex = '.'.join(str(ep).split(' = ')[1].split(':'))  # make fqn
                    toReturn[group].update({attr: ex})

            return toReturn

    logging.error("Cannot retrieve entry points for plugin `{}`, either not "
                  " installed or reachable.")

    return None


def _registerWindowBackend(attr, ep):
    """Make an entry point discoverable as a window backend.

    This allows it the given entry point to be used as a window backend by
    specifying `winType`. All window backends must be subclasses of `BaseBackend`
    and define a `winTypeName` attribute. The value of `winTypeName` will be
    used for selecting `winType`.

    This function is called by :func:`loadPlugin`, it should not be used for any
    other purpose.

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
    backend = resolveObjectFromName(
        fqn, resolve=(fqn not in sys.modules), error=False)

    if backend is None:
        logging.error("Failed to resolve name `{}`.".format(fqn))
        return   # something weird happened, just exit

    # if a module, scan it for valid backends
    foundBackends = {}
    if inspect.ismodule(ep):  # if the backend is a module
        for attrName in dir(ep):
            _attr = getattr(ep, attrName)
            if not inspect.isclass(_attr):  # skip if not class
                continue
            if not issubclass(_attr, backend.BaseBackend):  # not backend
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
        if not issubclass(ep, backend.BaseBackend):
            return
        if not hasattr(ep, 'winTypeName'):
            return
        foundBackends[ep.winTypeName] = '.' + attr
        logging.debug(
            "Registered window backend class `{}` for `winType={}`.".format(
                foundBackends[ep.winTypeName], ep.winTypeName))

    backend.winTypes.update(foundBackends)  # update installed backends


def _registerBuilderComponent(ep):
    """Register a PsychoPy builder component module.

    This function is called by :func:`loadPlugin` when encountering an entry
    point group for :mod:`psychopy.experiment.components`. It searches the
    module at the entry point for sub-classes of `BaseComponent` and registers
    it as a builder component. It will also search the module for any resources
    associated with the component (eg. icons and tooltip text) and register them
    for use.

    Builder component modules in plugins should follow the conventions and
    structure of a normal, stand-alone components. Any plugins that adds
    components to PsychoPy must be registered to load on startup.

    This function is called by :func:`loadPlugin`, it should not be used for any
    other purpose.

    Parameters
    ----------
    ep : ModuleType
        Module containing the builder component to register.

    """
    if not inspect.ismodule(ep):  # not a module
        return

    # give a default category
    if not hasattr(ep, 'categories'):
        ep.categories = ['Custom']

    # check if module contains components
    for attrib in dir(ep):
        # name and reference to component class
        name = attrib
        cls = getattr(ep, attrib)

        if not inspect.isclass(cls):
            continue

        if not issubclass(cls, components.BaseComponent):
            continue

        components.pluginComponents[attrib] = getattr(ep, attrib)

        # skip if this class was imported, not defined here
        if ep.__name__ != components.pluginComponents[attrib].__module__:
            continue  # class was defined in different module

        if hasattr(ep, 'tooltip'):
            components.tooltips[name] = ep.tooltip

        if hasattr(ep, 'iconFile'):
            components.iconFiles[name] = ep.iconFile

        # assign the module categories to the Component
        if not hasattr(components.pluginComponents[attrib], 'categories'):
            components.pluginComponents[attrib].categories = ['Custom']


if __name__ == "__main__":
    pass
