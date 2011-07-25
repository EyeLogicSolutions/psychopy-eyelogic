# Part of the PsychoPy library
# Copyright (C) 2011 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import StringIO, sys, codecs
from components import *#getComponents('') and getAllComponents([])
from psychopy import data, preferences, __version__, log
from lxml import etree
import numpy, numpy.random # want to query their name-spaces
import re, os
from psychopy.constants import FOREVER

# predefine some regex's (do it here because deepcopy complains if do in NameSpace.__init__)
_valid_var_re = re.compile(r"^[a-zA-Z_][\w]*$")  # filter for legal var names
_nonalphanumeric_re = re.compile(r'\W') # will match all bad var name chars

"""the code that writes out an actual experiment file is (in order):
    experiment.Experiment.writeScript() - starts things off, calls other parts
    settings.SettingsComponent.writeStartCode()
    experiment.Flow.writeCode()
        which will call .writeCode() bits from each component
    settings.SettingsComponent.writeStartCode()
"""

class IndentingBuffer(StringIO.StringIO):
    def __init__(self, *args, **kwargs):
        StringIO.StringIO.__init__(self, *args, **kwargs)
        self.oneIndent="    "
        self.indentLevel=0
    def writeIndented(self,text):
        """Write to the StringIO buffer, but add the current indent.
        Use write() if you don't want the indent.

        To test if the prev character was a newline use::
            self.getvalue()[-1]=='\n'

        """
        self.write(self.oneIndent*self.indentLevel + text)
    def writeIndentedLines(self,text):
        """As writeIndented(text) except that each line in text gets the indent level rather
        than the first line only.
        """
        for line in text.splitlines():
            self.write(self.oneIndent*self.indentLevel + line + '\n')
    def setIndentLevel(self, newLevel, relative=False):
        """Change the indent level for the buffer to a new value.

        Set relative to True if you want to increment or decrement the current value.
        """
        if relative:
            self.indentLevel+=newLevel
        else:
            self.indentLevel=newLevel

