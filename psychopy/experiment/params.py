#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2022 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Experiment classes:
    Experiment, Flow, Routine, Param, Loop*, *Handlers, and NameSpace

The code that writes out a *_lastrun.py experiment file is (in order):
    experiment.Experiment.writeScript() - starts things off, calls other parts
    settings.SettingsComponent.writeStartCode()
    experiment.Flow.writeBody()
        which will call the .writeBody() methods from each component
    settings.SettingsComponent.writeEndCode()
"""
import functools
from xml.etree.ElementTree import Element

import re
from pathlib import Path

from psychopy import logging
from . import utils
from . import py2js

from ..colors import Color
from numpy import ndarray
from ..alerts import alert


def _findParam(name, node):
    """Searches an XML node in search of a particular param name

    :param name: str indicating the name of the attribute
    :param node: xml element/node to be searched
    :return: None, or a parameter child node
    """
    for attr in node:
        if attr.get('name') == name:
            return attr

inputDefaults = {
    'str': 'single',
    'code': 'single',
    'num': 'single',
    'bool': 'bool',
    'list': 'single',
    'file': 'file',
    'color': 'color',
}

# These are parameters which once existed but are no longer needed, so inclusion in this list will silence any "future
# version" warnings
legacyParams = [
    'lineColorSpace', 'borderColorSpace', 'fillColorSpace', 'foreColorSpace',  # 2021.1, we standardised colorSpace to be object-wide rather than param-specific
]

class Param():
    r"""Defines parameters for Experiment Components
    A string representation of the parameter will depend on the valType:

    >>> print(Param(val=[3,4], valType='num'))
    asarray([3, 4])
    >>> print(Param(val=3, valType='num')) # num converts int to float
    3.0
    >>> print(Param(val=3, valType='str') # str keeps as int, converts to code
    3
    >>> print(Param(val='3', valType='str')) # ... and keeps str as str
    '3'
    >>> print(Param(val=[3,4], valType='str')) # val is <type 'list'> -> code
    [3, 4]
    >>> print(Param(val='[3,4]', valType='str'))
    '[3,4]'
    >>> print(Param(val=[3,4], valType='code'))
    [3, 4]
    >>> print(Param(val='"yes", "no"', valType='list'))
    ["yes", "no"]

    >>> #### auto str -> code:  at least one non-escaped '$' triggers
    >>> print(Param('[x,y]','str')) # str normally returns string
    '[x,y]'
    >>> print(Param('$[x,y]','str')) # code, as triggered by $
    [x,y]
    >>> print(Param('[$x,$y]','str')) # code, redundant $ ok, cleaned up
    [x,y]
    >>> print(Param('[$x,y]','str')) # code, a $ anywhere means code
    [x,y]
    >>> print(Param('[x,y]$','str')) # ... even at the end
    [x,y]
    >>> print(Param('[x,\$y]','str')) # string, because the only $ is escaped
    '[x,$y]'
    >>> print(Param('[x,\ $y]','str')) # improper escape -> code
    [x,\ y]
    >>> print(Param('/$[x,y]','str')) # improper escape -> code
    /[x,y]
    >>> print(Param('[\$x,$y]','str')) # code, python syntax error
    [$x,y]
    >>> print(Param('["\$x",$y]','str') # ... python syntax ok
    ["$x",y]
    >>> print(Param("'$a'",'str')) # code, with the code being a string
    'a'
    >>> print(Param("'\$a'",'str')) # str, with the str containing a str
    "'$a'"
    >>> print(Param('$$$$$myPathologicalVa$$$$$rName','str'))
    myPathologicalVarName
    >>> print(Param('\$$$$$myPathologicalVa$$$$$rName','str'))
    $myPathologicalVarName
    >>> print(Param('$$$$\$myPathologicalVa$$$$$rName','str'))
    $myPathologicalVarName
    >>> print(Param('$$$$\$$$myPathologicalVa$$$\$$$rName','str'))
    $myPathologicalVa$rName
    """

    def __init__(self, val, valType, inputType=None, allowedVals=None, allowedTypes=None,
                 hint="", label="", updates=None, allowedUpdates=None,
                 allowedLabels=None, direct=True,
                 canBePath=True,
                 categ="Basic"):
        """
        @param val: the value for this parameter
        @type val: any
        @param valType: the type of this parameter ('num', 'str', 'code')
        @type valType: string
        @param allowedVals: possible vals for this param
            (e.g. units param can only be 'norm','pix',...)
        @type allowedVals: any
        @param allowedTypes: if other types are allowed then this is
            the possible types this parameter can have
            (e.g. rgb can be 'red' or [1,0,1])
        @type allowedTypes: list
        @param hint: describe this parameter for the user
        @type hint: string
        @param updates: how often does this parameter update
            ('experiment', 'routine', 'set every frame')
        @type updates: string
        @param allowedUpdates: conceivable updates for this param
            [None, 'routine', 'set every frame']
        @type allowedUpdates: list
        @param categ: category for this parameter
            will populate tabs in Component Dlg
        @type allowedUpdates: string
        @param canBePath: is it possible for this parameter to be
            a path? If so, writing as str will check for pathlike
            characters and sanitise if needed.
        @type canBePath: bool
        @param direct: purely used in the test suite, marks whether this
        param's value is expected to appear in the script
        @type direct: bool
        """
        super(Param, self).__init__()
        self.label = label
        self.val = val
        self.valType = valType
        self.allowedTypes = allowedTypes or []
        self.hint = hint
        self.updates = updates
        self.allowedUpdates = allowedUpdates
        self.allowedVals = allowedVals or []
        self.allowedLabels = allowedLabels or []
        self.staticUpdater = None
        self.categ = categ
        self.readOnly = False
        self.codeWanted = False
        self.canBePath = canBePath
        self.direct = direct
        if inputType:
            self.inputType = inputType
        elif valType in inputDefaults:
            self.inputType = inputDefaults[valType]
        else:
            self.inputType = "String"

    def __str__(self):
        # localise variables
        val = self.val
        valType = self.valType
        # parse dollar syntax to work out val type / val types
        val, valType = dollarSyntax(val, valType)

        if isinstance(valType, (list, tuple)):
            parsed = []
            for subval, subType in zip(val, valType):
                parsed.append(
                    self.asString(subval, subType)
                )
            return "[" + ", ".join(parsed) + "]"
        else:
            return self.asString(val, valType)

    def asString(self, val=None, valType=None):
        if val is None:
            val = self.val
        if valType is None:
            valType = self.valType

        if valType == 'num':
            if val in [None, ""]:
                return "None"
            try:
                # will work if it can be represented as a float
                return "{}".format(float(val))
            except Exception:  # might be an array
                return "%s" % val
        elif valType == 'int':
            try:
                return "%i" % val  # int and float -> str(int)
            except TypeError:
                return "%s" % val  # try array of float instead?
        elif valType in ['extendedStr', 'str', 'file', 'table']:
            # at least 1 non-escaped '$' anywhere --> code wanted
            # return str if code wanted
            # return repr if str wanted; this neatly handles "it's" and 'He
            # says "hello"'
            if isinstance(val, str):
                # If str is wanted, return literal
                if utils.scriptTarget != 'PsychoPy':
                    if val.startswith("u'") or val.startswith('u"'):
                        # if target is python2.x then unicode will be u'something'
                        # but for other targets that will raise an annoying error
                        val = val[1:]
                # If param is a path or pathlike use Path to make sure it's valid (with / not \)
                isPathLike = bool(re.findall(r"[\\/](?!\W)", val))
                if valType in ['file', 'table'] or (isPathLike and self.canBePath):
                    val = val.replace("\\\\", "/")
                    val = val.replace("\\", "/")
                # Hide escape char on escaped $ (other escaped chars are handled by wx but $ is unique to us)
                val = re.sub(r"\\\$", "$", val)
                # Replace line breaks with escaped line break character
                val = re.sub("\n", "\\n", val)
                return repr(val)
            return repr(val)
        elif valType in ['code', 'extendedCode']:
            isStr = isinstance(val, str)
            if isStr and val.startswith("$"):
                # a $ in a code parameter is unnecessary so remove it
                val = "%s" % val[1:]
            elif isStr and val.startswith(r"\$"):
                # the user actually wanted just the $
                val = "%s" % val[1:]
            elif isStr:
                val = "%s" % val
            else:  # if val was a tuple it needs converting to a string first
                val = "%s" % repr(val)
            if utils.scriptTarget == "PsychoJS":
                if valType == 'code':
                    valJS = py2js.expression2js(val)
                elif valType == 'extendedCode':
                    valJS = py2js.snippet2js(val)
                if val != valJS:
                    logging.debug("Rewriting with py2js: {} -> {}".format(val, valJS))
                return valJS
            else:
                return val
        elif valType == 'color':
            if "," in val:
                # Handle lists (e.g. RGB, HSV, etc.)
                val = toList(val)
                return "{}".format(val)
            else:
                # Otherwise, treat as string
                return repr(val)
        elif valType == 'list':
            val = toList(val)
            return "{}".format(val)
        elif valType == 'bool':
            if utils.scriptTarget == "PsychoJS":
                return ("%s" % val).lower()  # make True -> "true"
            else:
                return "%s" % val
        elif valType == "table":
            return "%s" % val
        elif valType == "color":
            if re.match(r"\$", val):
                return val.strip('$')
            else:
                return f"\"{val}\""
        elif valType == "dict":
            return str(val)
        else:
            raise TypeError("Can't represent a Param of type %s" %
                            valType)

    def __repr__(self):
        return f"<Param: val={self.val}, valType={self.valType}>"

    def __eq__(self, other):
        """Test for equivalence is needed for Params because what really
        typically want to test is whether the val is the same
        """
        return self.val == other

    def __ne__(self, other):
        """Test for (non)equivalence is needed for Params because what really
        typically want to test is whether the val is the same/different
        """
        return self.val != other

    def __bool__(self):
        """Return a bool, so we can do `if thisParam`
        rather than `if thisParam.val`"""
        if self.val in ['True', 'true', 'TRUE', True, 1, 1.0]:
            # Return True for aliases of True
            return True
        if self.val in ['False', 'false', 'FALSE', False, 0, 0.0]:
            # Return False for aliases of False
            return False
        # If not a clear alias, use bool method of value
        return bool(self.val)

    @property
    def _xml(self):
        # Make root element
        element = Element('Param')
        # Assign values
        if hasattr(self, 'val'):
            element.set('val', u"{}".format(self.val).replace("\n", "&#10;"))
        if hasattr(self, 'valType'):
            element.set('valType', self.valType)
        if hasattr(self, 'updates'):
            element.set('updates', "{}".format(self.updates))

        return element

    def dollarSyntax(self):
        return dollarSyntax(self.val, self.valType)

    __nonzero__ = __bool__  # for python2 compatibility


class Partial(functools.partial):
    """
    Value to supply to `allowedVals` or `allowedLabels` which contains a reference
    to a method and arguments to use when populating the control.

    Parameters
    ----------
    method : method
        Method to call, should return the values to be used in the relevant control.
    args : tuple, list
        Array of positional arguments. To use the value of another parameter, supply
        a handle to its Param object.
    kwargs : dict
        Dict of keyword arguments. To use the value of another parameter, supply
        a handle to its Param object.
    """
    def __init__(self, method, args=(), kwargs=dict()):
        self.method = method
        self.args = args
        self.kwargs = kwargs


def dollarSyntax(val, valType):
    """
    Parse dollar syntax to identify whether a parameter value indicates that it is code.

    Parameters
    ----------
    val : any
        Value to parse dollar syntax within
    valType : str
        Type of the value before taking dollar syntax into account

    Returns
    -------
    any
        The value with dollar signs removed
    str or list
        The new valType of the param (or a list of valTypes, if given a list to start with)
    """

    # if val is a list, call on each item and return output as list
    if isinstance(val, (list, tuple)):
        outVal = []
        outTypes = []
        for subval in val:
            subval, subvalType = dollarSyntax(subval, "str")
            outVal.append(subval)
            outTypes.append(subvalType)

        return outVal, outTypes

    # if val isn't a string, just return as is
    if not isinstance(val, str):
        return val, valType

    # copy val
    activeVal = str(val)
    # remove any string contents
    activeVal = re.sub(r"[\"'].*[\"']", "_", activeVal)
    # remove any comments
    activeVal = re.sub(r"#.*", "_", activeVal)
    # if there are still unescaped dollars, it's code
    unescapedDollars = list(re.finditer(utils.unescaped_re + r"\$", activeVal))
    if unescapedDollars:
        valType = "code"

    # remove code markers
    deleteMarker = chr(int("FFFFE", 16))
    for match in unescapedDollars:
        val = val[:match.start()] + chr(int("FFFFE", 16)) + val[match.end():]
    val = val.replace(deleteMarker, "")

    return val, valType


def getCodeFromParamStr(val, target=None):
    """Convert a Param.val string to its intended python code
    (as triggered by special char $)
    """
    # Substitute target
    if target is None:
        target = utils.scriptTarget
    # remove leading $, if any
    tmp = re.sub(r"^(\$)+", '', val)
    # remove all nonescaped $, squash $$$$$
    tmp2 = re.sub(r"([^\\])(\$)+", r"\1", tmp)
    out = re.sub(r"[\\]\$", '$', tmp2)  # remove \ from all \$
    if target == 'PsychoJS':
        out = py2js.expression2js(out)
    return out if out else ''


def toList(val):
    """

    Parameters
    ----------
    val

    Returns
    -------
    A list of entries in the string value
    """
    if isinstance(val, (list, tuple, ndarray)):
        return val  # already a list. Nothing to do
    if isinstance(val, (int, float)):
        return [val]  # single value, just needs putting in a cell
    # we really just need to check if they need parentheses
    stripped = val.strip()
    if utils.scriptTarget == "PsychoJS":
        return py2js.expression2js(stripped)
    elif (stripped.startswith('(') and stripped.endswith(')')) or (stripped.startswith('[') and stripped.endswith(']')):
        return stripped
    elif utils.valid_var_re.fullmatch(stripped):
        return "{}".format(stripped)
    else:
        return "[{}]".format(stripped)
