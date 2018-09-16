#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Part of the PsychoPy library
# Copyright (C) 2018 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

#item groups
multichoice = ['rating','likert']

import surveys #seems easier to create for every experiment, even if it's empty, to allow adding of surveys by name
surveys.initialize()


from psychopy.visual.basevisual import (BaseVisualStim,
                                        ContainerMixin, ColorMixin)
from psychopy import visual

import pandas as pd #need this for managing data frame?
import math

class Form(BaseVisualStim, ContainerMixin, ColorMixin): #VisualComponent
    """A class to add Forms to a `psycopy.visual.Window`

    The Form allows Psychopy to be used as a questionnaire tool, where
    participants can be presented with a series of questions requiring responses.
    Form items, defined as questions and response pairs, are presented
    simultaneously onscreen with a scrollable viewing window.

    Example
    -------
    survey = Form(win, excelFile='AQ.xlsx', size=(1, 1), pos=(0.0, 0.0),name="first")

    Parameters
    ----------
    win : psychopy.visual.Window
        The window object to present the form.
    items : List of dicts
        a list of dicts with the following key, value pairs:
                 "qText": item question string,
                 "qWidth": question width between 0:1
                 "aType": type of rating e.g., 'choice', 'rating', 'slider'
                 "aWidth": question width between 0:1,
                 "aOptions": list of tick labels for options,
                 "aLayout": Response object layout e.g., 'horiz' or 'vert'
    textHeight : float
        Text height.
    size : tuple, list
        Size of form on screen.
    pos : tuple, list
        Position of form on screen.
    itemPadding : float
        Space or padding between form items.
    units : str
        units for stimuli, e.g., 'height', 'norm', 'pixels' etc.
    """

    def __init__(self,
                 win,
                 name,
                 excelFile,
                 #items,
                 textHeight=.03,
                 size=(.5, .5),
                 pos=(0, 0),
                 itemPadding=0.05,
                 units='height',
                 ):

        super(Form, self).__init__(win, units)
        self._baseYpositions = []
        self._items = {'question': [], 'response': []}
        self._scrollOffset = 0
        self.excelFile = excelFile
        self.items = 'tbc'
        self.itemPadding = itemPadding
        self.labelHeight = 0.02
        self.leftEdge = None
        self.name = name
        self.pos = pos
        self.rightEdge = None
        self.size = size
        self.textHeight = textHeight
        self.topEdge = None
        self.units = units
        self.virtualHeight = 0  # Virtual height determines pos from boundary box
        self.win = win

        self.loadExcel()



    def loadExcel(self):
        questions = []

        ## initiate this survey
        surveys.content[self.name] = {
            "items": {},
            "scoring": {}
        }

        my_data = pd.read_excel(self.excelFile)
        my_data.columns = map(str.lower, my_data.columns)

        ## add each scoring column
        scoringCols = list(filter(lambda x: "score:" in x, my_data.columns))


        for scoringCol in scoringCols:
            surveys.content[self.name]["scoring"][scoringCol] = {
                "items":{},
                "total":0
            }
            for i in range(len(my_data["item_name"])):
                thisScoreCode = my_data[scoringCol][i]
                print(thisScoreCode)
                thisItemName = my_data["item_name"][i]
                if isinstance(thisScoreCode,str):
                    print("hi")
                    surveys.content[self.name]["scoring"][scoringCol]["items"][thisItemName] = {
                        "code": thisScoreCode,
                        "value": 0
                    }
                elif math.isnan(thisScoreCode) == False:
                    print("ho")
                    surveys.content[self.name]["scoring"][scoringCol]["items"][thisItemName ] = {
                        "code" :thisScoreCode,
                        "value":0
                    }

        for i in range(len(my_data["item_name"])):
            thisItemName = my_data["item_name"][i]
            surveys.content[self.name]["items"][thisItemName] = {
                "optional" : my_data["optional"][i],
                "response":"",
                "value":"",
                "answers":my_data["answers"][i],
                "answerValues": my_data["values"][i]
            }


            if (my_data["type"][i].lower() == "button"):
                thisItem = {"qText": my_data["text"][i],
                            "qName": thisItemName,
                            "qWidth": .5,
                            "aType": my_data["type"][i],
                            "aWidth": 0,
                            "aOptions": my_data["answers"][i]  # .split("|")
                            }
                questions.append(thisItem)

            if (my_data["type"][i].lower() == "instruct"):
                thisItem = {"qText": my_data["text"][i],
                            "qName": self.name + "|" + thisItemName,
                            "qWidth": 1,
                            "aType": my_data["type"][i],
                            "aWidth": 0,
                            "aOptions": "tbc",  # my_data["answers"][i] #.split("|")
                            "aLayout": 'horiz'
                            }
                questions.append(thisItem)
            if (my_data["type"][i].lower() in multichoice):
                thisItem = {"qText": my_data["text"][i],
                            "qName": self.name + "|" + thisItemName,
                            "qWidth": .5,
                            "aType": my_data["type"][i],
                            "aWidth": .5,
                            "aOptions": my_data["answers"][i],
                            "aLayout": 'vert'
                            }
                questions.append(thisItem)
            if (my_data["type"][i].lower() == "radio"):
                thisItem = {"qText": my_data["text"][i],


                            "qName": self.name + "|" + thisItemName,
                            #make use of this to be able to name the radio buttons appropriately!



                            "qWidth": .7,
                            "aType": my_data["type"][i],
                            "aWidth": .3,
                            "aOptions": my_data["answers"][i].split("|"),
                            "aLayout": 'vert'
                            }
                questions.append(thisItem)

            if (my_data["type"][i].lower() == "slider"):
                thisItem = {"qText": my_data["text"][i],
                            "qName": self.name + "|" + thisItemName,
                            "qWidth": .7,
                            "aType": my_data["type"][i],
                            "aWidth": .3,
                            "aOptions": my_data["answers"][i].split("|"),
                            "aLayout": 'horiz'
                            }
                questions.append(thisItem)
        self.items = questions
        print(surveys.content)
        self._doLayout()

    def _setQuestion(self, item):
        """Creates TextStim object containing question

        Returns
        -------
        psychopy.visual.text.TextStim
            The textstim object with the question string
        qHeight
            The height of the question bounding box as type float
        qWidth
            The width of the question bounding box as type float
        """

        if (item['aType'] == "instruct"):
            question_color = "blue"
        else:
            question_color = "black"

        question = visual.TextStim(self.win,
                                   text=item['qText'],
                                   units=self.units,
                                   height=self.textHeight,
                                   alignHoriz='left',
                                   color = question_color,
                                   wrapWidth=item['qWidth'] * self.size[0])

        qHeight = self.getQuestionHeight(question)
        qWidth = self.getQuestionWidth(question)
        self._items['question'].append(question)

        return question, qHeight, qWidth

    def _setResponse(self, item, question):
        """Creates slider object for responses

        Returns
        -------
        psychopy.visual.slider.Slider
            The Slider object for response
        aHeight
            The height of the response object as type float
        """
        pos = (self.rightEdge - item['aWidth'] * self.size[0], question.pos[1])
        aHeight = self.getRespHeight(item)

        # Set radio button choice layout
        if item['aLayout'] == 'horiz':
            aSize = (item['aWidth'] * self.size[0], 0.03)
        elif item['aLayout'] == 'vert':
            aSize = (0.03, aHeight)


        if item['aType'].lower() in ['instruct']:

            #below does nothing except stop the code breaking
            resp = visual.Slider(self.win,
                                 pos=pos,
                                 size=(item['aWidth'] * self.size[0], 0.03),
                                 #ticks=[0, 1],
                                 #labels=item['aOptions'],
                                 units=self.units,
                                 labelHeight=self.labelHeight,
                                 flip=True)

        if item['aType'].lower() in ['slider']: #'rating',
            resp = visual.Slider(self.win,
                                 pos=pos,
                                 name=item["qName"],
                                 size=(item['aWidth'] * self.size[0], 0.03),
                                 ticks=[0, 1],
                                 color='blue',
                                 labels=item['aOptions'],
                                 units=self.units,
                                 labelHeight=self.labelHeight,
                                 flip=True)
        elif item['aType'].lower() in ['radio']:
            resp = visual.Slider(self.win,
                                 pos=pos,
                                 name=item["qName"],
                                 size=aSize,
                                 color='blue',
                                 ticks=None,
                                 labels=item['aOptions'],
                                 units=self.units,
                                 labelHeight=self.textHeight,
                                 style='radio',
                                 flip=True)

        self._items['response'].append(resp)
        return resp, aHeight

    def getQuestionHeight(self, question=None):
        """Takes TextStim and calculates height of bounding box

        Returns
        -------
        float
            The height of the question bounding box
        """
        return question.boundingBox[1] / float(self.win.size[1] / 2)

    def getQuestionWidth(self, question=None):
        """Takes TextStim and calculates width of bounding box

        Returns
        -------
        float
            The width of the question bounding box
        """
        return question.boundingBox[0] / float(self.win.size[0] / 2)

    def getRespHeight(self, item):
        """Takes list and calculates height of answer

        Returns
        -------
        float
            The height of the response object
        """
        if item['aLayout'] == 'vert':
            aHeight = len(item['aOptions']) * self.textHeight
        elif item['aLayout'] == 'horiz':
           aHeight = self.textHeight

        # TODO: Return size based on response types e.g., textbox
        return aHeight

    def _setScrollBar(self):
        """Creates Slider object for scrollbar

        Returns
        -------
        psychopy.visual.slider.Slider
            The Slider object for scroll bar
        """
        return visual.Slider(win=self.win, size=(0.03, self.size[1]),
                             ticks=[0, 1], style='slider',
                             pos=(self.rightEdge, self.pos[1]))

    def _setBorder(self):
        """Creates border using Rect
        Returns
        -------
        psychopy.visual.Rect
            The border for the survey
        """
        return visual.Rect(win=self.win, units=self.units, pos=self.pos,
                           width=self.size[0], height=self.size[1])

    def _setAperture(self):
        """Blocks text beyond border using Aperture

        Returns
        -------
        psychopy.visual.Aperture
            The aperture setting viewable area for forms
        """
        return visual.Aperture(win=self.win, name='aperture',
                               units=self.units, shape='square',
                               size=self.size, pos=(0, 0))
    def _getScrollOffet(self):
        """Calculate offset position of items in relation to markerPos

        Returns
        -------
        float
            Offset position of items proportionate to scroll bar
        """
        sizeOffset = (1 - self.scrollbar.markerPos) * (self.size[1]-self.itemPadding)
        maxItemPos = min(self._baseYpositions)
        return (maxItemPos - (self.scrollbar.markerPos * maxItemPos) + sizeOffset)

    def _doLayout(self):
        """Define layout of form"""
        # Define boundaries of form
        self.leftEdge = self.pos[0] - self.size[0]/2.0
        self.rightEdge = self.pos[0] + self.size[0]/2.0
        self.topEdge = self.pos[1] + self.size[1]/2.0


        # For each question, create textstim and rating scale
        for item in self.items:
            # set up the question text
            if ('aLayout' not in item): #assume horizontal if not stated
                item['aLayout'] = "horiz"

            question, qHeight, qWidth = self._setQuestion(item)
            # Position text relative to boundaries defined according to position and size
            question.pos = (self.leftEdge,
                            self.topEdge
                            + self.virtualHeight
                            - qHeight/2 - self.itemPadding)
            response, aHeight, = self._setResponse(item, question)
            # Calculate position of question based on larger qHeight vs aHeight.
            self._baseYpositions.append(self.virtualHeight
                                        - max(aHeight, qHeight)  # Positionining based on larger of the two
                                        + (aHeight/2)            # necessary to offset size-based positioning
                                        - self.textHeight)       # Padding for unaccounted marker size in slider height
            # update height ready for next row
            self.virtualHeight -= max(aHeight, qHeight) + self.itemPadding

        # position a slider on right-hand edge
        self.scrollbar = self._setScrollBar()
        self.scrollbar.markerPos = 1  # Set scrollbar to start position
        self.border = self._setBorder()
        self.aperture = self._setAperture()

    def _inRange(self, item):
        """Check whether item position falls within border area

        Parameters
        ----------
        item : TextStim, Slider object
            TextStim or Slider item from survey

        Returns
        -------
        bool
            Returns True if item position falls within border area
        """
        upperRange = self.size[1]/2
        lowerRange = -self.size[1]/2
        return (item.pos[1] < upperRange and item.pos[1] > lowerRange)

    def draw(self):
        """Draw items on form within border area"""
        decorations = [self.border]  # add scrollbar if it's needed
        fractionVisible = self.size[1]/(-self.virtualHeight)
        if fractionVisible < 1.0:
            decorations.append(self.scrollbar)

        # draw the box and scrollbar
        for decoration in decorations:
            decoration.draw()
        self.aperture.enable()

        # draw the items
        for element in self._items.keys():
            for idx, items in enumerate(self._items[element]):
                items.pos = (items.pos[0], self.size[1]/2 + self._baseYpositions[idx] - self._getScrollOffet())
                # Only draw if within border range for efficiency
                if self._inRange(items):
                    items.draw()


if __name__ == "__main__":

    # create window and display
    win = visual.Window(units='height', allowStencil=True)
    print(win.backend.shadersSupported, win._haveShaders)
    title = visual.TextStim(win, "My test survey", units='height', pos=[0,0.45])

    survey = Form(win, excelFile='AQ.xlsx', size=(1, 1), pos=(0.0, 0.0),name="first")



    for n in range(600):
        survey.draw()
        win.color = [255, 255, 255]  # clear blue in rgb255
        win.flip()
