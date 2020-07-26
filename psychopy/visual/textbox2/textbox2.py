#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
#
#  FreeType high-level python API - Copyright 2011-2015 Nicolas P. Rougier
#  Distributed under the terms of the new BSD license.
#
# -----------------------------------------------------------------------------

"""
TextBox2 provides a combination of features from TextStim and TextBox and then
some more added:

    - fast like TextBox (TextStim is pyglet-based and slow)
    - provides for fonts that aren't monospaced (unlike TextBox)
    - adds additional options to use <b>bold<\b> and <i>italic<\i> tags in text

"""
import numpy as np
import OpenGL.GL as gl

from ..basevisual import BaseVisualStim, ColorMixin, ContainerMixin
from psychopy.tools.attributetools import attributeSetter
from psychopy.tools.arraytools import val2array
from psychopy.tools.monitorunittools import convertToPix
from .fontmanager import FontManager, GLFont
from .. import shaders
from ..rect import Rect
from ..line import Line
from ... import core

allFonts = FontManager()

# compile global shader programs later (when we're certain a GL context exists)
rgbShader = None
alphaShader = None
showWhiteSpace = False

codes = {'BOLD_START': u'\uE100',
         'BOLD_END': u'\uE101',
         'ITAL_START': u'\uE102',
         'ITAL_END': u'\uE103'}

defaultLetterHeight = {'cm': 1.0,
                       'deg': 1.0,
                       'degs': 1.0,
                       'degFlatPos': 1.0,
                       'degFlat': 1.0,
                       'norm': 0.1,
                       'height': 0.2,
                       'pix': 20,
                       'pixels': 20}

defaultBoxWidth = {'cm': 15.0,
                   'deg': 15.0,
                   'degs': 15.0,
                   'degFlatPos': 15.0,
                   'degFlat': 15.0,
                   'norm': 1,
                   'height': 1,
                   'pix': 500,
                   'pixels': 500}

wordBreaks = " -\n"  # what about ",."?


# If text is ". " we don't want to start next line with single space?

