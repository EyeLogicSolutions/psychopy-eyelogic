
from psychopy.visual import RatingScale, Window
from psychopy import event, core
from psychopy.constants import *
import pytest
import shutil
from tempfile import mkdtemp

"""define RatingScale configurations, test the logic

    do some .draw() but not visual tests
    ~95%+ coverage, miss code that is conditional on mouse events
"""

@pytest.mark.ratingscale
class Test_class_RatingScale:
    """RatingScale internal logic, no check that its drawn correctly
    """
    def setup_class(self):
        self.temp_dir = mkdtemp(prefix='psychopy-tests-test_window')
        self.win = Window([128,128], pos=[50,50], allowGUI=False)
        self.winpix = Window([128,128], pos=[50,50], allowGUI=False, units='pix')

    def teardown_class(self):
        shutil.rmtree(self.temp_dir)

    def test_init_scales(self):
        # give non-default values for all params

        r = RatingScale(self.win)
        r = RatingScale(self.win, low=0, high=1000)
        r = RatingScale(self.win, low='a', high='s')
        assert r.low == 1
        assert r.high == 2
        r = RatingScale(self.win, low=10, high=2)
        assert r.high == r.low + 1
        assert r.precision == 100

        r = RatingScale(self.win, scale='scale')
        r = RatingScale(self.win, choices=['a', 'b'])
        r = RatingScale(self.win, choices=['a', 'b'], precision=10)
        assert r.precision == 1
        r = RatingScale(self.win, lowAnchorText=1, highAnchorText='a lot')
        r = RatingScale(self.win, tickMarks=[1,2,3])
        r = RatingScale(self.win, tickMarks=[1,2,3], labels=['a','b'])

        r = RatingScale(self.win, labels=['a', 'b'])
        for i in [0, 1, 10, 100, 1000, 0.3]:
            r = RatingScale(self.win, precision=i)
        r = RatingScale(self.win, textSizeFactor=3, textColor=0.3)
        r = RatingScale(self.win, textFont='Helvetica')
        r = RatingScale(self.win, showValue=False)
        r = RatingScale(self.win, showScale=False)
        r = RatingScale(self.win, showAnchors=False)
        r = RatingScale(self.win, showAccept=False, acceptKeys=[])
        r = RatingScale(self.win, showAccept=False, mouseOnly=True, singleClick=False)
        assert r.mouseOnly == False
        r = RatingScale(self.win, acceptKeys='a')
        r = RatingScale(self.win, acceptKeys=['a','b'])
        r = RatingScale(self.win, acceptPreText='a')
        r = RatingScale(self.win, acceptText='a')
        r = RatingScale(self.win, acceptSize=2.1)

        r = RatingScale(self.win, leftKeys=['a'])
        r = RatingScale(self.win, rightKeys=['a'])
        r = RatingScale(self.win, respKeys=['a'])
        r = RatingScale(self.win, lineColor='Black')

        r = RatingScale(self.win, ticksAboveLine=False)
        r = RatingScale(self.win, markerStart=3)
        r = RatingScale(self.win, markerStart='a', choices=['a','b'])

        r = RatingScale(self.win, markerColor='dark red')
        r = RatingScale(self.win, markerExpansion=10)
        r = RatingScale(self.win, markerStyle='glow', markerExpansion=0, displaySizeFactor=2)
        r.markerPlaced = True
        r.markerExpansion = 10
        r.draw()

        r = RatingScale(self.win, escapeKeys=['space'])
        r = RatingScale(self.win, allowSkip=False)
        r = RatingScale(self.win, mouseOnly=True, singleClick=True)
        r = RatingScale(self.win, displaySizeFactor=.2, stretchHoriz=2)
        r = RatingScale(self.win, pos=(0,.5), skipKeys='space')

        r = RatingScale(self.winpix, pos=['a','x'])
        r = RatingScale(self.winpix, pos=(1, 2))
        assert r.offsetHoriz == 2./r.win.size[0]
        assert r.offsetVert == 4. / r.win.size[1]

        r = RatingScale(self.win, stretchHoriz='foo')
        assert r.stretchHoriz == 1
        r = RatingScale(self.win, displaySizeFactor='foo')
        assert r.displaySizeFactor == 0.6

        r = RatingScale(self.win, minTime=0.001, maxTime=1)
        r = RatingScale(self.win, minTime='x', maxTime='s')
        r = RatingScale(self.win, name='name', autoLog=False)

        for marker in ['triangle', 'glow', 'slider', 'circle']:
            r = RatingScale(self.win, markerStyle=marker)

        class customMarker(object):
            def __init__(self):
                self.color = None
                self.fillColor = 1
            def draw(self): pass
            def setPos(self, *args, **kwargs): pass
        cm = customMarker()
        r = RatingScale(self.win, customMarker=cm)
        del cm.color
        r = RatingScale(self.win, customMarker=cm)
        del cm.fillColor
        r = RatingScale(self.win, customMarker=cm)

        class customMarker2(object):
            def __init__(self): pass
        r = RatingScale(self.win, customMarker=customMarker2())

        r = RatingScale(self.win, customMarker=customMarker())
        r.noResponse = False
        r.markerPosFixed = False
        r.draw()

    def test_ratingscale_misc(self):
        r = RatingScale(self.win)
        r._getMarkerFromPos(.2)
        r._getMarkerFromTick(0)
        r.setMarkerPos(2)

    def test_draw_conditionals(self):
        r = RatingScale(self.win)

        # 934-40, 944-45 if self.allowTimeOut ....:
        r.allowTimeOut = True
        r.timedOut = False
        r.maxTime = -1
        r.noResponse = False
        r.disappear = True
        r.draw()

        # 1049-1061  if self.myMouse.getPressed()[0]:

        # 1066-1072  if not self.noResponse and self.decisionTime == 0:
        r = RatingScale(self.win)
        r.beyondMinTime = True
        r.showAccept = True
        r.noResponse = False
        r.decisionTime = 0
        r.draw()

        r = RatingScale(self.win, singleClick=True, markerStyle='glow', markerExpansion=-10)
        r.draw()

    def test_key_presses(self):
        r = RatingScale(self.win)
        r.markerPlaced = True
        r.allKeys = ['s']
        r.markerPlacedAt = 2

        # 1014-1042
        r.mouseOnly = False
        r.skipKeys = ['s']
        event._onPygletKey(symbol='s', modifiers=None, emulated=True)
        r.draw()
        r.skipKeys = []

        r.respKeys = ['s']
        r.enableRespKeys = True
        event._onPygletKey(symbol='s', modifiers=None, emulated=True)
        r.draw()
        r.respKeys = []

        r = RatingScale(self.win)
        r.markerPlaced = True
        r.allKeys = ['s']
        r.markerPlacedAt = 2
        r.leftKeys = ['s']
        event._onPygletKey(symbol='s', modifiers=None, emulated=True)
        r.draw()
        r.leftKeys = []

        r.rightKeys = ['s']
        event._onPygletKey(symbol='s', modifiers=None, emulated=True)
        r.draw()
        r.rightKeys = []

        r.acceptKeys = ['s']
        r.beyondMinTime = True
        event._onPygletKey(symbol='s', modifiers=None, emulated=True)
        r.draw()

    def test_1019_1029(self):
        # 1019-1029
        r = RatingScale(self.win)
        r.skipKeys = []
        r.mouseOnly = False
        r.enableRespKeys = True
        r.respKeys = ['s']
        r.allKeys = ['s']
        r.tickFromKeyPress = {u's': 1}
        event._onPygletKey(symbol='s', modifiers=None, emulated=True)
        r.singleClick = True
        r.beyondMinTime = True
        r.draw()

        r.leftKeys = ['s']
        r.draw()
        r.leftKeys = []
        r.rightKeys = ['s']
        r.draw()
        r.rightKeys = []

    def test_reset(self):
        r = RatingScale(self.win, markerStart=3)
        r.reset()
        assert r.noResponse == True
        assert r.markerPlaced == True
        assert r.markerPlacedAt == r.markerStart - r.low
        assert r.firstDraw == True
        assert r.decisionTime == 0
        assert r.markerPosFixed == False
        assert r.frame == 0
        assert r.status == NOT_STARTED
        assert r.history == None

    def test_getRating_RT_history(self):
        # 1139-43
        r = RatingScale(self.win)
        r.status = FINISHED
        r.noResponse = True
        for r.timedOut in [True, False]:
            assert r.getRT() in [r.maxTime, None]
        r.noResponse = False
        assert r.getRT() == r.decisionTime

        r = RatingScale(self.win, precision=10)
        r.noResponse = True
        r.markerPlacedAt = 0
        r.status = FINISHED
        assert r.getRating() == False

        r.status = FINISHED + 1
        assert r.getRating() == 1

        r.precision = 1
        r.choices = ['a', 'b']
        assert r.getRating() == 'b'

        r = RatingScale(self.win, singleClick=True)
        r.draw()
        core.wait(.001, 0)
        r.acceptKeys = r.allKeys = ['1']
        r.beyondMinTime = True
        event._onPygletKey(symbol='1', modifiers=None, emulated=True)
        r.draw()
        h = r.getHistory()
        assert h[0] == (None, 0)
        assert h[-1][0] == 1
        assert 0.001 < h[-1][1] < 0.03

    def test_labels_False(self):
        # 386-92
        for anc in [None, 'a']:
            r = RatingScale(self.win, choices=['1', '2', '3'], labels=False,
                               lowAnchorText=anc, highAnchorText=anc)
