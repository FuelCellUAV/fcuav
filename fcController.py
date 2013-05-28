#!/usr/bin/python2

# Import libraries
import sys
from   time import time
import piface.pfio as pfio
import RPi.GPIO as GPIO
import smbus
import argparse

# Define default global constants
parser = argparse.ArgumentParser(description='Fuel Cell Controller by Simon Howroyd 2013')
parser.add_argument('--out'	   , nargs=1, help='Name of the output logfile')
parser.add_argument('--BLUE'       , nargs=1, type=float, default=0x4a,	help='I2C address')
parser.add_argument('--EARTH'      , nargs=1, type=float, default=0x49, help='I2C address')
parser.add_argument('--RED'        , nargs=1, type=float, default=0x48, help='I2C address')
parser.add_argument('--YELLOW'     , nargs=1, type=float, default=0x4b, help='I2C address')
parser.add_argument('--h2Pin'      , nargs=1, type=float, default=0,	help='H2 supply relay') # Relay
parser.add_argument('--fanPin'     , nargs=1, type=float, default=1,    help='Fan relay') 	# Relay
parser.add_argument('--purgePin'   , nargs=1, type=float, default=2,    help='Purge switch')
parser.add_argument('--buttonOn'   , nargs=1, type=float, default=0,    help='On button')
parser.add_argument('--buttonOff'  , nargs=1, type=float, default=1,    help='Off button')
parser.add_argument('--buttonReset', nargs=1, type=float, default=2,    help='Reset button')
parser.add_argument('purgeFreq'  , nargs='?', type=float, default=3, 	help='How often to purge in seconds')
parser.add_argument('purgeTime'  , nargs='?', type=float, default=0.5,	help='How long to purge for in seconds')
parser.add_argument('startTime'  , nargs='?', type=float, default=5,	help='Duration of the startup routine')
parser.add_argument('stopTime'   , nargs='?', type=float, default=5,	help='Duration of the shutdown routine')
parser.add_argument('cutoff'     , nargs='?', type=float, default=25.0,	help='Temperature cutoff in celcius')
args = parser.parse_args()

# Class to save to file & print to screen
class MyWriter:
    def __init__(self, stdout, filename):
        self.stdout = stdout
        self.logfile = file(filename, 'a')
    def write(self, text):
        self.stdout.write(text)
        self.logfile.write(text)
    def close(self):
        self.stdout.close()
        self.logfile.close()

# Look at user arguments
if args.out: # save to output file
        writer = MyWriter(sys.stdout, args.out)
	sys.stdout = writer
BLUE 	    = args.BLUE
EARTH 	    = args.EARTH
RED 	    = args.RED
YELLOW 	    = args.YELLOW
h2Pin 	    = args.h2Pin
fanPin 	    = args.fanPin
purgePin    = args.purgePin
buttonOn    = args.buttonOn
buttonOff   = args.buttonOff
buttonReset = args.buttonReset
purgeFreq   = args.purgeFreq
purgeTime   = args.purgeTime
startTime   = args.startTime
stopTime    = args.stopTime
cutoff 	    = args.cutoff

# State machine cases
class STATE:
	startup, on, shutdown, off, error = range(5)

# Class to enable controlled switching
class Switch:
	pin   = 0
	state = False
	lastTime = 0
	lastOff= 0
	
	def __init__(self, pin):
		self.pin = pin
		
	def timed(self, freq, duration):
		# Deactivate if time is up
		if (time()-self.lastTime) >= duration and self.state == True:
		    self.lastTime = time()
		    self.state = False
		    return self.write()

		# Activate
		if (time()-self.lastTime) >= freq and self.state == False:
		    self.lastTime = time()
		    self.state = True
		    return self.write()

	def switch(self, state):
		self.state = state
		return self.write()

	def write(self):
		try:
		    pfio.digital_write(self.pin,self.state)
		except Exception as e:
    		    print ("Timer digital write error")
                
		return self.state

# Class to read I2c TMP102 Temperature Sensor
class I2cTemp:
	address = 0x00
	
	def __init__(self, address):
		self.address = address
		
	def __call__(self):
		try:
		   tmp  = bus.read_word_data(self.address , 0 )
		   msb  = (tmp & 0x00ff)
		   lsb  = (tmp & 0xff00) >> 8
		   temp = ((( msb * 256 ) + lsb) >> 4 ) * 0.0625
		   return temp
		except Exception as e:
           	   print ("I2C Error")
		   return -1

# Define class instances
bus       = smbus.SMBus(0)
purge     = Switch(purgePin)
h2        = Switch(h2Pin)
fan       = Switch(fanPin)
blue      = I2cTemp(BLUE)
earth     = I2cTemp(EARTH)
red       = I2cTemp(RED)
yellow    = I2cTemp(YELLOW)


# Setup
pfio.init()
state = STATE.off
print("\nFuel Cell Controller")
print("Horizon H-100 Stack")
print("(c) Simon Howroyd 2013")
print("Loughborough University\n")

# Main
while (True):

    # TEMP SHUTDOWN
    if blue() >= cutoff or earth() >= cutoff or red() >= cutoff or yellow() >= cutoff:
	print '\rToo hot! (cutoff={} degC)'.format(cutoff),
	print '\tBlue={0}\tEarth={1}\tRed={2}\tYellow={3}'.format(blue(),earth(),red(),yellow()),
	state = STATE.error

    # STOP BUTTON
    if pfio.digital_read(buttonOn) == False and pfio.digital_read(buttonOff) == True:
        if state == STATE.startup or state == STATE.on:
            state = STATE.shutdown
            timeChange = time()
            print ("Shutting down")

    ## STATE MACHINE ##
    if state == STATE.off:
        # Off
        h2.switch(False)
        fan.switch(False)
        purge.switch(False)

        if pfio.digital_read(buttonOn) == True and pfio.digital_read(buttonOff) == False:
	    state = STATE.startup
            timeChange = time()
            print ("Starting")
    if state == STATE.startup:
        # Startup
        try:
	    h2.timed(0,startTime)
            fan.timed(0,startTime)
            purge.timed(0,startTime)
            if (time() - timeChange) > startTime:
                state = STATE.on
                print ("Running")
        except Exception as e:
            print ("Startup Error")
            state = STATE.error
    if state == STATE.on:
        # Running
        try:
            h2.switch(True)
            fan.switch(True)
            purge.timed(purgeFreq,purgeTime)
        except Exception as e:
            print ("Running Error")
            state = STATE.error
    if state == STATE.shutdown:
        # Shutdown
        try:
            h2.switch(False)
            fan.timed(0,stopTime)
            purge.timed(0,stopTime)
            if (time() - timeChange) > stopTime:
                state = STATE.off
                print("Stopped")
        except Exception as e:
            print ("Shutdown Error")
            state = STATE.error
    if state == STATE.error:
        # Error lock
        if pfio.digital_read(buttonReset) == True:
  	    # Reset button
	    state = STATE.off
            print("\nResetting")
            
	h2.switch(False)
        purge.switch(False)
        if blue() >= cutoff or earth() >= cutoff or red() >= cutoff or yellow() >= cutoff:
	    fan.switch(True)
	else:
	    fan.switch(False)

    ## end STATE MACHINE ##
# end main
