#!/usr/bin/python2

# Import libraries
import sys
from time import time
import piface.pfio as pfio
import RPi.GPIO as GPIO
import smbus

# Define global constants
BLUE      =  0x4a
EARTH     =	0x49
RED       =	0x48
YELLOW    =	0x4b
h2Pin     = 0 # Relay
fanPin    = 1 # Relay
purgePin  = 2
buttonOn  = 0
buttonOff = 1
purgeFreq = 3 # Seconds
purgeTime = 0.5 # Seconds
startTime = 3
stopTime  = 3
cutoff    = 25 # degC

class STATE:
	startup, on, shutdown, off, error = range(5)

# Class to enable controlled switching
class Switch:
	pin   = 0
	state = False
	lastTime = 0
	
	def __init__(self, pin):
		self.pin = pin
		self.lastTime = time()
		
	def timed(self, freq, duration):
		delta = time() - self.lastTime
		
		# Deactivate if time is up
		if delta >= duration && self.state == True:
			self.state = False
			self.lastTime = time()
		# Activate
		elif delta >= freq && self.state == False:
			self.state = True
			self.lastTime = time()
		
		pfio.digital_write(self.pin,self.state)
		
		return self.state
		
	def switch(self, state):
		self.state = state
		pfio.digital_write(self.pin,self.state)
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
	blue() ; earth() ; red() ; yellow()
	if blue >= cutoff or earth >= cutoff or red >= cutoff or yellow >= cutoff:
		print ("Too hot!")
		state = STATE.error

    # STOP BUTTON
    if pfio.digital_read(buttonOn) == False and pfio.digital_read(buttonOff) == True:
        if state == 1 or state == 2:
            state = 3
            timeChange = time()
            h2.stop()
            fan.stop()
            purge.stop()
            print ("Shutting down")

    ## STATE MACHINE ##
    if state == 0:
        # Off
        h2.stop()
        fan.stop()
        purge.stop()

        if pfio.digital_read(buttonOn) == True and pfio.digital_read(buttonOff) == False:
             state = 1
             timeChange = time()
             h2.resetTimers()
             fan.resetTimers()
             purge.resetTimers()
             print ("Starting")
    if state == 1:
        # Startup
        try:
            h2(startTime,startTime)
            fan(startTime,startTime)
            purge(startTime,startTime)
            if (time() - timeChange) > startTime:
                state = 2
                h2.resetTimers()
                fan.resetTimers()
                purge.resetTimers()
                print ("Running")
        except Exception as e:
            print ("Startup Error")
            state = 4
    if state == 2:
        # Running
        try:
            h2()
            fan()
            purge(purgeFreq,purgeTime)
        except Exception as e:
            print ("Running Error")
            state = 4
    if state == 3:
        # Shutdown
        try:
            h2.stop()
            fan(stopTime,stopTime)
            purge(stopTime,stopTime)
            if (time() - timeChange) > stopTime:
                state = 0
                h2.resetTimers()
                fan.resetTimers()
                purge.resetTimers()
                print("Stopped")
        except Exception as e:
            print ("Shutdown Error")
            state = 4
    if state == 4:
        # Error lock
        while (True):
            h2.stop()
            fan.stop()
            purge.stop()
    ## end STATE MACHINE ##
# end main
