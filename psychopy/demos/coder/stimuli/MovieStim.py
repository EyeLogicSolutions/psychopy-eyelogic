#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Demo of MovieStim

Different systems have different sets of codecs.
avbin (which PsychoPy uses to load movies) seems not to load compressed audio on all systems.
To create a movie that will play on all systems I would recommend using the format:
    video: H.264 compressed,
    audio: Linear PCM
"""
from psychopy import visual, core, event, constants

win = visual.Window((800, 600))
mov = visual.MovieStim(win, 'jwpIntro.mp4', size=(640, 480),
    flipVert=False, flipHoriz=False, loop=False)
print('orig movie size=%s' % mov.size)
print('duration=%.2fs' % mov.duration)
globalClock = core.Clock()

while mov.status != constants.FINISHED:
    mov.draw()
    win.flip()
    if event.getKeys():
        break

win.close()
core.quit()

# The contents of this file are in the public domain.