class Experiment:
    """
    An experiment contains a single Flow and at least one
    Routine. The Flow controls how Routines are organised
    e.g. the nature of repeats and branching of an experiment.
    """
    def __init__(self, prefs=None):
        self.name=None
        self.flow = Flow(exp=self)#every exp has exactly one flow
        self.routines={}
        #get prefs (from app if poss or from cfg files)
        if prefs==None:
            prefs = preferences.Preferences()
        #deepCopy doesn't like the full prefs object to be stored, so store each subset
        self.prefsAppDataCfg=prefs.appDataCfg
        self.prefsGeneral=prefs.general
        self.prefsCoder=prefs.coder
        self.prefsBuilder=prefs.builder
        self.prefsPaths=prefs.paths
        #this can be checked by the builder that this is an experiment and a compatible version
        self.psychopyVersion=psychopy.__version__ #imported from components
        self.psychopyLibs=['core','data', 'event']
        self.settings=getAllComponents()['SettingsComponent'](parentName='', exp=self)
        self._doc=None#this will be the xml.dom.minidom.doc object for saving
        self.namespace = NameSpace(self) # manage variable names
    def requirePsychopyLibs(self, libs=[]):
        """Add a list of top-level psychopy libs that the experiment will need.
        e.g. [visual, event]
        """
        if type(libs)!=list:
            libs=list(libs)
        for lib in libs:
            if lib not in self.psychopyLibs:
                self.psychopyLibs.append(lib)
    def addRoutine(self,routineName, routine=None):
        """Add a Routine to the current list of them.

        Can take a Routine object directly or will create
        an empty one if none is given.
        """
        if routine==None:
            self.routines[routineName]=Routine(routineName, exp=self)#create a deafult routine with this name
        else:
            self.routines[routineName]=routine

    def writeScript(self, expPath=None):
        """Write a PsychoPy script for the experiment
        """
        self.expPath = expPath
        script = IndentingBuffer(u'') #a string buffer object
        script.write('#!/usr/bin/env python\n' +
                    '# -*- coding: utf-8 -*-\n' +
                    '"""\nThis experiment was created using PsychoPy2 Experiment Builder (v%s), %s\n' % (
                        self.psychopyVersion, data.getDateStr(format="%B %d, %Y, at %H:%M") ) +
                    'If you publish work using this script please cite the relevant PsychoPy publications\n' +
                    '  Peirce, JW (2007) PsychoPy - Psychophysics software in Python. Journal of Neuroscience Methods, 162(1-2), 8-13.\n' +
                    '  Peirce, JW (2009) Generating stimuli for neuroscience using PsychoPy. Frontiers in Neuroinformatics, 2:10. doi: 10.3389/neuro.11.010.2008\n"""\n')
        script.write("from numpy import * #many different maths functions\n" +
                    "from numpy.random import * #maths randomisation functions\n" +
                    "import os #handy system and path functions\n" +
                    "from psychopy import %s\n" % ', '.join(self.psychopyLibs) +
                    "import psychopy.log #import like this so it doesn't interfere with numpy.log\n" +
                    "from psychopy.constants import *\n\n")
        self.namespace.user.sort()
        script.write("#User-defined variables = %s\n" % str(self.namespace.user) +
                    "known_name_collisions = %s  #(collisions are bad)\n\n" % str(self.namespace.get_collisions()) )
        
        self.settings.writeStartCode(script) #present info dlg, make logfile, Window
        #delegate rest of the code-writing to Flow
        self.flow.writeCode(script)
        self.settings.writeEndCode(script) #close log file

        return script
    
    def saveToXML(self, filename):
        #create the dom object
        self.xmlRoot = etree.Element("PsychoPy2experiment")
        self.xmlRoot.set('version', __version__)
        self.xmlRoot.set('encoding', 'utf-8')
        
        ##in the following, anything beginning '
        #store settings
        settingsNode=etree.SubElement(self.xmlRoot, 'Settings')
        for name, setting in self.settings.params.iteritems():
            settingNode=self._setXMLparam(parent=settingsNode,param=setting,name=name)
        #store routines
        routinesNode=etree.SubElement(self.xmlRoot, 'Routines')
        for routineName, routine in self.routines.iteritems():#routines is a dict of routines
            routineNode = self._setXMLparam(parent=routinesNode,param=routine,name=routineName)
            for component in routine: #a routine is based on a list of components
                componentNode=self._setXMLparam(parent=routineNode,param=component,name=component.params['name'].val)
                for name, param in component.params.iteritems():
                    paramNode=self._setXMLparam(parent=componentNode,param=param,name=name)
        #implement flow
        flowNode=etree.SubElement(self.xmlRoot, 'Flow')
        for element in self.flow:#a list of elements(routines and loopInit/Terms)
            elementNode=etree.SubElement(flowNode, element.getType())
            if element.getType() == 'LoopInitiator':
                loop=element.loop
                name = loop.params['name'].val      
                elementNode.set('loopType',loop.getType())
                elementNode.set('name', name)
                for paramName, param in loop.params.iteritems():
                    paramNode = self._setXMLparam(parent=elementNode,param=param,name=paramName)
                    if paramName=='trialList': #override val with repr(val)
                        paramNode.set('val',repr(param.val))
            elif element.getType() == 'LoopTerminator':
                elementNode.set('name', element.loop.params['name'].val)
            elif element.getType() == 'Routine':
                elementNode.set('name', '%s' %element.params['name'])
        #write to disk
        f=codecs.open(filename, 'wb', 'utf-8')
        f.write(etree.tostring(self.xmlRoot, encoding=unicode, pretty_print=True))
        f.close()
    def _getShortName(self, longName):
        return longName.replace('(','').replace(')','').replace(' ','')
    def _setXMLparam(self,parent,param,name):
        """Add a new child to a given xml node.
        name can include spaces and parens, which will be removed to create child name
        """
        if hasattr(param,'getType'):
            thisType = param.getType()
        else: thisType='Param'
        thisChild = etree.SubElement(parent,thisType)#creates and appends to parent
        thisChild.set('name',name)
        if hasattr(param,'val'): thisChild.set('val',unicode(param.val))
        if hasattr(param,'valType'): thisChild.set('valType',param.valType)
        if hasattr(param,'updates'): thisChild.set('updates',unicode(param.updates))
        return thisChild
    def _getXMLparam(self,params,paramNode):
        """params is the dict of params of the builder component (e.g. stimulus) into which
        the parameters will be inserted (so the object to store the params should be created first)
        paramNode is the parameter node fetched from the xml file
        """
        name=paramNode.get('name')
        if name=='times':#handle this parameter, deprecated in v1.60.00
            exec('times=%s' %paramNode.get('val'))
            params['startTime'].val =unicode(times[0])
            params['duration'].val = unicode(times[1]-times[0])
            return #times doesn't need to update its type or 'updates' rule
        elif name=='correctIf':#handle this parameter, deprecated in v1.60.00
            corrIf=paramNode.get('val')
            corrAns=corrIf.replace('resp.keys==unicode(','').replace(')','')
            params['correctAns'].val=corrAns
            name='correctAns'#then we can fetch thte other aspects correctly below
        if 'olour' in name:#colour parameter was Americanised in v1.61.00
            name=name.replace('olour','olor')            
            params[name].val = paramNode.get('val')
        elif 'val' in paramNode.keys(): params[name].val = paramNode.get('val')
        #get the value type and update rate
        if 'valType' in paramNode.keys(): 
            params[name].valType = paramNode.get('valType')
            # compatibility checks: 
            if name in ['correctAns','allowedKeys','text'] and paramNode.get('valType')=='code':
                params[name].valType='str'# these components were changed in v1.60.01
            #conversions based on valType
            if params[name].valType=='bool': exec("params[name].val=%s" %params[name].val)
        if 'updates' in paramNode.keys(): 
            params[name].updates = paramNode.get('updates')
    def loadFromXML(self, filename):
        """Loads an xml file and parses the builder Experiment from it
        """
        #open the file using a parser that ignores prettyprint blank text
        parser = etree.XMLParser(remove_blank_text=True)
        f=open(filename)
        self._doc=etree.XML(f.read(),parser)
        f.close()
        root=self._doc#.getroot()
        
        #some error checking on the version (and report that this isn't valid .psyexp)?
        filename_base = os.path.basename(filename)
        if root.tag != "PsychoPy2experiment":
            log.error('%s is not a valid .psyexp file, "%s"' % (filename_base, root.tag))
            # the current exp is already vaporized at this point, oops
            return
        self.psychopyVersion = root.get('version')
        version_f = float(self.psychopyVersion.rsplit('.',1)[0]) # drop bugfix
        if version_f < 1.63:
            log.warning('note: v%s was used to create %s ("%s")' % (self.psychopyVersion, filename_base, root.tag))
        
        #Parse document nodes
        #first make sure we're empty
        self.flow = Flow(exp=self)#every exp has exactly one flow
        self.routines={}
        self.namespace = NameSpace(self) # start fresh
        modified_names = []
        
        #fetch exp settings
        settingsNode=root.find('Settings')
        for child in settingsNode:
            self._getXMLparam(params=self.settings.params, paramNode=child)
        #fetch routines
        routinesNode=root.find('Routines')
        for routineNode in routinesNode:#get each routine node from the list of routines
            routine_good_name = self.namespace.make_valid(routineNode.get('name'))
            if routine_good_name != routineNode.get('name'):
                modified_names.append(routineNode.get('name'))
            self.namespace.user.append(routine_good_name)
            routine = Routine(name=routine_good_name, exp=self)
            #self._getXMLparam(params=routine.params, paramNode=routineNode)
            self.routines[routineNode.get('name')]=routine
            for componentNode in routineNode:
                componentType=componentNode.tag
                #create an actual component of that type
                component=getAllComponents()[componentType](\
                    name=componentNode.get('name'),
                    parentName=routineNode.get('name'), exp=self)
                #populate the component with its various params
                for paramNode in componentNode:
                    self._getXMLparam(params=component.params, paramNode=paramNode)
                comp_good_name = self.namespace.make_valid(componentNode.get('name'))
                if comp_good_name != componentNode.get('name'):
                    modified_names.append(componentNode.get('name'))
                self.namespace.add(comp_good_name)
                component.params['name'].val = comp_good_name
                routine.append(component)
        
        #fetch flow settings
        flowNode=root.find('Flow')
        loops={}
        for elementNode in flowNode:
            if elementNode.tag=="LoopInitiator":
                loopType=elementNode.get('loopType')
                loopName=self.namespace.make_valid(elementNode.get('name'))
                if loopName != elementNode.get('name'):
                    modified_names.append(elementNode.get('name'))
                self.namespace.add(loopName)
                exec('loop=%s(exp=self,name="%s")' %(loopType,loopName))
                loops[loopName]=loop
                for paramNode in elementNode:
                    self._getXMLparam(paramNode=paramNode,params=loop.params)
                    #for trialList convert string rep to actual list of dicts
                    if paramNode.get('name')=='trialList':
                        param=loop.params['trialList']
                        exec('param.val=%s' %(param.val))#e.g. param.val=[{'ori':0},{'ori':3}]
                # get condition names from within trialListFile, if any:
                trialListFile = loop.params['trialListFile'].val
                if trialListFile:
                    trialListFile = os.path.join(os.path.dirname(filename), trialListFile)
                    loop.params['trialListFile'].val = trialListFile
                    _, fieldNames = data.importTrialList(trialListFile, returnFieldNames=True)
                    for fname in fieldNames:
                        if fname != self.namespace.make_valid(fname):
                            log.error('problem with condition name %s in trialListFile %s' % (fname, trialListFile))
                        else:
                            self.namespace.add(fname)
                self.flow.append(LoopInitiator(loop=loops[loopName]))
            elif elementNode.tag=="LoopTerminator":
                self.flow.append(LoopTerminator(loop=loops[elementNode.get('name')]))
            elif elementNode.tag=="Routine":
                self.flow.append(self.routines[elementNode.get('name')])
                
        if modified_names:
            log.warning('duplicate variable name(s) changed in loadFromXML: %s\n' % ' '.join(modified_names))
            
    def setExpName(self, name):
        self.name=name
        self.settings.expName=name

