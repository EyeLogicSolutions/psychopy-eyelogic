import sys
from psychopy.alerts import alerttools
from psychopy.alerts._alerts import alertLog
from psychopy.alerts._errorHandler import ErrorHandler
from psychopy.experiment import getAllComponents, Experiment


class TestAlertTools(object):
    """A class for testing the alerttools module"""

    def setup(self):
        # Create experiment and test components
        exp = Experiment()
        allComp = getAllComponents(fetchIcons=False)

        # Polygon
        self.polygonComp = allComp["PolygonComponent"](parentName='trial', exp=exp)
        self.polygonComp.params['units'].val = 'height'
        self.polygonComp.params['startType'].val = "time (s)"
        self.polygonComp.params['stopType'].val = "time (s)"

        # Code component
        self.codeComp = allComp["CodeComponent"](parentName='trial', exp=exp)
        self.codeComp.params['Begin Experiment'].val = "(\n"
        self.codeComp.params['Begin JS Experiment'].val = "{\n"

        # Set ErrorHandler
        self.error = ErrorHandler()
        sys.stderr = self.error

    def teardown(self):
        sys.stderr = sys.__stderr__
        del alertLog[:]

    def test_sizing_x_dimension(self):
        self.polygonComp.params['size'].val = [4, .5]
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli size exceeds the X dimension of your window' in alertLog[0].msg)

    def test_sizing_y_dimension(self):
        self.polygonComp.params['size'].val = [.5, 4]
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli size exceeds the Y dimension of your window' in alertLog[0].msg)

    def test_size_too_small_x(self):
        self.polygonComp.params['size'].val = [.0000001, .05]
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli size is smaller than 1 pixel (X dimension)' in alertLog[0].msg)

    def test_size_too_small_y(self):
        self.polygonComp.params['size'].val = [.05, .0000001]
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli size is smaller than 1 pixel (Y dimension)' in alertLog[0].msg)

    def test_position_x_dimension(self):
        self.polygonComp.params['pos'].val = [4, .5]
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli position exceeds the X dimension' in alertLog[0].msg)

    def test_position_y_dimension(self):
        self.polygonComp.params['pos'].val = [.5, 4]
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli position exceeds the Y dimension' in alertLog[0].msg)

    def test_variable_fail(self):
        self.polygonComp.params['pos'].val = '$pos'
        self.polygonComp.params['size'].val = '$size'
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert (len(alertLog) == 0)

    def test_timing(self):
        self.polygonComp.params['startVal'].val = 12
        self.polygonComp.params['stopVal'].val = 10
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli start time exceeds the stop time' in alertLog[0].msg)

    def test_disabled(self):
        self.polygonComp.params['disabled'].val = True
        alerttools.testDisabled(self.polygonComp)
        sys.stderr.flush()
        assert ('Your component is currently disabled' in alertLog[0].msg)

    def test_achievable_visual_stim_onset(self):
        self.polygonComp.params['startVal'].val = .001
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli start-time of 0.001 is less than a screen refresh for a 60Hz monitor' in alertLog[0].msg)

    def test_achievable_visual_stim_offset(self):
        self.polygonComp.params['stopVal'].val = .001
        self.polygonComp.params['stopType'].val = "duration (s)"
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('Your stimuli stop-time of 0.001 is less than a screen refresh for a 60Hz monitor' in alertLog[0].msg)

    def test_valid_visual_timing(self):
        self.polygonComp.params['startVal'].val = 1.01
        self.polygonComp.params['stopVal'].val = 2.01
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ('start-time of 1.01 seconds cannot be accurately presented' in alertLog[0].msg)

    def test_frames_as_int(self):
        self.polygonComp.params['startVal'].val = .5
        self.polygonComp.params['startType'].val = "duration (frames)"
        alerttools.runTest(self.polygonComp)
        sys.stderr.flush()
        assert ("Your stimuli start-type 'duration (frames)' must be expressed as a whole number" in alertLog[0].msg)

    def test_python_syntax(self):
        alerttools.checkPythonSyntax(self.codeComp, 'Begin Experiment')
        sys.stderr.flush()
        assert ("Python Syntax Error in 'Begin Experiment'" in alertLog[0].msg)

    def test_javascript_syntax(self):
        alerttools.checkJavaScriptSyntax(self.codeComp, 'Begin JS Experiment')
        sys.stderr.flush()
        assert ("JavaScript Syntax Error in 'Begin JS Experiment'" in alertLog[0].msg)

def test_validDuration():
    testVals = [
        {'t': 0.5, 'hz' : 60, 'ans': True},
        {'t': 0.1, 'hz': 60, 'ans': True},
        {'t': 0.01667, 'hz': 60, 'ans': True},  # 1 frame-ish
        {'t': 0.016, 'hz': 60, 'ans': False},  # too sloppy
        {'t': 0.01, 'hz': 60, 'ans': False},
        {'t': 0.01, 'hz': 100, 'ans': True},
        {'t': 0.009, 'hz': 100, 'ans': False},  # 0.9 frames
        {'t': 0.012, 'hz': 100, 'ans': False},  # 1.2 frames
    ]
    for this in testVals:
        assert alerttools.validDuration(this['t'], this['hz']) == this['ans']
