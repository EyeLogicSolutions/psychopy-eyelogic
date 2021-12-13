#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from psychopy.colors import Color
from psychopy.tests.test_all_visual.test_basevisual import _TestColorMixin
from psychopy.visual.window import Window
from psychopy.visual.slider import Slider
from psychopy.visual.grating import GratingStim
from psychopy.visual.elementarray import ElementArrayStim
from psychopy.visual.shape import ShapeStim
from psychopy.visual.rect import Rect
from psychopy import constants
from numpy import array_equal
import random


class Test_Slider(_TestColorMixin):
    def setup_class(self):
        self.win = Window([128,128], pos=[50,50], monitor="testMonitor", allowGUI=False,
                          autoLog=False)
        self.obj = Slider(self.win, units="height", size=(1, 0.1), pos=(0, 0.5), style='radio')
        self.obj.markerPos = 1

        # Pixel which is the border color
        self.borderPoint = (0, 127)
        self.borderUsed = True
        # Pixel which is the fill color
        self.fillPoint = (0, 0)
        self.fillUsed = True
        # Pixel which is the fore color
        self.forePoint = (0, 0)
        self.foreUsed = False

    def teardown_class(self):
        self.win.close()

    def test_horiz(self):
        # Define cases
        exemplars = [
            {'size': (1, 0.1), 'ori': 0, 'horiz': True},  # Wide slider, no rotation
            {'size': (0.1, 1), 'ori': 0, 'horiz': False},  # Tall slider, no rotation
            {'size': (1, 0.1), 'ori': 90, 'horiz': False},  # Wide slider, 90deg rotation
            {'size': (0.1, 1), 'ori': 90, 'horiz': True},  # Tall slider, 90deg rotation
        ]
        tykes = [
            {'size': (1, 0.1), 'ori': 25, 'horiz': True},  # Wide slider, accute rotation
            {'size': (0.1, 1), 'ori': 25, 'horiz': False},  # Tall slider, accute rotation
            {'size': (1, 0.1), 'ori': 115, 'horiz': False},  # Wide slider, obtuse rotation
            {'size': (0.1, 1), 'ori': 115, 'horiz': True},  # Tall slider, obtuse rotation
        ]
        # Try each case
        for case in exemplars + tykes:
            obj = Slider(self.win, size=case['size'], ori=case['ori'])
            assert obj.horiz == case['horiz']

    def test_reset(self):
        s = Slider(self.win, size=(1, 0.1))
        s.markerPos = 1
        s.history = [1]
        s.rating = 1
        s.rt = 1
        s.status = constants.STARTED
        s.reset()
        assert s.markerPos == None
        assert s.history == []
        assert s.rating == None
        assert s.rt == None
        assert s.status == constants.NOT_STARTED

    def test_elements(self):
        s = Slider(self.win, size=(1, 0.1))
        assert type(s.line) == type(Rect(self.win))
        assert type(s.tickLines) == type(ElementArrayStim(self.win))
        assert type(s.marker) == type(ShapeStim(self.win))
        assert type(s.validArea) == type(Rect(self.win))
        
    def test_pos(self):
        s = Slider(self.win, size=(1, 0.1))
        positions = [(.05, .05),(0.2, .2)]
        for newPos in positions:
            s.pos = newPos
            assert array_equal(s.pos, newPos)
        
    def test_ratingToPos(self):
        s = Slider(self.win, size=(1, 0.1), )
        assert s._ratingToPos(3)[0] == 0
        assert s._ratingToPos(1)[0] == -.5
        assert s._ratingToPos(5)[0] == .5

    def test_posToRatingToPos(self):
        s = Slider(self.win, size=(1, 0.1), )
        assert s._posToRating((0, 0)) == 3
        assert s._posToRating((-.5, 0)) == 1
        assert s._posToRating((.5, 0)) == 5

    def test_tickLocs(self):
        s = Slider(self.win, size=(1, 0.1), )
        assert s.tickParams['xys'][0][0] == -.5 and s.tickParams['xys'][0][1] == 0.0
        assert s.tickParams['xys'][1][0] == -.25 and s.tickParams['xys'][1][1] == 0.0
        assert s.tickParams['xys'][2][0] == .0 and s.tickParams['xys'][2][1] == 0.0
        assert s.tickParams['xys'][3][0] == .25 and s.tickParams['xys'][3][1] == 0.0
        assert s.tickParams['xys'][4][0] == .5 and s.tickParams['xys'][4][1] == 0.0

    def test_labelLocs(self):
        s = Slider(self.win, size=(1, 0.1), labels=('a','b','c','d','e'))
        assert s.labelParams['pos'][0, 0] == -.5 and s.labelParams['pos'][0, 1] == 0
        assert s.labelParams['pos'][1, 0] == -.25 and s.labelParams['pos'][1, 1] == 0
        assert s.labelParams['pos'][2, 0] == .0 and s.labelParams['pos'][2, 1] == 0
        assert s.labelParams['pos'][3, 0] == .25 and s.labelParams['pos'][3, 1] == 0
        assert s.labelParams['pos'][4, 0] == .5 and s.labelParams['pos'][4, 1] == 0

    def test_granularity(self):
        s = Slider(self.win, size=(1, 0.1), granularity=1)
        minRating, maxRating = 1, 5

        assert s.granularity == 1
        assert s._granularRating(1) == minRating
        assert s._granularRating(5) == maxRating
        assert s._granularRating(0) == minRating
        assert s._granularRating(6) == maxRating

    def test_rating(self):
        s = Slider(self.win, size=(1, 0.1))
        minRating, maxRating = 1, 5

        s.rating = 1
        assert s.rating == minRating
        s.rating = 5
        assert s.rating == maxRating
        s.rating = 0
        assert s.rating == minRating
        s.rating = 6
        assert s.rating == maxRating

    def test_markerPos(self):
        s = Slider(self.win, size=(1, 0.1))
        s._updateMarkerPos = False
        minPos, maxPos = 1, 5

        assert s._updateMarkerPos != True
        s.markerPos = 1
        assert s.markerPos == minPos
        s.markerPos = 5
        assert s.markerPos == maxPos
        s.markerPos = 0
        assert s.markerPos == minPos
        s.markerPos = 6
        assert s.markerPos == maxPos
        assert s._updateMarkerPos == True

    def test_recordRating(self):
        s = Slider(self.win, size=(1, 0.1))
        minRating, maxRating = 1, 5

        counter = 0
        for rates in range(0,7):
            s.recordRating(rates, random.random())
            counter +=1

        ratings = [rating[0] for rating in s.history]
        RT = [rt[1] for rt in s.history]

        assert len(s.history) == counter
        assert len(ratings) == counter
        assert min(ratings) == minRating
        assert max(ratings) == maxRating
        assert len(RT) == counter
        assert max(RT) <= 1
        assert min(RT) >= 0

    def test_getRating(self):
        s = Slider(self.win, size=(1, 0.1))
        minRating, maxRating = 1, 5
        s.rating = 1
        assert s.getRating() == minRating
        s.rating = 5
        assert s.getRating() == maxRating
        s.rating = 0
        assert s.getRating() == minRating
        s.rating = 6
        assert s.getRating() == maxRating

    def test_getRT(self):
        s = Slider(self.win, size=(1, 0.1))
        testRT = .89
        s.recordRating(2, testRT)
        assert s.history[-1][1] == s.getRT()
        assert type(s.getRT()) == float
        assert s.getRT() == testRT