class Param:
    """Defines parameters for Experiment Components
    A string representation of the parameter will depend on the valType:

    >>> sizeParam = Param(val=[3,4], valType='num')
    >>> print sizeParam
    numpy.asarray([3,4])

    >>> sizeParam = Param(val=[3,4], valType='str')
    >>> print sizeParam
    "[3,4]"

    >>> sizeParam = Param(val=[3,4], valType='code')
    >>> print sizeParam
    [3,4]

    """
    def __init__(self, val, valType, allowedVals=[],allowedTypes=[], hint="", updates=None, allowedUpdates=None):
        """
        @param val: the value for this parameter
        @type val: any
        @param valType: the type of this parameter ('num', 'str', 'code')
        @type valType: string
        @param allowedVals: possible vals for this param (e.g. units param can only be 'norm','pix',...)
        @type allowedVals: any
        @param allowedTypes: if other types are allowed then this is the possible types this parameter can have (e.g. rgb can be 'red' or [1,0,1])
        @type allowedTypes: list
        @param hint: describe this parameter for the user
        @type hint: string
        @param updates: how often does this parameter update ('experiment', 'routine', 'set every frame')
        @type updates: string
        @param allowedUpdates: conceivable updates for this param [None, 'routine', 'set every frame']
        @type allowedUpdates: list
        """
        self.val=val
        self.valType=valType
        self.allowedTypes=allowedTypes
        self.hint=hint
        self.updates=updates
        self.allowedUpdates=allowedUpdates
        self.allowedVals=allowedVals
    def __str__(self):
        if self.valType == 'num':
            try:
                return str(float(self.val))#will work if it can be represented as a float
            except:#might be an array
                return "asarray(%s)" %(self.val)
        elif self.valType == 'str':
            if (type(self.val) in [str, unicode]) and self.val.startswith("$"):
                return "%s" %(self.val[1:])#override the string type and return as code
            elif (type(self.val) in [str, unicode]) and self.val.startswith("\$"): 
                return repr(self.val[1:])#the user actually wanted a string repr with the $ as first char
            else:#provide the string representation (the code to create a string)
                return repr(self.val)#this neatly handles like "it's" and 'He says "hello"'
        elif self.valType == 'code':
            if (type(self.val) in [str, unicode]) and self.val.startswith("$"):
                return "%s" %(self.val[1:])#a $ in a code parameter is unecessary so remove it
            elif (type(self.val) in [str, unicode]) and self.val.startswith("\$"): 
                return "%s" %(self.val[1:])#the user actually wanted just the $
            else:#provide the code
                return "%s" %(self.val)
        elif self.valType == 'bool':
            return "%s" %(self.val)
        else:
            raise TypeError, "Can't represent a Param of type %s" %self.valType

