from pyglet.gl import *
from psychopy import visual
import sys, platform

print "System info:"
print platform.platform()
if sys.platform=='darwin':
    OSXver, junk, architecture = platform.mac_ver()
    print "OS X %s running on %s" %(OSXver, architecture)

print "\nPython info"
print sys.executable
print sys.version
import numpy; print "numpy", numpy.__version__
import scipy; print "scipy", scipy.__version__
import matplotlib; print "matplotlib", matplotlib.__version__
import pyglet; print "pyglet", pyglet.version
import pyo; print "pyo", '.'.join(map(str, pyo.getVersion()))
from psychopy import __version__
print "PsychoPy", __version__

win = visual.Window([100,100])#some drivers want a window open first
print "\nOpenGL info:"
#get info about the graphics card and drivers
print "vendor:", gl_info.get_vendor()
print "rendering engine:", gl_info.get_renderer()
print "OpenGL version:", gl_info.get_version()
print "(Selected) Extensions:"
extensionsOfInterest=['GL_ARB_multitexture', 
    'GL_EXT_framebuffer_object','GL_ARB_fragment_program',
    'GL_ARB_shader_objects','GL_ARB_vertex_shader',
    'GL_ARB_texture_non_power_of_two','GL_ARB_texture_float', 'GL_STEREO']
for ext in extensionsOfInterest:
    print "\t", bool(gl_info.have_extension(ext)), ext
#also determine nVertices that can be used in vertex arrays
maxVerts=GLint()
glGetIntegerv(GL_MAX_ELEMENTS_VERTICES,maxVerts)
print '\tmax vertices in vertex array:', maxVerts.value