class TextBox2(BaseVisualStim, ContainerMixin, ColorMixin):
    def __init__(self, win, text, font,
                 pos=(0, 0), units='pix', letterHeight=None,
                 size=None,
                 color=(1.0, 1.0, 1.0),
                 colorSpace='rgb',
                 contrast=1,
                 opacity=1.0,
                 bold=False,
                 italic=False,
                 lineSpacing=1.0,
                 padding=None,  # gap between box and text
                 anchor='center',
                 alignment='left',
                 fillColor=None,
                 borderWidth=1,
                 borderColor=None,
                 flipHoriz=False,
                 flipVert=False,
                 editable=False,
                 name='',
                 autoLog=None):

        BaseVisualStim.__init__(self, win, units=units, name=name)
        self.win = win

        self.colorSpace = colorSpace
        self.color = color
        self.contrast = contrast
        self.opacity = opacity

        # first set params needed to create font (letter sizes etc)
        if letterHeight is None:
            self.letterHeight = defaultLetterHeight[units]
        else:
            self.letterHeight = letterHeight
        # self._pixLetterHeight helps get font size right but not final layout
        if 'deg' in units:  # treat deg, degFlat or degFlatPos the same
            scaleUnits = 'deg'  # scale units are just for font resolution
        else:
            scaleUnits = units
        self._pixLetterHeight = convertToPix(
                self.letterHeight, pos=0, units=scaleUnits, win=self.win)
        self._pixelScaling = self._pixLetterHeight / self.letterHeight
        if size is None:
            size = [defaultBoxWidth[units], -1]
        self._requestedSize = size  # (-1 in either dim means not constrained)
        self.size = size  # but this will be updated later to actual size
        self.bold = bold
        self.italic = italic
        self.lineSpacing = lineSpacing
        if padding is None:
            padding = defaultLetterHeight[units] / 2.0
        self.padding = padding
        self.glFont = None  # will be set by the self.font attribute setter
        self.font = font
        # once font is set up we can set the shader (depends on rgb/a of font)
        if self.glFont.atlas.format == 'rgb':
            global rgbShader
            self.shader = rgbShader = shaders.Shader(
                    shaders.vertSimple, shaders.fragTextBox2)
        else:
            global alphaShader
            self.shader = alphaShader = shaders.Shader(
                    shaders.vertSimple, shaders.fragTextBox2alpha)
        self._needVertexUpdate = False  # this will be set True during layout
        # standard stimulus params
        self.pos = pos
        self.posPix = convertToPix(vertices=[0, 0],
                                   pos=self.pos,
                                   units=self.units,
                                   win=self.win)
        self.ori = 0.0
        self.depth = 0.0
        # used at render time
        self._lines = None  # np.array the line numbers for each char
        self._colors = None

        self.flipHoriz = flipHoriz
        self.flipVert = flipVert
        # params about positioning (after layout has occurred)
        self.anchor = anchor  # 'center', 'top_left', 'bottom-center'...
        self.alignment = alignment
        # then layout the text (setting text triggers _layout())
        self.text = text
        # box border and fill
        w, h = self.size
        self.box = Rect(
                win, pos=pos,
                width=w, height=h, units=units,
                lineWidth=borderWidth, lineColor=borderColor,
                fillColor=fillColor,
                autoLog=False)
        # also bounding box (not normally drawn but gives tight box around chrs)
        self.boundingBox = Rect(
                win, pos=pos,
                width=w, height=h, units=units,
                lineWidth=1, lineColor=None, fillColor=None,
                autoLog=False)
        self._requested = {
            'lineColor': borderColor,
            'lineRGB': self.box.lineRGB,
            'lineWidth': borderWidth,
            'fillColor': fillColor,
            'fillRGB': self.box.fillRGB
        }
        self.borderWidth = borderWidth
        self.borderColor = borderColor
        self.fillColor = fillColor

        # caret
        self.editable = editable
        self.caret = Caret(self, color=self.color, width=5)
        self._hasFocus = False
        if editable:  # may yet gain focus if the first editable obj
            self.win.addEditable(self)

        self.autoLog = autoLog

    @attributeSetter
    def font(self, fontName, italic=False, bold=False):
        if isinstance(fontName, GLFont):
            self.glFont = fontName
            self.__dict__['font'] = fontName.name
        else:
            self.__dict__['font'] = fontName
            self.glFont = allFonts.getFont(
                    fontName,
                    size=int(round(self._pixLetterHeight)),
                    bold=self.bold, italic=self.italic)

    @attributeSetter
    def anchor(self, anchor):
        """anchor is a string of terms, top, bottom, left, right, center

        e.g. 'top_center', 'center-right', 'topleft', 'center' are all valid"""
        self.__dict__['anchor'] = anchor
        # look for unambiguous terms first (top, bottom, left, right)
        self._anchorY = None
        self._anchorX = None
        if 'top' in anchor:
            self._anchorY = 'top'
        elif 'bottom' in anchor:
            self._anchorY = 'bottom'
        if 'right' in anchor:
            self._anchorX = 'right'
        elif 'left' in anchor:
            self._anchorX = 'left'
        # then 'center' can apply to either axis that isn't already set
        if self._anchorX is None:
            self._anchorX = 'center'
        if self._anchorY is None:
            self._anchorY = 'center'

    @attributeSetter
    def alignment(self, alignment):
        self.__dict__['alignment'] = alignment
        # look for unambiguous terms first (top, bottom, left, right)
        self._alignY = None
        self._alignX = None
        if 'top' in alignment:
            self._alignY = 'top'
        elif 'bottom' in alignment:
            self._alignY = 'bottom'
        if 'right' in alignment:
            self._alignX = 'right'
        elif 'left' in alignment:
            self._alignX = 'left'
        # then 'center' can apply to either axis that isn't already set
        if self._alignX is None:
            self._alignX = 'center'
        if self._alignY is None:
            self._alignY = 'center'

        self._needVertexUpdate = True

    @attributeSetter
    def text(self, text):
        self.__dict__['text'] = text
        self._layout()

    def _layout(self):
        """Layout the text, calculating the vertex locations
        """

        text = self.text + "\n"
        text = text.replace('<i>', codes['ITAL_START'])
        text = text.replace('</i>', codes['ITAL_END'])
        text = text.replace('<b>', codes['BOLD_START'])
        text = text.replace('</b>', codes['BOLD_END'])
        rgb = self._getDesiredRGB(self.rgb, self.colorSpace, self.contrast)
        font = self.glFont

        # the vertices are initially pix (natural for freetype)
        # then we convert them to the requested units for self._vertices
        # then they are converted back during rendering using standard BaseStim
        vertices = np.zeros((len(text) * 4, 2), dtype=np.float32)
        self._charIndices = np.zeros((len(text)), dtype=int)
        self._colors = np.zeros((len(text) * 4, 4), dtype=np.float32)
        self._texcoords = np.zeros((len(text) * 4, 2), dtype=np.float32)
        self._glIndices = np.zeros((len(text) * 4), dtype=int)

        # the following are used internally for layout
        self._lineNs = np.zeros(len(text), dtype=int)
        self._lineTops = []  # just length of nLines
        self._lineBottoms = []
        self._lineLenChars = []  #
        self._lineWidths = []  # width in stim units of each line

        self._lineHeight = font.height * self.lineSpacing
        lineMax = (self.size[0] - self.padding) * self._pixelScaling
        current = [0, 0]
        fakeItalic = 0.0
        fakeBold = 0.0
        # for some reason glyphs too wide when using alpha channel only
        if font.atlas.format == 'alpha':
            alphaCorrection = 1 / 3.0
        else:
            alphaCorrection = 1

        wordLen = 0
        charsThisLine = 0
        lineN = 0
        for i, charcode in enumerate(text):

            printable = True  # unless we decide otherwise
            # handle formatting codes
            if charcode in codes.values():
                if charcode == codes['ITAL_START']:
                    fakeItalic = 0.1 * font.size
                elif charcode == codes['ITAL_END']:
                    fakeItalic = 0.0
                elif charcode == codes['BOLD_START']:
                    fakeBold = 0.3 * font.size
                elif charcode == codes['BOLD_END']:
                    current[0] -= fakeBold / 2  # we expected bigger current
                    fakeBold = 0.0
                continue
            # handle newline
            if charcode == '\n':
                printable = False

            # handle printable characters
            if printable:
                if showWhiteSpace and charcode == " ":
                    glyph = font[u"·"]
                else:
                    glyph = font[charcode]
                xBotL = current[0] + glyph.offset[0] - fakeItalic - fakeBold / 2
                xTopL = current[0] + glyph.offset[0] - fakeBold / 2
                yTop = current[1] + glyph.offset[1]
                xBotR = xBotL + glyph.size[0] * alphaCorrection + fakeBold
                xTopR = xTopL + glyph.size[0] * alphaCorrection + fakeBold
                yBot = yTop - glyph.size[1]
                u0 = glyph.texcoords[0]
                v0 = glyph.texcoords[1]
                u1 = glyph.texcoords[2]
                v1 = glyph.texcoords[3]
            else:
                glyph = font[u"·"]
                x = current[0] + glyph.offset[0]
                yTop = current[1] + glyph.offset[1]
                yBot = yTop - glyph.size[1]
                xBotL = x
                xTopL = x
                xBotR = x
                xTopR = x
                u0 = glyph.texcoords[0]
                v0 = glyph.texcoords[1]
                u1 = glyph.texcoords[2]
                v1 = glyph.texcoords[3]

            index = i * 4
            theseVertices = [[xTopL, yTop], [xBotL, yBot],
                             [xBotR, yBot], [xTopR, yTop]]
            texcoords = [[u0, v0], [u0, v1],
                         [u1, v1], [u1, v0]]

            vertices[i * 4:i * 4 + 4] = theseVertices
            self._texcoords[i * 4:i * 4 + 4] = texcoords
            self._colors[i*4 : i*4+4, :3] = rgb
            self._colors[i*4 : i*4+4, 3] = self.opacity
            self._lineNs[i] = lineN
            current[0] = current[0] + glyph.advance[0] + fakeBold / 2
            current[1] = current[1] + glyph.advance[1]

            # are we wrapping the line?
            if charcode == "\n":
                lineWPix = current[0]
                current[0] = 0
                current[1] -= self._lineHeight
                lineN += 1
                charsThisLine += 1
                self._lineLenChars.append(charsThisLine)
                lineWidth = lineWPix / self._pixelScaling + self.padding * 2
                self._lineWidths.append(lineWidth)
                charsThisLine = 0
            elif charcode in wordBreaks:
                wordLen = 0
                charsThisLine += 1
            elif printable:
                wordLen += 1
                charsThisLine += 1

            # end line with auto-wrap
            if current[0] >= lineMax and wordLen > 0:
                # move the current word to next line
                lineBreakPt = vertices[(i - wordLen + 1) * 4, 0]
                wordWidth = current[0] - lineBreakPt
                # shift all chars of the word left by wordStartX
                vertices[(i - wordLen + 1) * 4: (i + 1) * 4, 0] -= lineBreakPt
                vertices[(i - wordLen + 1) * 4: (i + 1) * 4, 1] -= self._lineHeight
                # update line values
                self._lineNs[i - wordLen + 1: i + 1] += 1
                self._lineLenChars.append(charsThisLine - wordLen)
                self._lineWidths.append(
                        lineBreakPt / self._pixelScaling + self.padding * 2)
                lineN += 1
                # and set current to correct location
                current[0] = wordWidth
                current[1] -= self._lineHeight
                charsThisLine = wordLen

            # have we stored the top/bottom of this line yet
            if lineN + 1 > len(self._lineTops):
                self._lineBottoms.append(current[1] + font.descender)
                self._lineTops.append(current[1] + self._lineHeight
                                      + font.descender/2)

        # convert the vertices to stimulus units
        self._rawVerts = vertices / self._pixelScaling

        # thisW = current[0] - glyph.advance[0] + glyph.size[0] * alphaCorrection
        # calculate final self.size and tightBox
        if self.size[0] == -1:
            self.size[0] = max(self._lineWidths)
        if self.size[1] == -1:
            self.size[1] = ((lineN + 1) * self._lineHeight / self._pixelScaling
                            + self.padding * 2)

        # if we had to add more glyphs to make possible then 
        if self.glFont._dirty:
            self.glFont.upload()
            self.glFont._dirty = False
        self._needVertexUpdate = True

    def draw(self):
        """Draw the text to the back buffer"""
        if self._needVertexUpdate:
            self._updateVertices()
        if self.fillColor is not None or self.borderColor is not None:
            self.box.draw()
        gl.glPushMatrix()
        self.win.setScale('pix')

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.glFont.textureID)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glEnableClientState(gl.GL_COLOR_ARRAY)
        gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY)
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)

        gl.glVertexPointer(2, gl.GL_FLOAT, 0, self.verticesPix)
        gl.glColorPointer(4, gl.GL_FLOAT, 0, self._colors)
        gl.glTexCoordPointer(2, gl.GL_FLOAT, 0, self._texcoords)

        self.shader.bind()
        self.shader.setInt('texture', 0)
        self.shader.setFloat('pixel', [1.0 / 512, 1.0 / 512])
        nVerts = len(self.text)*4
        gl.glDrawElements(gl.GL_QUADS, nVerts,
                          gl.GL_UNSIGNED_INT, list(range(nVerts)))
        self.shader.unbind()

        # removed the colors and font texture
        gl.glDisableClientState(gl.GL_COLOR_ARRAY)
        gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY)
        gl.glDisableVertexAttribArray(1)
        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glDisable(gl.GL_TEXTURE_2D)

        if self.hasFocus:  # draw caret line
            self.caret.draw()

        gl.glPopMatrix()

    def contains(self, x, y=None, units=None, tight=False):
        """Returns True if a point x,y is inside the stimulus' border.

        Can accept variety of input options:
            + two separate args, x and y
            + one arg (list, tuple or array) containing two vals (x,y)
            + an object with a getPos() method that returns x,y, such
                as a :class:`~psychopy.event.Mouse`.

        Returns `True` if the point is within the area defined either by its
        `border` attribute (if one defined), or its `vertices` attribute if
        there is no .border. This method handles
        complex shapes, including concavities and self-crossings.

        Note that, if your stimulus uses a mask (such as a Gaussian) then
        this is not accounted for by the `contains` method; the extent of the
        stimulus is determined purely by the size, position (pos), and
        orientation (ori) settings (and by the vertices for shape stimuli).

        See Coder demos: shapeContains.py
        See Coder demos: shapeContains.py
        """
        if tight:
            return self.boundingBox.contains(x, y, units)
        else:
            return self.box.contains(x, y, units)

    def overlaps(self, polygon, tight=False):
        """Returns `True` if this stimulus intersects another one.

        If `polygon` is another stimulus instance, then the vertices
        and location of that stimulus will be used as the polygon.
        Overlap detection is typically very good, but it
        can fail with very pointy shapes in a crossed-swords configuration.

        Note that, if your stimulus uses a mask (such as a Gaussian blob)
        then this is not accounted for by the `overlaps` method; the extent
        of the stimulus is determined purely by the size, pos, and
        orientation settings (and by the vertices for shape stimuli).

        Parameters

        See coder demo, shapeContains.py
        """
        if tight:
            return self.boundingBox.overlaps(polygon)
        else:
            return self.box.overlaps(polygon)

    def _updateVertices(self):
        """Sets Stim.verticesPix and ._borderPix from pos, size, ori,
        flipVert, flipHoriz
        """
        # check whether stimulus needs flipping in either direction
        flip = np.array([1, 1])
        if hasattr(self, 'flipHoriz') and self.flipHoriz:
            flip[0] = -1  # True=(-1), False->(+1)
        if hasattr(self, 'flipVert') and self.flipVert:
            flip[1] = -1  # True=(-1), False->(+1)

        font = self.glFont
        # to start with the anchor is bottom left of *first line*
        if self._anchorY == 'top':
            self._anchorOffsetY = (-font.ascender / self._pixelScaling
                                   - self.padding)
        elif self._anchorY == 'center':
            self._anchorOffsetY = (
                    self.size[1] / 2
                    - (font.height / 2 - font.descender) / self._pixelScaling
                    - self.padding)
        elif self._anchorY == 'bottom':
            self._anchorOffsetY = (
                        self.size[1] / 2 - font.descender / self._pixelScaling)
        else:
            raise ValueError('Unexpected error for _anchorY')

        if self._anchorX == 'right':
            self._anchorOffsetX = - (self.size[0] - self.padding) / 1.0
        elif self._anchorX == 'center':
            self._anchorOffsetX = - (self.size[0] - self.padding) / 2.0
        elif self._anchorX == 'left':
            self._anchorOffsetX = 0
        else:
            raise ValueError('Unexpected error for _anchorX')
        self.vertices = self._rawVerts + (self._anchorOffsetX, self._anchorOffsetY)

        vertsPix = convertToPix(vertices=self.vertices,
                                pos=self.pos,
                             win=self.win, units=self.units)
        self.__dict__['verticesPix'] = vertsPix

        # tight bounding box
        L = self.vertices[:, 0].min()
        R = self.vertices[:, 0].max()
        B = self.vertices[:, 1].min()
        T = self.vertices[:, 1].max()
        tightW = R-L
        Xmid = (R+L)/2
        tightH = T-B
        Ymid = (T+B)/2
        self.box.size = tightW, tightH
        self.box.pos = Xmid, Ymid
        self._needVertexUpdate = False

    def _onText(self, chr):
        """Called by the window when characters are received"""
        if chr == '\t':
            self.win.nextEditable()
            return
        if chr == '\r':  # make it newline not Carriage Return
            chr = '\n'
        txt = self.text
        self.text = txt[:self.caret.index] + chr + txt[self.caret.index:]
        self.caret.index += 1

    def _onCursorKeys(self, key):
        """Called by the window when cursor/del/backspace... are received"""
        if key == 'MOTION_UP':
            self.caret.row -= 1
        elif key == 'MOTION_DOWN':
            self.caret.row += 1
        elif key == 'MOTION_RIGHT':
            self.caret.index += 1
        elif key == 'MOTION_LEFT':
            self.caret.index -= 1
        elif key == 'MOTION_BACKSPACE':
            self.text = self.text[:self.caret.index-1] + self.text[self.caret.index:]
            self.caret.index -= 1
        elif key == 'MOTION_DELETE':
            self.text = self.text[:self.caret.index] + self.text[self.caret.index+1:]
        elif key == 'MOTION_NEXT_WORD':
            pass
        elif key == 'MOTION_PREVIOUS_WORD':
            pass
        elif key == 'MOTION_BEGINNING_OF_LINE':
            self.caret.char = 0
        elif key == 'MOTION_END_OF_LINE':
            self.caret.char = -1
        elif key == 'MOTION_NEXT_PAGE':
            pass
        elif key == 'MOTION_PREVIOUS_PAGE':
            pass
        elif key == 'MOTION_BEGINNING_OF_FILE':
            pass
        elif key == 'MOTION_END_OF_FILE':
            pass
        else:
            print("Received unhandled cursor motion type: ", key)

    @property
    def hasFocus(self):
        return self._hasFocus

    @hasFocus.setter
    def hasFocus(self, state):
        if state:
            # Double border width
            if self._requested['lineWidth'] is None:
                self.box.setLineWidth(5*2) # Use 1 as base if border width is none
            else:
                self.box.setLineWidth(max(self._requested['lineWidth'], 5) * 2)
            self.borderWidth = self.box.lineWidth
            # Darken border
            if self._requested['lineColor'] is None:
                # Use window colour as base if border colour is none
                self.box.setLineColor(
                        [max(c - 0.05, 0.05) for c in self.win.color])
            else:
                self.box.setLineColor(
                        [max(c - 0.05, 0.05) for c in self._requested['lineRGB']],
                        colorSpace='rgb')
            self.borderColor = self.box.lineColor
            # Lighten background
            if self._requested['fillColor'] is None:
                # Use window colour as base if fill colour is none
                self.box.color = [
                    min(c+0.05, 0.95) for c in self.win.color
                ]
            else:
                self.box.color = [
                    min(c+0.05, 0.95) for c in self._requested['fillRGB']
                ]
            self.fillColor = self.box.fillColor
            # Redraw text box
            self.draw()
            # Show caret
            self.caret.setOpacity(self.opacity)
        else:
            # Set box properties back to their original values
            self.box.setLineWidth(self._requested['lineWidth'])
            self.borderWidth = self.box.lineWidth
            self.box.setLineColor(self._requested['lineColor'],
                                  colorSpace=self.colorSpace)
            self.borderColor = self.box.lineColor
            self.box.setFillColor(self._requested['fillColor'],
                                  colorSpace=self.colorSpace)
            self.fillColor = self.box.fillColor
            self.box.draw()
            # Hide caret
            self.caret.setOpacity(0)
        # Store focus
        self._hasFocus = state

    @property
    def hasFocus(self):
        return self._hasFocus

    @hasFocus.setter
    def hasFocus(self, state):
        # todo : shouldn't calculate these on change do it once and store
        if state:
            # Adjust fill colour
            if self._requested['fillColor'] is None:
                # Check whether background is light or dark
                self.fillColor = 'white' if np.mean(self.win.rgb) < 0 else 'black'
                self.box.setOpacity(0.1)
            elif self.box.fillColorSpace in ['rgb', 'dkl', 'lms', 'hsv']:
                self.fillColor = [c + 0.1 * \
                                 (1 if np.mean(self._fillColor) < 0.5 else -1)
                for c in self.fillColor]
            elif self.box.colorSpace in ['rgb255', 'named']:
                self.fillColor = [c + 30 * \
                                 (1 if np.mean(self._fillColor) < 127 else -1)
                                  for c in self.fillColor]
            elif self.box.colorSpace in ['hex']:
                self.fillColor = [c + 30 * \
                                 (1 if np.mean(self.box.fillRGB) < 127 else -1)
                                  for c in self.box.fillRGB]
            self.draw()
        else:
            # Set box properties back to their original values
            self.fillColor = self._requested['fillColor']
            self.box.opacity = self.opacity
            self.box.draw()
        # Store focus
        self._hasFocus = state

    def getText(self):
        """Returns the current text in the box"""
        return self.text

    @attributeSetter
    def pos(self, value):
        """The position of the center of the TextBox in the stimulus
        :ref:`units <units>`

        `value` should be an :ref:`x,y-pair <attrib-xy>`.
        :ref:`Operations <attrib-operations>` are also supported.

        Example::

            stim.pos = (0.5, 0)  # Set slightly to the right of center
            stim.pos += (0.5, -1)  # Increment pos rightwards and upwards.
                Is now (1.0, -1.0)
            stim.pos *= 0.2  # Move stim towards the center.
                Is now (0.2, -0.2)

        Tip: If you need the position of stim in pixels, you can obtain
        it like this:

            from psychopy.tools.monitorunittools import posToPix
            posPix = posToPix(stim)
        """
        self.__dict__['pos'] = val2array(value, False, False)
        try:
            self.box.pos = (self.__dict__['pos'] +
                            (self._anchorOffsetX, self._anchorOffsetY))
        except AttributeError:
            pass  # may not be created yet, which is fine
        self._needVertexUpdate = True
        self._needUpdate = True