class TrialHandler:
    """A looping experimental control object
            (e.g. generating a psychopy TrialHandler or StairHandler).
            """
    def __init__(self, exp, name, loopType='random', nReps=5,
        trialList=[], trialListFile='',endPoints=[0,1]):
        """
        @param name: name of the loop e.g. trials
        @type name: string
        @param loopType:
        @type loopType: string ('rand', 'seq')
        @param nReps: number of reps (for all trial types)
        @type nReps:int
        @param trialList: list of different trial conditions to be used
        @type trialList: list (of dicts?)
        @param trialListFile: filename of the .csv file that contains trialList info
        @type trialList: string (filename)
        """
        self.type='TrialHandler'
        self.exp=exp
        self.order=['name']#make name come first (others don't matter)
        self.params={}
        self.params['name']=Param(name, valType='code', updates=None, allowedUpdates=None,
            hint="Name of this loop")
        self.params['nReps']=Param(nReps, valType='code', updates=None, allowedUpdates=None,
            hint="Number of repeats (for each type of trial)")
        self.params['trialList']=Param(trialList, valType='str', updates=None, allowedUpdates=None,
            hint="A list of dictionaries describing the differences between each trial type")
        self.params['trialListFile']=Param(trialListFile, valType='str', updates=None, allowedUpdates=None,
            hint="A comma-separated-value (.csv) file specifying the parameters for each trial")
        self.params['endPoints']=Param(endPoints, valType='num', updates=None, allowedUpdates=None,
            hint="The start and end of the loop (see flow timeline)")
        self.params['loopType']=Param(loopType, valType='str', 
            allowedVals=['random','sequential','staircase','interleaved staircases'],
            hint="How should the next trial value(s) be chosen?")#NB staircase is added for the sake of the loop properties dialog
        #these two are really just for making the dialog easier (they won't be used to generate code)
        self.params['endPoints']=Param(endPoints,valType='num',
            hint='Where to loop from and to (see values currently shown in the flow view)')
    def writeInitCode(self,buff):
        #todo: write code to fetch trialList from file?
        #create nice line-separated list of trial types
        if self.params['trialListFile'].val==None:
            trialStr="[None]"
        else: trialStr="data.importTrialList(%s)" %self.params['trialListFile']
        #also a 'thisName' for use in "for thisTrial in trials:"
        self.thisName = self.exp.namespace.make_loop_index(self.params['name'].val)
        #write the code
        buff.writeIndentedLines("\n#set up handler to look after randomisation of trials etc\n")
        buff.writeIndented("%s=data.TrialHandler(nReps=%s, method=%s, \n" \
                %(self.params['name'], self.params['nReps'], self.params['loopType']))
        buff.writeIndented("    extraInfo=expInfo, originPath=%s,\n" %repr(self.exp.expPath))
        buff.writeIndented("    trialList=%s)\n" %(trialStr))
        buff.writeIndented("%s=%s.trialList[0]#so we can initialise stimuli with some values\n" %(self.thisName, self.params['name']))
        #create additional names (e.g. rgb=thisTrial.rgb) if user doesn't mind cluttered namespace
        if not self.exp.prefsBuilder['unclutteredNamespace']:
            buff.writeIndented("#abbrieviate parameter names if possible (e.g. rgb=%s.rgb)\n" %self.thisName)
            buff.writeIndented("if %s!=None:\n" %self.thisName)
            buff.writeIndented(buff.oneIndent+"for paramName in %s.keys():\n" %self.thisName)
            buff.writeIndented(buff.oneIndent*2+"exec(paramName+'=%s.'+paramName)\n" %self.thisName)
    def writeLoopStartCode(self,buff):
        #work out a name for e.g. thisTrial in trials:
        buff.writeIndented("\n")
        buff.writeIndented("for %s in %s:\n" %(self.thisName, self.params['name']))
        #fetch parameter info from trialList        
        buff.setIndentLevel(1, relative=True)
        buff.writeIndented("currentLoop = %s\n" %(self.params['name']))
        #create additional names (e.g. rgb=thisTrial.rgb) if user doesn't mind cluttered namespace
        if not self.exp.prefsBuilder['unclutteredNamespace']:
            buff.writeIndented("#abbrieviate parameter names if possible (e.g. rgb=%s.rgb)\n" %self.thisName)
            buff.writeIndented("if %s!=None:\n" %self.thisName)
            buff.writeIndented(buff.oneIndent+"for paramName in %s.keys():\n" %self.thisName)
            buff.writeIndented(buff.oneIndent*2+"exec(paramName+'=%s.'+paramName)\n" %self.thisName)
    def writeLoopEndCode(self,buff):
        buff.setIndentLevel(-1, relative=True)
        buff.writeIndented("\n")
        buff.writeIndented("#completed %s repeats of '%s'\n" \
            %(self.params['nReps'], self.params['name']))
        buff.writeIndented("\n")

        #save data
        ##a string to show all the available variables (if the trialList isn't just None or [None])
        stimOutStr="["
        if self.params['trialList'].val not in [None, [None]]:
            for variable in sorted(self.params['trialList'].val[0].keys()):#get the keys for the first trial type
                stimOutStr+= "'%s', " %variable
        stimOutStr+= "]"
        if self.exp.settings.params['Save psydat file'].val:
            buff.writeIndented("%(name)s.saveAsPickle(filename+'%(name)s')\n" %self.params)
        if self.exp.settings.params['Save excel file'].val:
            buff.writeIndented("%(name)s.saveAsExcel(filename+'.xlsx', sheetName='%(name)s',\n" %self.params)
            buff.writeIndented("    stimOut=%s,\n" %stimOutStr)
            buff.writeIndented("    dataOut=['n','all_mean','all_std', 'all_raw'])\n")
        if self.exp.settings.params['Save csv file'].val:
            buff.writeIndented("%(name)s.saveAsText(filename+'%(name)s.csv', delim=',',\n" %self.params)
            buff.writeIndented("    stimOut=%s,\n" %stimOutStr)
            buff.writeIndented("    dataOut=['n','all_mean','all_std', 'all_raw'])\n")
    def getType(self):
        return 'TrialHandler'
    
