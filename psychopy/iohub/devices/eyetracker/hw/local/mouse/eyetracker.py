# -*- coding: utf-8 -*-
# Part of the psychopy.iohub library.
# Copyright (C) 2012-2016 iSolver Software Solutions
# Distributed under the terms of the GNU General Public License (GPL).
from ......errors import print2err, printExceptionDetailsToStdErr
from ......constants import EventConstants, EyeTrackerConstants
from ..... import Computer, Device
from .... import EyeTrackerDevice
from ....eye_events import *
import sys, errno
from ......util import convertCamelToSnake
from .....mouse import MouseInputEvent

ET_UNDEFINED = EyeTrackerConstants.UNDEFINED
getTime = Computer.getTime

class EyeTracker(EyeTrackerDevice):
    """
    To start iohub with a Mouse Simulated eye tracker, add the full iohub device name
    as a kwarg passed to launchHubServer::

        eyetracker.hw.local.mouse.EyeTracker
              
    Examples:
        A. Start ioHub with the Mouse Simulated eye tracker::
    
            from psychopy.iohub import launchHubServer
            from psychopy.core import getTime, wait

            iohub_config = {'eyetracker.hw.local.mouse.EyeTracker': {}}
                
            io = launchHubServer(**iohub_config)
            
            # Get the eye tracker device.
            tracker = io.devices.tracker
            
        B. Print all eye tracker events received for 2 seconds::
                        
            # Check for and print any eye tracker events received...
            tracker.setRecordingState(True)
            
            stime = getTime()
            while getTime()-stime < 2.0:
                for e in tracker.getEvents():
                    print(e)
            
        C. Print current eye position for 5 seconds::
                        
            # Check for and print current eye position every 100 msec.
            stime = getTime()
            while getTime()-stime < 5.0:
                print(tracker.getPosition())
                wait(0.1)
            
            tracker.setRecordingState(False)
            
            # Stop the ioHub Server
            io.quit()
    """

    DEVICE_TIMEBASE_TO_SEC = 1.0
    EVENT_CLASS_NAMES = [
        'MonocularEyeSampleEvent',
        'FixationStartEvent',
        'FixationEndEvent',
        'SaccadeStartEvent',
        'SaccadeEndEvent',
        'BlinkStartEvent',
        'BlinkEndEvent']
    __slots__ = []
    _ioMouse = None
    _recording = False
    _last_mouse_event_time = 0
    # TODO: Use runtime_settings: sampling_rate: to calc _ISI
    _ISI = 0.01
    def __init__(self, *args, **kwargs):
        EyeTrackerDevice.__init__(self, *args, **kwargs)
        config = self.getConfiguration()
        # Used to hold the last sample processed by iohub.
        self._latest_sample = None
        EyeTracker._ISI = 1.0/config.get('runtime_settings').get('sampling_rate')
        print2err('EyeTracker._ISI: ', EyeTracker._ISI)
        # Used to hold the last valid gaze position processed by ioHub.
        # If the last mouse tracker in a blink state, then this is set to None
        #
        self._latest_gaze_position = 0.0, 0.0

    def _connectMouse(self):
        if self._iohub_server:
            for dev in self._iohub_server.devices:
                if dev.__class__.__name__ == 'Mouse':
                    EyeTracker._ioMouse = dev

    def _poll(self):
        if self.isConnected() and self.isRecordingEnabled():
            if EyeTracker._last_mouse_event_time == 0:
                EyeTracker._last_mouse_event_time = getTime() - self._ISI

            while getTime() - EyeTracker._last_mouse_event_time >= self._ISI:
                # Generate an eye sample every ISI seconds
                lb, mb, rb = self._ioMouse.getCurrentButtonStates()
                if rb and lb:
                    # In blink state, handle....
                    self._latest_gaze_position = None
                elif rb:
                    self._latest_gaze_position = self._ioMouse.getPosition()

                EyeTracker._last_mouse_event_time += self._ISI
                next_sample_time = EyeTracker._last_mouse_event_time
                self._addSample(next_sample_time)
            #TODO: Generate fixation, saccade blink events

    def _addSample(self, sample_time):
        if self._latest_gaze_position:
            gx, gy = self._latest_gaze_position
            status = 0
        else:
            gx, gy = EyeTrackerConstants.UNDEFINED, EyeTrackerConstants.UNDEFINED
            status = 2

        pupilSize = 5
        monoSample = [0,
                      0,
                      0,  # device id (not currently used)
                      Device._getNextEventID(),
                      EventConstants.MONOCULAR_EYE_SAMPLE,
                      sample_time,
                      sample_time,
                      sample_time,
                      0,
                      0,
                      0,
                      EyeTrackerConstants.RIGHT_EYE,
                      gx,
                      gy,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      pupilSize,
                      EyeTrackerConstants.PUPIL_DIAMETER_MM,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      EyeTrackerConstants.UNDEFINED,
                      status
                      ]
        self._latest_sample = monoSample
        self._addNativeEventToBuffer(monoSample)

    def trackerTime(self):
        """
        Current eye tracker time.

        Args:
            None

        Returns:
            float: current eye tracker time in sec.msec format.
        """
        return getTime()

    def trackerSec(self):
        """
        Same as trackerTime().
        """
        return getTime()

    def setConnectionState(self, enable):
        """
        When 'connected', the Mouse Simulated Eye Tracker taps into the ioHub Mouse event stream.
        """
        if enable and self._ioMouse is None:
            self._connectMouse()
        elif enable is False and self._ioMouse:
            EyeTracker._ioMouse = None
        return self.isConnected()

    def isConnected(self):
        """
        """
        return self._ioMouse is not None

    def enableEventReporting(self, enabled=True):
        """enableEventReporting is functionally identical to the eye tracker
        device specific setRecordingState method."""

        try:
            self.setRecordingState(enabled)
            enabled = EyeTrackerDevice.enableEventReporting(self, enabled)
            return enabled
        except Exception as e:
            print2err('Exception in EyeTracker.enableEventReporting: ', str(e))
            printExceptionDetailsToStdErr()

    def setRecordingState(self, recording):
        """
        setRecordingState is used to start or stop the recording of data
        from the eye tracking device.
        """
        current_state = self.isRecordingEnabled()
        if recording is True and current_state is False:
            EyeTracker._recording = True
            if self._ioMouse is None:
                self._connectMouse()
        elif recording is False and current_state is True:
            EyeTracker._recording = False
            self._latest_sample = None
            EyeTracker._last_mouse_event_time = 0
        return EyeTrackerDevice.enableEventReporting(self, recording)

    def isRecordingEnabled(self):
        """
        isRecordingEnabled returns the recording state from the eye tracking
        device.

        Args:
           None

        Return:
            bool: True == the device is recording data; False == Recording is not occurring

        """
        return self._recording

    def runSetupProcedure(self):
        """
        runSetupProcedure does nothing in the Mouse Simulated eye tracker, as calibration is automatic. ;)
        """
        print2err("Mouse Simulated eye tracker runSetupProcedure called.")
        return True

    def _getIOHubEventObject(self, native_event_data):
        """The _getIOHubEventObject method is called by the ioHub Process to
        convert new native device event objects that have been received to the
        appropriate ioHub Event type representation."""
        self._latest_sample = native_event_data
        return self._latest_sample

    def _eyeTrackerToDisplayCoords(self, eyetracker_point):
        """Converts GP3 gaze positions to the Display device coordinate space.
        """

        return eyetracker_point[0], eyetracker_point[1]

    def _displayToEyeTrackerCoords(self, display_x, display_y):
        """Converts a Display device point to GP3 gaze position coordinate
        space.
        """
        return display_x, display_y

    def _close(self):
        self.setRecordingState(False)
        self.setConnectionState(False)
        EyeTrackerDevice._close(self)