class Caret(ColorMixin):
    """
    Class to handle the caret (cursor) within a textbox. Do **not** call without a textbox.
    Parameters
        ----------
        textbox : psychopy.visual.TextBox2
            Textbox which caret corresponds to
        visible : bool
            Whether the caret is visible
        row : int
            Textbox row which caret is on
        char : int
            Text character within row which caret is on
        index : int
            Index of character which caret is on
        vertices : list, tuple
            Coordinates of each corner of caret
        width : int, float
            Width of caret line
        color : list, tuple, str
            Caret colour
    """

    def __init__(self, textbox, color, width):
        self.textbox = textbox
        self.index = len(textbox.text)  # start off at the end
        self.autoLog = False
        self.width = width
        self.units = textbox.units
        self.color = color

    @attributeSetter
    def color(self, color):
        ColorMixin.setColor(self, color)
        if self.colorSpace not in ['rgb', 'dkl', 'lms', 'hsv']:
            self._desiredRGB = self.rgb / 127.5 - 1
        else:
            self._desiredRGB = self.rgb

    def draw(self):
        if not self.visible:
            return
        if core.getTime() % 1 > 0.6:  # Flash every other second
            return
        gl.glLineWidth(self.width)
        rgb = self._desiredRGB
        gl.glColor4f(
            rgb[0], rgb[1], rgb[2], self.textbox.opacity
        )
        gl.glBegin(gl.GL_LINES)
        gl.glVertex2f(self.vertices[0, 0], self.vertices[0, 1])
        gl.glVertex2f(self.vertices[1, 0], self.vertices[1, 1])
        gl.glEnd()

    @property
    def visible(self):
        return self.textbox.hasFocus

    @property
    def row(self):
        """What row is caret on?"""
        # Check that index is with range of all character indices
        if self.index >= len(self.textbox._lineNs):
            self.index = len(self.textbox._lineNs) - 1
        # Get line of index
        return self.textbox._lineNs[self.index]
    @row.setter
    def row(self, value):
        """Use line to index conversion to set index according to row value"""
        # Figure out how many characters into previous row the cursor was
        charsIn = self.char
        # If new row is more than total number of rows, move to end of current row
        if value >= len(self.textbox._lineLenChars):
            value = len(self.textbox._lineLenChars)-1
            charsIn = self.textbox._lineLenChars[value]-1
        # If new row is less than 0, move to beginning of first row
        if value < 0:
            value = 0
            charsIn = 0
        # If charsIn is more than number of chars in new row, send it to end of row
        if charsIn > self.textbox._lineLenChars[value]:
            charsIn = self.textbox._lineLenChars[value]-1
        # Set new index in new row
        self.index = sum(self.textbox._lineLenChars[:value]) + charsIn
        # Redraw caret at new row
        self.draw()

    @property
    def char(self):
        """What character within current line is caret on?"""
        # Check that index is with range of all character indices
        self.index = min(self.index, len(self.textbox._lineNs) - 1)
        self.index = max(self.index, 0)
        # Get first index of line, subtract from index to get char
        return self.index - sum(self.textbox._lineLenChars[:self.row])
    @char.setter
    def char(self, value):
        """Set character within row"""
        # If setting char to less than 0, move to last char on previous line
        if value < 0:
            if self.row == 0:
                value = 0
            else:
                self.row -= 1
                value = self.textbox._lineLenChars[self.row]-1
        # If value exceeds row length, set value to beginning of next row
        if value >= self.textbox._lineLenChars[self.row]:
            self.row += 1
            value = 0
        self.index = self.textbox._lineLenChars[:self.row] + value
        # Redraw caret at new char
        self.draw()

    @property
    def vertices(self):
        textbox = self.textbox
        # check we have a caret index
        if self.index is None or self.index > len(textbox._lineNs)-1:
            self.index = len(textbox._lineNs)-1
        if self.index < 0:
            self.index = 0
        # get the verts of character next to caret (chr is the next one so use
        # left edge unless last index then use the right of prev chr)
        # lastChar = [bottLeft, topLeft, **bottRight**, **topRight**]
        ii = self.index
        chrVerts = textbox.vertices[range(ii * 4, ii * 4 + 4)]  # Get vertices of character at this index
        if self.index >= len(textbox._lineNs):  # caret is after last chr
            x = chrVerts[2, 0]  # x-coord of left edge (of final char)
        else:
            x = chrVerts[1, 0]  # x-coord of right edge
        # the y locations are the top and bottom of this line
        y1 = textbox._lineBottoms[self.row] / textbox._pixelScaling
        y2 = textbox._lineTops[self.row] / textbox._pixelScaling

        # char x pos has been corrected for anchor already but lines haven't
        verts = (np.array([[x, y1], [x, y2]])
                 + (0, textbox._anchorOffsetY))
        return convertToPix(vertices=verts, pos=textbox.pos,
                            win=textbox.win, units=textbox.units)