class StairHandler:
    """A staircase experimental control object.
    """
    def __init__(self, exp, name, nReps='50', startVal='', nReversals='',
            nUp=1, nDown=3, minVal=0,maxVal=1,
            stepSizes='[4,4,2,2,1]', stepType='db', endPoints=[0,1]):
        """
        @param name: name of the loop e.g. trials
        @type name: string
        @param nReps: number of reps (for all trial types)
        @type nReps:int
        """
        self.type='StairHandler'
        self.exp=exp
        self.order=['name']#make name come first (others don't matter)
        self.params={}
        self.params['name']=Param(name, valType='code', hint="Name of this loop")
        self.params['nReps']=Param(nReps, valType='code',
            hint="(Minimum) number of trials in the staircase")
        self.params['start value']=Param(startVal, valType='num',
            hint="The initial value of the parameter")
        self.params['max value']=Param(maxVal, valType='num',
            hint="The maximum value the parameter can take")
        self.params['min value']=Param(minVal, valType='num',
            hint="The minimum value the parameter can take")
        self.params['step sizes']=Param(stepSizes, valType='num',
            hint="The size of the jump at each step (can change on each 'reversal')")
        self.params['step type']=Param(stepType, valType='str', allowedVals=['lin','log','db'],
            hint="The units of the step size (e.g. 'linear' will add/subtract that value each step, whereas 'log' will ad that many log units)")
        self.params['N up']=Param(nUp, valType='code',
            hint="The number of 'incorrect' answers before the value goes up")
        self.params['N down']=Param(nDown, valType='code',
            hint="The number of 'correct' answers before the value goes down")
        self.params['N reversals']=Param(nReversals, valType='code',
            hint="Minimum number of times the staircase must change direction before ending")
        #these two are really just for making the dialog easier (they won't be used to generate code)
        self.params['loopType']=Param('staircase', valType='str', 
            allowedVals=['random','sequential','staircase','interleaved stairs'],
            hint="How should the next trial value(s) be chosen?")#NB this is added for the sake of the loop properties dialog
        self.params['endPoints']=Param(endPoints,valType='num',
            hint='Where to loop from and to (see values currently shown in the flow view)')
    def writeInitCode(self,buff):
        #also a 'thisName' for use in "for thisTrial in trials:"
        self.thisName = self.exp.namespace.make_loop_index(self.params['name'].val)
        if self.params['N reversals'].val in ["", None, 'None']:
            self.params['N reversals'].val='0'
        #write the code
        buff.writeIndentedLines("\n#set up handler to look after randomisation of trials etc\n")
        buff.writeIndented("%(name)s=data.StairHandler(startVal=%(start value)s, extraInfo=expInfo,\n" %(self.params))
        buff.writeIndented("    stepSizes=%(step sizes)s, stepType=%(step type)s,\n" %self.params)
        buff.writeIndented("    nReversals=%(N reversals)s, nTrials=%(nReps)s, \n" %self.params)
        buff.writeIndented("    nUp=%(N up)s, nDown=%(N down)s,\n" %self.params)
        buff.writeIndented("    originPath=%s)\n" %repr(self.exp.expPath))
        buff.writeIndented("level=%s=%s#initialise some vals\n" %(self.thisName, self.params['start value']))
    def writeLoopStartCode(self,buff):
        #work out a name for e.g. thisTrial in trials:
        buff.writeIndented("\n")
        buff.writeIndented("for %s in %s:\n" %(self.thisName, self.params['name']))
        buff.setIndentLevel(1, relative=True)
        buff.writeIndented("currentLoop = %s\n" %(self.params['name']))
        buff.writeIndented("level=%s\n" %(self.thisName))
    def writeLoopEndCode(self,buff):
        buff.setIndentLevel(-1, relative=True)
        buff.writeIndented("\n")
        buff.writeIndented("#staircase completed\n")
        buff.writeIndented("\n")
        #save data
        if self.exp.settings.params['Save psydat file'].val:
            buff.writeIndented("%(name)s.saveAsPickle(filename+'%(name)s')\n" %self.params)
        if self.exp.settings.params['Save excel file'].val:
            buff.writeIndented("%(name)s.saveAsExcel(filename+'.xlsx', sheetName='%(name)s')\n" %self.params)
        if self.exp.settings.params['Save csv file'].val:
            buff.writeIndented("%(name)s.saveAsText(filename+'%(name)s.csv', delim=',')\n" %self.params)
    def getType(self):
        return 'StairHandler'
    
class MultiStairHandler:
    """To handle multiple interleaved staircases
    """
    def __init__(self, exp, name, nReps='50', stairType='simple', 
        switchStairs='random', 
        conditions=[], conditionsFile='', endPoints=[0,1]):
        """
        @param name: name of the loop e.g. trials
        @type name: string
        @param nReps: number of reps (for all trial types)
        @type nReps:int
        """
        self.type='MultiStairHandler'
        self.exp=exp
        self.order=['name']#make name come first
        self.params={}
        self.params['name']=Param(name, valType='code', hint="Name of this loop")
        self.params['nReps']=Param(nReps, valType='code',
            hint="(Minimum) number of trials in *each* staircase")
        self.params['stairType']=Param(nReps, valType='str', allowedVals=['simple','QUEST'],
            hint="How to select the next staircase to run")
        self.params['switchMethod']=Param(nReps, valType='str', allowedVals=['random','sequential'],
            hint="How to select the next staircase to run")
        #these two are really just for making the dialog easier (they won't be used to generate code)
        self.params['loopType']=Param('staircase', valType='str', 
        allowedVals=['random','sequential','staircase','interleaved stairs'],
            hint="How should the next trial value(s) be chosen?")#NB this is added for the sake of the loop properties dialog
        self.params['endPoints']=Param(endPoints,valType='num',
            hint='Where to loop from and to (see values currently shown in the flow view)')
        self.params['conditions']=Param(conditions, valType='str', updates=None, allowedUpdates=None,
            hint="A list of dictionaries describing the differences between each condition")
        self.params['trialListFile']=Param(conditionsFile, valType='str', updates=None, allowedUpdates=None,
            hint="An xlsx or csv file specifying the parameters for each condition")
    def writeInitCode(self,buff):
        #also a 'thisName' for use in "for thisTrial in trials:"
        self.thisName = self.exp.namespace.make_loop_index(self.params['name'].val)
        if self.params['N reversals'].val in ["", None, 'None']:
            self.params['N reversals'].val='0'
        #write the code
        buff.writeIndentedLines("\n#set up handler to look after randomisation of trials etc\n")
        buff.writeIndentedLines("conditions=data.importTrialList(%s)" %self.params['conditionsFile'])
        buff.writeIndented("%(name)s=data.MultiStairHandler(startVal=%(start value)s, extraInfo=expInfo,\n" %(self.params))
        buff.writeIndented("    nTrials=%(nReps)s,\n" %self.params)
        buff.writeIndented("    conditions=conditions,\n")
        buff.writeIndented("    originPath=%s)\n" %repr(self.exp.expPath))
        buff.writeIndented("#initialise values for first condition\n" %repr(self.exp.expPath))
        buff.writeIndented("level=%s._nextIntensity#initialise some vals\n" %(self.thisName))
        buff.writeIndented("condition=%s.currentStaircase.condition\n" %(self.thisName))
    def writeLoopStartCode(self,buff):
        #work out a name for e.g. thisTrial in trials:
        buff.writeIndented("\n")
        buff.writeIndented("for level, condition in %s:\n" %(self.thisName, self.params['name']))
        buff.setIndentLevel(1, relative=True)
        buff.writeIndented("currentLoop = %s\n" %(self.params['name']))
    def writeLoopEndCode(self,buff):
        buff.setIndentLevel(-1, relative=True)
        buff.writeIndented("\n")
        buff.writeIndented("#all staircases completed\n")
        buff.writeIndented("\n")
        #save data
        if self.exp.settings.params['Save psydat file'].val:
            buff.writeIndented("%(name)s.saveAsPickle(filename+'%(name)s')\n" %self.params)
        if self.exp.settings.params['Save excel file'].val:
            buff.writeIndented("%(name)s.saveAsExcel(filename+'.xlsx', sheetName='%(name)s')\n" %self.params)
        if self.exp.settings.params['Save csv file'].val:
            buff.writeIndented("%(name)s.saveAsText(filename+'%(name)s.csv', delim=',')\n" %self.params)
    def getType(self):
        return 'MultiStairHandler'
    
