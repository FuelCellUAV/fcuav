#!/usr/bin/python2

# Import libraries
import sys
from   time import time
import piface.pfio as pfio
import RPi.GPIO as GPIO
import smbus

# Define global constants
BLUE      = 0x4a
EARTH     = 0x49
RED       = 0x48
YELLOW    = 0x4b
h2Pin     = 0 # Relay
fanPin    = 1 # Relay
purgePin  = 2
buttonOn  = 0
buttonOff = 1
purgeFreq = 3 # Seconds
purgeTime = 0.5 # Seconds
startTime = 3
stopTime  = 3
cutoff    = 25.0 # degC

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
		    print 'turning off {0}. delta={1}'.format(self.pin,time()-self.lastTime)
		    self.lastTime = time()
		    self.state = False
		    return self.write()

		# Activate
		if (time()-self.lastTime) >= freq and self.state == False:
		    print 'turning on {0}. delta={1}'.format(self.pin,time()-self.lastTime)
		    self.lastTime = time()
		    self.state = True
		    return self.write()

		
	def switch(self, state):
		self.state = state
		return self.write()

	def resetTimers(self):
		self.lastTime = time()

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
	print 'Too hot! (cutoff={} degC)'.format(cutoff)
	print '\tBlue={0}, Earth={1}, Red={2}, Yellow={3}.'.format(blue(),earth(),red(),yellow())
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
        while (True):
            h2.switch(False)
            fan.switch(False)
            purge.switch(False)
    ## end STATE MACHINE ##
# end main