class LoopInitiator:
    """A simple class for inserting into the flow.
    This is created automatically when the loop is created"""
    def __init__(self, loop):
        self.loop=loop
        self.exp=loop.exp
    def writeInitCode(self,buff):
        self.loop.writeInitCode(buff)
    def writeMainCode(self,buff):
        self.loop.writeLoopStartCode(buff)
        self.exp.flow._loopList.append(self.loop)#we are now the inner-most loop
    def getType(self):
        return 'LoopInitiator'
    def writeExperimentEndCode(self,buff):#not needed
        pass
class LoopTerminator:
    """A simple class for inserting into the flow.
    This is created automatically when the loop is created"""
    def __init__(self, loop):
        self.loop=loop
        self.exp=loop.exp
    def writeInitCode(self,buff):
        pass
    def writeMainCode(self,buff):
        self.loop.writeLoopEndCode(buff)
        self.exp.flow._loopList.remove(self.loop)# _loopList[-1] will now be the inner-most loop
    def getType(self):
        return 'LoopTerminator'
    def writeExperimentEndCode(self,buff):#not needed
        pass
class Flow(list):
    """The flow of the experiment is a list of L{Routine}s, L{LoopInitiator}s and
    L{LoopTerminator}s, that will define the order in which events occur
    """
    def __init__(self, exp):
        list.__init__(self)
        self.exp=exp
        self._currentRoutine=None
        self._loopList=[]#will be used while we write the code
    def __repr__(self):
        return "psychopy.experiment.Flow(%s)" %(str(list(self)))
    def addLoop(self, loop, startPos, endPos):
        """Adds initiator and terminator objects for the loop
        into the Flow list"""
        self.insert(int(endPos), LoopTerminator(loop))
        self.insert(int(startPos), LoopInitiator(loop))
        self.exp.requirePsychopyLibs(['data'])#needed for TrialHandlers etc
    def addRoutine(self, newRoutine, pos):
        """Adds the routine to the Flow list"""
        self.insert(int(pos), newRoutine)
    def removeComponent(self,component,id=None):
        """Removes a Loop, LoopTerminator or Routine from the flow
        
        For a Loop (or initiator or terminator) to be deleted we can simply remove
        the object using normal list syntax. For a Routine there may be more than 
        one instance in the Flow, so either choose which one by specifying the id, or all
        instances will be removed (suitable if the Routine has been deleted).
        """
        if component.getType() in ['LoopInitiator', 'LoopTerminator']:
            component=component.loop#and then continue to do the next
        if component.getType() in ['StairHandler', 'TrialHandler']:
            #we need to remove the termination points that correspond to the loop
            for comp in self:
                if comp.getType() in ['LoopInitiator','LoopTerminator']:
                    if comp.loop==component: self.remove(comp)
        elif component.getType()=='Routine':
            if id==None: 
                #a Routine may come up multiple times - remove them all
                #self.remove(component)#cant do this - two empty routines (with diff names) look the same to list comparison
                for id, compInFlow in enumerate(self):
                    if hasattr(compInFlow, 'name') and component.name==compInFlow.name: del self[id]
            else: del self[id]#just delete the single entry we were given (e.g. from right-click in GUI)
    def writeCode(self, script):
        #initialise
        for entry in self: #NB each entry is a routine or LoopInitiator/Terminator
            self._currentRoutine=entry
            entry.writeInitCode(script)
        #run-time code
        for entry in self:
            self._currentRoutine=entry
            entry.writeMainCode(script)
        #tear-down code (very few components need this)
        for entry in self:
            self._currentRoutine=entry
            entry.writeExperimentEndCode(script)
    
class Routine(list):
    """
    A Routine determines a single sequence of events, such
    as the presentation of trial. Multiple Routines might be
    used to comprise an Experiment (e.g. one for presenting
    instructions, one for trials, one for debriefing subjects).

    In practice a Routine is simply a python list of Components,
    each of which knows when it starts and stops.
    """
    def __init__(self, name, exp, components=[]):
        self.params={'name':name}
        self.name=name
        self.exp=exp
        self._clockName=None#this is used for script-writing e.g. "t=trialClock.GetTime()"
        list.__init__(self, components)
    def __repr__(self):
        return "psychopy.experiment.Routine(name='%s',exp=%s,components=%s)" %(self.name,self.exp,str(list(self)))
    def addComponent(self,component):
        """Add a component to the end of the routine"""
        self.append(component)
    def removeComponent(self,component):
        """Remove a component from the end of the routine"""
        self.remove(component)
    def writeInitCode(self,buff):
        buff.writeIndented('\n')
        buff.writeIndented('#Initialise components for routine:%s\n' %(self.name))
        self._clockName = self.name+"Clock"
        buff.writeIndented('%s=core.Clock()\n' %(self._clockName))
        for thisEvt in self:
            thisEvt.writeInitCode(buff)

    def writeMainCode(self,buff):
        """This defines the code for the frames of a single routine
        """
        
        buff.writeIndentedLines("\n#update component parameters for each repeat\n")
        #This is the beginning of the routine, before the loop starts
        for event in self:
            event.writeRoutineStartCode(buff)
        
        #create the frame loop for this routine
        buff.writeIndentedLines('\n#run %s\n' %(self.name))
        buff.writeIndented('continueRoutine=True\n')
        buff.writeIndented('t=0; %s.reset()\n' %(self._clockName))
        
        maxtime = self.getMaxTime()
        if maxtime >= FOREVER:
            maxtime = 'FOREVER' # defined in the script by import psychopy.constants
        else:
            maxtime = '%.4f' % maxtime
        buff.writeIndented('while continueRoutine and (t<%s):\n' %(maxtime))
        buff.setIndentLevel(1,True)

        #write the code for each component during frame
        buff.writeIndentedLines('#update/draw components on each frame\n')
        for event in self:
            event.writeFrameCode(buff)

        #update screen
        buff.writeIndentedLines('\n#check for quit (the [Esc] key)\n')
        buff.writeIndented('if event.getKeys(["escape"]): core.quit()\n')
        buff.writeIndented('#refresh the screen\n')
        buff.writeIndented('win.flip()\n')

        #on each frame
        buff.writeIndented('\n#get current time\n')
        buff.writeIndented('t=%s.getTime()\n' %self._clockName)

        #that's done decrement indent to end loop
        buff.setIndentLevel(-1,True)

        #write the code for each component for the end of the routine
        buff.writeIndented('\n')
        buff.writeIndented('#end of this routine\n')
        for event in self:
            event.writeRoutineEndCode(buff)

    def writeExperimentEndCode(self,buff):
        """This defines the code for the frames of a single routine
        """
        #This is the beginning of the routine, before the loop starts
        for component in self:
            component.writeExperimentEndCode(buff)
    def getType(self):
        return 'Routine'
    def getComponentFromName(self, name):
        for comp in self:
            if comp.params['name']==name:
                return comp
        return None
    def getMaxTime(self):
        maxTime=0
        times=[]
        for event in self:
            if 'startTime' not in event.params.keys(): continue
            if event.params['duration'].val in ['-1', ''] \
                or '$' in [event.params['startTime'].val[0], event.params['duration'].val[0]]:
                maxTime=FOREVER
            else:
                exec("maxTime=%(startTime)s+%(duration)s" %(event.params))#convert params['duration'].val into numeric
            times.append(maxTime)
            maxTime=float(max(times))
        return maxTime
    
class NameSpace():
    """class for managing variable names in builder-constructed experiments.
    
    The aim is to help detect and avoid name-space collisions from user-entered variable names.
    Track four groups of variables:
        numpy =    part of numpy or numpy.random (maybe its ok for a user to redefine these?)
        psychopy = part of psychopy, such as event or data; include os here
        builder =  used internally by the builder when constructing an experiment
        user =     used 'externally' by a user when programming an experiment
    Some vars, like core, are part of both psychopy and numpy, so the order of operations can matter
    
    Notes for development:
    are these all of the ways to get into the namespace?
    - import statements at top of file: numpy, psychopy, os, etc
    - a handful of things that always spring up automatically, like t and win
    - routines: user-entered var name = routine['name'].val, plus sundry helper vars, like theseKeys
    - flow elements: user-entered = flowElement['name'].val
    - routine & flow from either GUI or .psyexp file
    - each routine and flow element potentially has a ._clockName,
        loops have thisName, albeit thisNam (missing end character)
    - column headers in condition files
    - abbreviating parameter names (e.g. rgb=thisTrial.rgb)
    
    TO DO (throughout app):
        trialLists on import
        how to rename routines? seems like: make a contextual menu with 'remove', which calls DlgRoutineProperties
        staircase resists being reclassified as trialhandler
    
    :Author:
        2011 Jeremy Gray
    """
    def __init__(self, exp):
        """ set-up a given experiment's namespace: known reserved words, plus empty 'user' space list"""
        self.exp = exp
        #deepcopy fails if you pre-compile regular expressions and stash here
        
        self.numpy = list(set(dir(numpy) + dir(numpy.random))) # remove some redundancies
        self.keywords = ['and', 'del', 'from', 'not', 'while', 'as', 'elif', 'global', 'or',
                        'with', 'assert', 'else', 'if', 'pass', 'yield', 'break', 'except',
                        'import', 'print', 'class', 'exec', 'in', 'raise', 'continue', 'finally',
                        'is', 'return', 'def', 'for', 'lambda', 'try',
                        
                         'abs', 'all', 'any', 'apply', 'basestring', 'bin', 'bool', 'buffer',
                         'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'cmp', 'coerce',
                         'compile', 'complex', 'copyright', 'credits', 'delattr', 'dict', 'dir',
                         'divmod', 'enumerate', 'eval', 'execfile', 'exit', 'file', 'filter',
                         'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash',
                         'help', 'hex', 'id', 'input', 'int', 'intern', 'isinstance', 'issubclass',
                         'iter', 'len', 'license', 'list', 'locals', 'long', 'map', 'max', 'memoryview',
                         'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property',
                         'quit', 'range', 'raw_input', 'reduce', 'reload', 'repr', 'reversed', 'round',
                         'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super',
                         'tuple', 'type', 'unichr', 'unicode', 'vars', 'xrange', 'zip',
                         'clear', 'copy', 'fromkeys', 'get', 'has_key', 'items', 'iteritems', 'iterkeys',
                         'itervalues', 'keys', 'pop', 'popitem', 'setdefault', 'update', 'values',
                         'viewitems', 'viewkeys', 'viewvalues',
                         
                         '__builtins__', '__doc__', '__file__', '__name__', '__package__']
        # these are based on a partial test, known to be incomplete:
        self.psychopy = ['psychopy', 'os', 'core', 'data', 'visual', 'event', 'gui']
        self.builder = ['KeyResponse', 'buttons', 'continueTrial', 'dlg', 'expInfo', 'expName', 'filename',
            'logFile', 't', 'theseKeys', 'win', 'x', 'y', 'level']
        # user-entered, from Builder dialog or conditions file:
        self.user = []
    
    def __str__(self, numpy_count_only=True):
        vars = self.user + self.builder + self.psychopy
        if numpy_count_only:
            return "%s + [%d numpy]" % (str(vars), len(self.numpy))
        else:
            return str(vars + self.numpy)
    
    def get_derived(self, basename):
        """ buggy
        idea: return variations on name, based on its type, to flag name that will come to exist at run-time;
        more specific than is_possibly-derivable()
        if basename is a routine, return continueBasename and basenameClock,
        if basename is a loop, return make_loop_index(name)
        """
        derived_names = []
        for flowElement in self.exp.flow:
            if flowElement.getType() in ['LoopInitiator','LoopTerminator']:
                flowElement=flowElement.loop  # we want the loop itself
                # basename can be <type 'instance'>
                derived_names += [self.make_loop_index(basename)]
            if basename == str(flowElement.params['name']) and basename+'Clock' not in derived_names:
                derived_names += [basename+'Clock', 'continue'+basename.capitalize()]
        # other derived_names?
        # 
        return derived_names 
    
    def get_collisions(self):
        """return None, or a list of names in .user that are also in one of the other spaces"""
        duplicates = list(set(self.user).intersection(set(self.builder + self.psychopy + self.numpy)))
        su = sorted(self.user)
        duplicates += [var for i,var in enumerate(su) if i<len(su)-1 and su[i+1] == var] 
        if duplicates != []:
            return duplicates
        return None
    
    def is_valid(self, name):
        """var-name compatible? return True if string name is alphanumeric + underscore only, with non-digit first"""
        return bool(_valid_var_re.match(name))
    def is_possibly_derivable(self, name):
        """catch all possible derived-names, regardless of whether currently"""
        derivable = name.startswith('this') or name.startswith('continue') or name.endswith('Clock')
        derivable = derivable or name.startswith('these')
        return derivable
    def exists(self, name): 
        """returns None, or a message indicating where the name is in use.
        cannot guarantee that a name will be conflict-free.
        does not check whether the string is a valid variable name.
        
        >>> exists('t')
        Builder variable
        """
        try: name = str(name) # convert from unicode if possible
        except: pass
        
        # check get_derived:
        
        # check in this order:
        if name in self.user: return "script variable"
        if name in self.builder: return "Builder variable"
        if name in self.psychopy: return "Psychopy module"
        if name in self.numpy: return "numpy function"
        if name in self.keywords: return "python keyword"
        
        return # None, meaning does not exist already
    
    def add(self, name, sublist='default'):
        """add name to namespace by appending a name or list of names to a sublist, eg, self.user"""
        if name is None: return
        if sublist == 'default': sublist = self.user
        if type(name) != list:
            sublist.append(name)
        else:
            sublist += name
        
    def remove(self, name, sublist='default'):
        """remove name from the specified sublist (and hence from the name-space), eg, self.user"""
        if name is None: return
        if sublist == 'default': sublist = self.user
        if type(name) != list:
            name = [name]
        for n in list(name):
            if n in sublist:
                del sublist[sublist.index(n)]
        
    def make_valid(self, name, prefix='var', add_to_space=None):
        """given a string, return a valid and unique variable name.
        replace bad characters with underscore, add an integer suffix until its unique
        
        >>> make_valid('t')
        't_1'
        >>> make_valid('Z Z Z')
        'Z_Z_Z'
        >>> make_valid('a')
        'a'
        >>> make_valid('a')
        'a_1'
        >>> make_valid('a')
        'a_2'
        >>> make_valid('123')
        'var_123'
        """
        
        # make it legal:
        try: name = str(name) # convert from unicode, flag as uni if can't convert
        except: prefix = 'uni'
        if not name: name = prefix+'_1'
        if name[0].isdigit():
            name = prefix+'_' + name
        name = _nonalphanumeric_re.sub('_', name) # replace all bad chars with _
        
        # try to make it unique; success depends on accuracy of self.exists():
        i = 2
        if self.exists(name) and name.find('_') > -1: # maybe it already has _\d+? if so, increment from there
            basename, count = name.rsplit('_', 1)
            try:
                i = int(count)
                name = basename
            except:
                pass
        name_orig = name + '_'
        while self.exists(name): # brute-force a unique name
            name = name_orig + str(i)
            i += 1
        if add_to_space:
            self.add(name, add_to_space)
        return name

    def make_loop_index(self, name):
        """return a valid, readable loop-index name: 'this' + (plural->singular).capitalize() [+ (_\d+)]"""
        try: new_name = str(name)
        except: new_name = name
        prefix = 'this'
        irregular = {'stimuli': 'stimulus', 'mice': 'mouse', 'people': 'person'}
        for plural, singular in irregular.items():
            nn = re.compile(plural, re.IGNORECASE)
            new_name = nn.sub(singular, new_name)
        if new_name.endswith('s') and not new_name.lower() in irregular.values():
            new_name = new_name[:-1] # trim last 's'
        else: # might end in s_2, so delete that s; leave S
            match = re.match(r"^(.*)s(_\d+)$", new_name)
            if match: new_name = match.group(1) + match.group(2)
        new_name = prefix + new_name[0].capitalize() + new_name[1:] # retain CamelCase
        new_name = self.make_valid(new_name)
        return new_name
            
def _XMLremoveWhitespaceNodes(parent):
    """Remove all text nodes from an xml document (likely to be whitespace)
    """
    for child in list(parent.childNodes):
        if child.nodeType==node.TEXT_NODE and node.data.strip()=='':
            parent.removeChild(child)
        else:
            removeWhitespaceNodes(child)
