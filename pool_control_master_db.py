#!/usr/bin/python

"""
This python script is the heart of my pool control project. This script
relies on many other components to work including energy monitoring, mysql
databases, influx databases, rachio sprinkler systems and various sensors
installed throughout the project and tracked via the open source project
OpenEnergyMonitor.

The goal of this project is to automate, as much as possible, the management
and visualization of my pool automation and chemical systems.

This is an ongoing project often with major changes as I learn more about
python.

You can read the readme or visit my project on Hackster
https://www.hackster.io/user3424878278/pool-fill-control-119ab7

"""


__author__ = 'Richard J. Sears'
VERSION = "V3.5.1 (2019-03-03)"
# richard@sears.net

#TODO Put more thought into logging. Too much? Too little?


# Manage Imports
import os
import yaml
import logging.config
import logging
import logging.handlers
import sys
sys.path.append('/var/www/utilities')
import pooldb  # Database information
import mysql.connector
from mysql.connector import errorcode
import time
import RPi.GPIO as GPIO
import serial
import subprocess
import datetime
import urllib2
import json
import httplib
from subprocess import call
import requests
import get_ph
import get_orp
import influx_data
from use_database import update_database, read_database, read_emoncms_database, insert_database, read_database_fill
from notifications_db import notify
import db_info
import ConfigParser


## Setup All of our LOGGING here:
config = ConfigParser.ConfigParser()

def read_logging_config(file, section, status):
    pathname = '/var/www/' + file
    config.read(pathname)
    if status == "LOGGING":
        current_status = config.getboolean(section, status)
    else:
        current_status = config.get(section, status)
    return current_status

def update_logging_config(file, section, status, value):
    pathname = '/var/www/' + file
    config.read(pathname)
    cfgfile = open(pathname, 'w')
    config.set(section, status, value)
    config.write(cfgfile)
    cfgfile.close()

def setup_logging(default_path='logging.yaml', default_level=logging.CRITICAL, env_key='LOG_CFG'):
    if LOGGING == 1:
        path = default_path
        value = os.getenv(env_key, None)
        if value:
            path = value
        if os.path.exists(path):
            with open(path, 'rt') as f:
                try:
                    config = yaml.safe_load(f.read())
                    logging.config.dictConfig(config)
                   # coloredlogs.install()
                except Exception as e:
                    print(e)
                    print('Error in Logging Configuration. Using default configs')
                    logging.basicConfig(level=default_level)
                   # coloredlogs.install(level=default_level)
        else:
            logging.basicConfig(level=default_level)
           # coloredlogs.install(level=default_level)
            print('Failed to load configuration file. Using default configs')
    else:
        log.disabled = True


LOGGING = read_logging_config("logging_config", "logging", "LOGGING")
LOG_LEVEL = read_logging_config("logging_config", "logging", "LEVEL")
log = logging.getLogger(__name__)
level = logging._checkLevel(LOG_LEVEL)
log.setLevel(level)
## End of logging setup





#Set our current timestamp & current military time
current_timestamp = int(time.time())
current_military_time = datetime.datetime.now().strftime('%A %b %d, %Y  %H:%M:%S')

## Let's setup our GPIO stuff here
# Connected to GPIO 2 (Physical Pin 3) Builtin Resistor
manual_fill_button = 2

# The LED in the button is connected to GPIO 11 (Physical Pin 23)
manual_fill_button_led = 11

# Our relay for the sprinkler valve is on GPIO 17 (Physical Pin 11)
pool_fill_relay = 17

# Relay that controls power to the transformer that operates
# the sprinkler valve (Physical Pin 19)
pool_fill_transformer_relay = 26

# Acid level sensor pin here is tied to GPIO 14. The acid level sensor is
# a three wire connection with ground and 3.3V plus GPIO for detecting the
# level of the acid in our acid tank. It provides OK or LOW only, not a
# specific level in the tank.
acid_level_sensor_pin = 14
sprinkler_run_led = 5
pump_run_led = 13
system_run_led = 21
system_error_led = 16
pool_filling_led = 12
pool_fill_valve_disabled_pin = 3
pool_fill_valve_disabled_led = 4
pool_pump_running_pin = 19

# Setup our GPIO Pins
GPIO.setwarnings(False)  # Don't tell me about GPIO warnings.
GPIO.setmode(GPIO.BCM)  # Use BCM Pin Numbering Scheme
GPIO.setup(pool_fill_relay, GPIO.OUT)
GPIO.setup(pool_fill_transformer_relay, GPIO.OUT)
GPIO.setup(manual_fill_button_led, GPIO.OUT)  # Make LED  an Output
GPIO.setup(sprinkler_run_led, GPIO.OUT)
GPIO.setup(pump_run_led, GPIO.OUT)
GPIO.setup(system_run_led, GPIO.OUT)
GPIO.setup(system_error_led, GPIO.OUT)
GPIO.setup(pool_filling_led, GPIO.OUT)
GPIO.setup(pool_fill_valve_disabled_pin, GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.setup(pool_fill_valve_disabled_led, GPIO.OUT)
GPIO.setup(acid_level_sensor_pin, GPIO.IN)
GPIO.setup(pool_pump_running_pin, GPIO.IN,pull_up_down=GPIO.PUD_UP)


# Do we have internet access? This functions checks for internet access. We then use this to determine
# which database server we will be using (eventually). If we do not have internet access, we (currently) cannot run
# this system until I rewrite the code to reference local servers as opposed to remote servers.
#TODO Add local DB servers so this system will run without internet access.
def check_internet():
    """Check to see if internet is accessible.
    This function uses a predefined url for testing
    located in pooldb.check_url:

    >>> check_internet()
    check_internet() Started
    We have Internet Access!
    check_internet() Completed
    True
    """
    log.debug("check_internet() Started")
    check_url = pooldb.check_url
    conn = httplib.HTTPConnection(check_url, timeout=3)
    try:
        conn.request("HEAD", "/")
        conn.close()
        log.info("We have Internet Access")
        log.debug("check_internet() Completed")
        return True
    except:
        conn.close()
        # debug("We 'DO NOT' have Internet Access!")
        # debug("EXITING: Will try again on the next run!")
        #verbose_debug("check_internet() Completed")
        log.critical("check_internet(): We 'DO NOT' have Internet Access. Exiting!")
        log.critical("check_internet() Completed with Errors. System Exit")
        exit()  # At "this" point we cannot run without internet, so just throw the error and exit.
                # TODO We need to change DB setup to allow it to run without internet!!

# This is the setup to our MightyHat (lowpowerlabs.com). You can disable this
# function if you are not using the MightyHat. Remove it here as well as in
# def main() below. If you leave it, error handling should catch it and allow
# the rest of the script to continue.
#
# Error handling in case USB port wrong or fails to open or no MightyHat -
# at least code will continue to run in either case. Does not effect outcome
# of program. MightyHat is informational display only.
# Right now I do not have this incorporated in the new version of code.
def mightyhat_serial_setup():
    log.debug("mightyhat_serial_setup() - Started")
    #verbose_debug("mightyhat_serial_setup() - Started")
    #TODO Finish setting up MightyHat message management
    try:
     #   global ser
        ser = serial.Serial(
            port='/dev/ttyAMA0',
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1)
    except Exception as error:
        # debug("EXCEPTION: mightyhat_serial_setup()")
        log.warning("EXCEPTION: mightyhat_serial_setup()")
        log.warning(error)
        # debug(type(error))
        # debug(error)
    #verbose_debug("mightyhat_serial_setup()  - Completed")
    log.debug("mightyhat_serial_setup() - Completed")

# LED Blinking
def blink_led(pin, numtimes, speed):
    for i in range(0, numtimes):
        GPIO.output(pin, True)
        time.sleep(speed)
        GPIO.output(pin, False)
        time.sleep(speed)

# LED Control - ON/OFF = True/False
def led_control(led, onoff):
    """ Function to turn physical system LEDs on and off. """
    if onoff == "True":
        GPIO.output(led, True)
    elif onoff == "False":
        GPIO.output(led, False)

# Here is where we convert our resistance level from our eTape to a percentage
# for our web interface. I was having trouble with my eTape getting moisture
# inside the tape itself and failing so I am converting to a two level stainless
# steel water level sensor sold on Amazon by Elecall Tools. As a result I wrote
# a new sketch that outputs 3 levels, 0) Low, 1) Mid and 2) Full:
def get_pool_level_percentage(level):
    log.debug("get_pool_level_percentage(level) called with {}.".format(level))

    """Input a level from our pool sensor and it is converted to
    a percentage for use with our gauge in our web display and
    debug output and logging messages. The value is read from our
    emoncms database as 0 (Low), 1 (Mid) or 2 (Full).

    >>> get_pool_level_percentage(0)
    74
    """

    if level == 0:
        return 74
    elif level == 1:
        return 85
    else:
        return 100


# Convert our battery voltages from various sensors to percentages
# for web interface
def get_battery_percentage(voltage):
    log.debug("get_battery_percentage(voltage) called with {} voltage.".format(voltage))

    """Input a battery voltage and get a battery level
    percentage in return. Useful for gauge readouts:

    >>> get_battery_percentage(2.8)
    67
    """

    if voltage >= 3.2:
        batt_level = 100
    elif voltage >= 3.0 < 3.2:
        batt_level = 87
    elif voltage >= 2.7 < 3.0:
        batt_level = 67
    elif voltage >= 2.5 < 2.7:
        batt_level = 53
    elif voltage >= 2.2 < 2.5:
        batt_level = 33
    else:
        batt_level = 20
    return batt_level

# We are utilizing pump control software from Russell Goldin
# (https://github.com/tagyourit) to manage our Pentair Variable Speed pump and
# this is where we check to make sure that it is running so we can use it. If it
# is not running, then we get some information like wattage from our energy
# management functions.
def check_pump_control_url():
    """ Check to see if our pump control software is running. If it is,
    it will respond to a web request on port 3000. This verifies that we
    can reach the software:

    >>> check_pump_control_url()
    check_pump_control_url() Started
    Pump Control System - Online
    check_pump_control_url() Completed
    True
    """
    #verbose_debug("check_pump_control_url() Started")
    log.debug("check_pump_control_url() Started")
    check_url = pooldb.PUMP_DATA_TEST_URL
    conn = httplib.HTTPConnection(check_url, timeout=3)
    try:
        conn.request("HEAD", "/")
        conn.close()
        update_database ("pump_status", "pump_control_active", True)
        log.info("Pump Control System - Online")
        log.debug("check_pump_control_url() Completed")
        pump_control_active = True
        return True
    except:
        conn.close()
        update_database ("pump_status", "pump_control_active", False)
        log.debug("Pump Control System - Offline")
        log.debug("check_pump_control_url() Completed")
        pump_control_active = False
        return False


# Function to retrieve json data from pump control software
# See https://github.com/tagyoureit/nodejs-poolController
# Exception handling due to URL request.
#TODO Impliment this function and remove get_pump_gpm, get_pump_rpm & alter get_pump_watts
def get_pump_data(key):
    log.debug("get_pump_data() called with '{}' ".format(key))
    pump_control_active = read_database("pump_status", "pump_control_active")
    if pump_control_active:
        try:
            req = urllib2.Request(pooldb.PUMP_DATA_URL)
            opener = urllib2.build_opener()
            f = opener.open(req)
            data = json.load(f)
            pump_data = data["pump"]["1"][key]
            log.debug("get_pump_data() returned {}".format(pump_data))
            log.debug("get_pump_data() - Completed")
            #TODO Make this all one statement with variable substitution for (key)!
            if key == "gpm":
                pump_gpm = pump_data
                update_database("pump_status", "pump_gpm", pump_gpm)
                log.info("get_pump_gpm() reports Current GPM: {}".format(pump_gpm))
                log.debug("get_pump_gpm() Completed")
            elif key == "rpm":
                pump_rpm = pump_data
                update_database("pump_status", "pump_rpm", pump_rpm)
                log.info("get_pump_rpm() reports Current RPM: {}".format(pump_rpm))
                log.debug("get_pump_rpm() Completed")
            else:
                pump_watts = pump_data
                update_database("pump_status", "pump_watts", pump_watts)
                log.info("get_pump_watts() reports Current WATTS: {}".format(pump_watts))
                log.debug("get_pump_watts() Completed")
            return pump_data
        except Exception as error:
            pump_data = 0
            log.warning("EXCEPTION: get_pump_data()")
            log.warning(error)
            log.debug("get_pump_data() - Completed with EXCEPTION")
            return pump_data
    else:
        pump_data = 0
        return pump_data

# Tests for get_pump_data() function above - not needed for production deployment
def get_pump_gpm_test():
    """ Test to see if get_pump_data() is working."""
    test_gpm = get_pump_data("gpm")
    log.debug("Current GPM: {}".format(test_gpm))

def get_pump_rpm_test():
    test_rpm = get_pump_data("rpm")
    log.debug("Current RPM: {}".format(test_rpm))

def get_pump_watts_test():
    test_watts = get_pump_data("watts")
    log.debug("Current WATTS: {}".format(test_watts))

def get_pump_data_test():
    get_pump_gpm_test()
    get_pump_rpm_test()
    get_pump_watts_test()
# End get_pump_data() tests

# This function is only called externally by our Flask web template
# so there is no screen debugging outputted as it will never be seen, however
# we leave it in in case we are running flask in debug mode we will see the messages.
def pump_control(command):
    log.debug("pump_control() called with {}.".format(command))
    pump_program_running = read_database("pump_status", "pump_program_running")
    pump_control_notifications = read_database("notification_settings", "pump_control_notifications")
    pump_control_active = read_database("pump_status", "pump_control_active")
    if pump_control_active:
        try:
            if command == "START":
                urllib2.urlopen(pooldb.PUMP_START_URL)
                update_database("led_status", "pump_run_led", True)
                log.debug("pump_control() called with START command")
                notify("pump_control_notifications", "Your pool pump has been started.", "Your pool pump has been started.")
            elif command == "PROGRAM_1":
                if pump_program_running == "program_1":
                    pass
                else:
                    urllib2.urlopen(pooldb.PUMP_PROGRAM1_URL)
                    update_database("led_status", "pump_run_led", True)
                    log.debug("pump_control() called with PROGRAM 1 (15 GPM) command")
                    notify("pump_control_notifications", "Your pool pump has been set to 15 GPM.", "Your pool pump has been set to 15 GPM.")
            elif command == "PROGRAM_2":
                if pump_program_running == "program_2":
                    pass
                else:
                    urllib2.urlopen(pooldb.PUMP_PROGRAM2_URL)
                    update_database("led_status", "pump_run_led", True)
                    log.debug("pump_control() called with PROGRAM 2 (20 GPM) command")
                    notify("pump_control_notifications", "Your pool pump has been set to 20 GPM.",
                           "Your pool pump has been set to 20 GPM.")
            elif command == "PROGRAM_3":
                if pump_program_running == "program_3":
                    pass
                else:
                    urllib2.urlopen(pooldb.PUMP_PROGRAM3_URL)
                    update_database("led_status", "pump_run_led", True)
                    log.debug("pump_control() called with PROGRAM 3 (30 GPM) command")
                    notify("pump_control_notifications","Your pool pump has been set to 30 GPM.",
                           "Your pool pump has been set to 30 GPM.")
            elif command == "PROGRAM_4":
                if pump_program_running == "program_4":
                    pass
                else:
                    urllib2.urlopen(pooldb.PUMP_PROGRAM4_URL)
                    update_database("led_status", "pump_run_led", True)
                    log.debug("pump_control() called with PROGRAM 4 (50 GPM) command")
                    notify("pump_control_notifications", "Your pool pump has been set to 50 GPM.",
                           "Your pool pump has been set to 50 GPM.")
            else:
                urllib2.urlopen(pooldb.PUMP_STOP_URL)
                update_database("led_status", "pump_run_led", False)
                log.debug("pump_control() called with STOP command")
                notify("pump_control_notifications", "Your pool pump has been stopped.",
                       "Your pool pump has been stopped.")
        except Exception as error:
            log.warning("EXCEPTION: pump_control()")
            log.warning(error)
            log.warning("pump_control() - Completed with EXCEPTION")
    else:
        pass

# Called by our web interface to control Pump Control Software
def pump_control_software(startstop):
    log.debug("pump_control_software() called with {}.".format(startstop))
    pump_control_software_notifications = read_database("notification_settings", "pump_control_software_notifications")
    if startstop == "START":
        call(["/usr/bin/pm2", "start", "0"])
        update_database("pump_status", "pump_control_active", True)
        log.debug("pump_control_software() called with 'START' command")
        notify("pump_control_software_notifications",
               "Pump Control Software",
               "Your pump control software has started.")
        log.debug("pump_control_software() Completed")
    else:
        call(["/usr/bin/pm2", "stop", "0"])
        update_database("pump_status", "pump_control_active", False)
        log.debug("pump_control_software() called with 'STOP' command")
        notify("pump_control_software_notifications",
               "Pump Control Software",
               "Your pump control software has been stopped.")
        log.debug("pump_control_software() Completed")

#TODO Can we modify led_control() to also update database LED status?
#TODO Add sprinkler notifications to web interface and notification system (Done now..???)
def get_sprinkler_status():
    log.debug("get_sprinkler_status() Started.")
    SprinklerStart = int(400)
    SprinklerStop = int(600)
    """ Function to determine if our sprinklers are currently running. """
    if pooldb.sprinkler_type == "Timer":
        if SprinklerStart < current_military_time < SprinklerStop:
            sprinklers_on = True
            update_database("sprinkler_status", "sprinklers_on", True)
            led_control(sprinkler_run_led, "True")
            update_database("led_status", "sprinkler_run_led", True)
            log.debug("Sprinklers are running via TIMER mode.")
            log.debug("Sprinkler Run LED should be ON. This is a BLUE LED.")
        else:
            sprinklers_on = False
            update_database("sprinkler_status", "sprinklers_on", False)
            led_control(sprinkler_run_led, "False")
            update_database("led_status", "sprinkler_run_led", False)
            log.info("Sprinklers are not running via TIMER mode.")
            log.debug("Sprinkler Run LED should be off. This is a BLUE LED.")
    elif pooldb.sprinkler_type == "Rachio":
        log.debug("get_sprinkler_status() called via subprocess (RACHIO)")
        output = subprocess.check_output(pooldb.rachio_url, shell=True)
        if output == "{}":
            sprinklers_on = False
            update_database("sprinkler_status", "sprinklers_on", False)
            led_control(sprinkler_run_led, "False")
            update_database("led_status", "sprinkler_run_led", False)
            log.info("Sprinklers are not running via RACHIO mode.")
            log.debug("Sprinkler Run LED should be off. This is a BLUE LED.")
        elif 'errors' in output:
            log.debug('Rachio returned an Error: {}. Falling back to TIMER MODE'.format(output))
            if SprinklerStart < current_military_time < SprinklerStop:
                sprinklers_on = True
                update_database("sprinkler_status", "sprinklers_on", True)
                led_control(sprinkler_run_led, "True")
                update_database("led_status", "sprinkler_run_led", True)
                log.debug("Sprinklers are running via TIMER mode.")
                log.debug("Sprinkler Run LED should be ON. This is a BLUE LED.")
            else:
                sprinklers_on = False
                update_database("sprinkler_status", "sprinklers_on", False)
                led_control(sprinkler_run_led, "False")
                update_database("led_status", "sprinkler_run_led", False)
                log.info("Sprinklers are not running via TIMER mode.")
                log.debug("Sprinkler Run LED should be off. This is a BLUE LED.")
        else:
            sprinklers_on = True
            update_database("sprinkler_status", "sprinklers_on", True)
            update_database("led_status", "sprinkler_run_led", True)
            log.debug("Sprinklers are running via RACHIO mode.")
            led_control(sprinkler_run_led, "True")
            log.debug("Sprinkler Run LED should be ON. This is a BLUE LED.")
    else:
        sprinklers_on = read_database('sprinkler_status', 'sprinklers_on')
        if sprinklers_on == 0:
            sprinklers_on = False
        else:
            sprinklers_on = True
        log.debug('Reading sprinklers status from database, Sprinkler Status is: {}'.format(sprinklers_on))
    log.debug("get_sprinkler_status() Completed")
    return sprinklers_on


## Here is where we get our pH reading if we have a probe installed.
## In order to get an accurate pH reading the way the sensors are
## installed, we must have the pool pump running. Here is where we
## check to see if the pool pump is running. If it is, we get the
## pH reading, if it is not, we do nothing but log the fact the pump
## is not running.

def get_ph_reading():
    log.debug("get_ph_reading() Started")
    pool_pump_running = read_database("pump_status", "pump_running")
    if pool_pump_running:
        if pooldb.temp_probe == "Yes":
            pool_temp = float(read_database("system_status", "pool_current_temp" ))
            ph_value = float(get_ph.get_current_ph_with_temp(pool_temp))
        else:
            ph_value = float(get_ph.get_current_ph_no_temp())
        influx_data.write_data("pH", ph_value)
        influx_data.write_data("pool_temp", pool_temp)
        if pooldb.emoncms_server1 == "Yes":
            res = requests.get("http://" + pooldb.server1 + "/" + pooldb.emoncmspath1 + "/input/post?&node=" + str(
                pooldb.ph_node) + "&csv=" + ph_value + "&apikey=" + pooldb.apikey1)
            log.debug("Sent current pH Value of {} to Emoncms Server 1".format(ph_value))
        if pooldb.emoncms_server2 == "Yes":
            res = requests.get("http://" + pooldb.server2 + "/" + pooldb.emoncmspath2 + "/input/post?&node=" + str(
                pooldb.ph_node) + "&csv=" + ph_value + "&apikey=" + pooldb.apikey2)
            log.debug("Sent current pH Value of {} to Emoncms Server 2".format(ph_value))
        update_database("pool_chemicals", "pool_current_ph", ph_value)
        log.debug("get_ph_reading() Completed")
    else:
        log.info("Pool Pump is NOT running, cannot get accurate pH reading!")
        log.debug("get_ph_reading() Completed")


## If we have an ORP Probe installed (Atlas Scientific USB) set it up here.
## In order to get an accurate ORP reading the way the sensors are
## installed, we must have the pool pump running. Here is where we
## check to see if the pool pump is running. If it is, we get the
## ORP reading, if it is not, we do nothing but log the fact the pump
## is not running.

def get_orp_reading():
    log.debug("get_orp_reading() Started")
    pool_pump_running = read_database("pump_status", "pump_running")
    if pool_pump_running:
        orp_value = float(get_orp.get_current_orp())
        influx_data.write_data("orp", orp_value)
        if pooldb.emoncms_server1 == "Yes":
            res = requests.get("http://" + pooldb.server1 + "/" + pooldb.emoncmspath1 + "/input/post.json?&node=" + str(
                pooldb.orp_node) + "&csv=" + orp_value + "&apikey=" + pooldb.apikey1)
            log.debug("Sent current ORP Value of {} to Emoncms Server 1".format(orp_value))
        if pooldb.emoncms_server2 == "Yes":
            res = requests.get("http://" + pooldb.server2 + "/" + pooldb.emoncmspath2 + "/input/post.json?&node=" + str(
                pooldb.orp_node) + "&csv=" + orp_value + "&apikey=" + pooldb.apikey2)
            log.debug("Sent current ORP Value of {} to Emoncms Server 2".format(orp_value))
        update_database("pool_chemicals", "pool_current_orp", orp_value)

        log.debug("get_orp_reading() Completed")
    else:
        log.info("Pool Pump is NOT running, cannot get accurate ORP reading!")
        log.debug("get_orp_reading() Completed")

# Track total gallons added to pool during fill times
def get_gallons_total():
    log.debug("get_gallons_total() Started")
    get_gallons_total = read_emoncms_database("data", pooldb.pool_gallons_total)
    pool_gallons_total = int("%1.0f" % get_gallons_total)
    log.info("Total Gallons: {}".format(pool_gallons_total))
    log.debug("get_gallons_total() Completed")
    return pool_gallons_total

def calculate_current_fill_gallons():
    log.debug("calculate_current_fill_gallons() Started")
    fill_gallons_start = get_gallons_total()
    fill_gallons_stop = read_database("filling_gallons","gallons_stop")
    current_fill_gallons = int(fill_gallons_start) - int(fill_gallons_stop)
    update_database("filling_gallons", "gallons_current_fill", current_fill_gallons)
    log.info("Current Fill Gallons: {}".format(current_fill_gallons))
    log.debug("calculate_current_fill_gallons() Completed")
    return current_fill_gallons

def calculate_gallons_used():
    log.debug("calculate_gallons_used() Started")
    gallons_start = read_database("filling_gallons","gallons_start")
    gallons_stop = read_database("filling_gallons","gallons_stop")
    gallons_used = int(gallons_stop) - int(gallons_start)
    update_database("filling_gallons", "gallons_last_fill", gallons_used)
    insert_database("pool_filling_history", "gallons", gallons_used)
    log.info("Gallons Used: {}".format(gallons_used))
    log.debug("calculate_gallons_used() Completed")
    return gallons_used

def reset_gallon_stop_meter():
    """ Make sure we start with zero gallons used. Only used once when we start filling pool."""
    fill_gallons_stop = get_gallons_total()
    update_database("filling_gallons", "gallons_stop", fill_gallons_stop)
    log.debug("reset_gallons_stop_meter called to start with zero gallons used.")



# TODO - Complete pfv_function, add notification via PB once until PFV reenabled!
# TODO - Update logging for pfv_disable function
def pfv_disabled():
    pool_fill_notifications = read_database("notification_settings", "pool_fill_notifications")
    # TODO Complete and test pfv_disabled() function
    """ Function to determine if our PFV has been manually disabled. """
    if DEBUG == "True":
        print("Starting pfv_disabled().")
    # Let take a quick look at the switch that controls our fill valve. Has
    # it been disabled? If so, send a notification
    # and log the error.
    pool_fill_valve_disabled = GPIO.input(pool_fill_valve_disabled_pin)
    if pool_fill_valve_disabled == True:
        led_control(pool_fill_valve_disabled_led, "True")
        if PUSHBULLET == "True" and pool_fill_notifications == "True":
            send_push_notification("Pool Fill Valve DISABLED", "Your pool fill valve has been DISABLED. Pool will not fill.")
    if DEBUG == "True":
        print("Completed pfv_disabled() function")

# Pool_Fill_Valve controls pool sprinkler relay as well as pool sprinkler
# transformer relay.
def pool_fill_valve(openclose):
    log.info("pool_fill_valve() called with {} command.".format(openclose))
    current_timestamp = int(time.time())
    if openclose == "OPEN":
       sprinkler_status = get_sprinkler_status()
       pool_level_sensor_ok = read_database("sensor_status", "pool_level_sensor_ok")
       if sprinkler_status:
           # debug("Sprinklers are running, we cannot fill the pool at this time, we will try again later.")
           log.info("Sprinklers are running, we cannot fill the pool at this time, we will try again later.")
           pass
       elif not pool_level_sensor_ok:
           # debug("There is a problem with your pool level sensor and we cannot fill the pool.")
           log.warning("There is a problem with a pool level sensor and we cannot fill the pool. Please check your sensors.")
           notify("pool_fill_notifications", "Unable to Refill Pool!", "There is a problem with your pool level sensor. We are unable to fill the pool.")
           pass
       else:
           reset_gallon_stop_meter()
           gallons_start = get_gallons_total()
           update_database("filling_gallons", "gallons_start", gallons_start)
           update_database("filling_status", "pool_is_filling", True)
           update_database("filling_time", "pool_fill_start_time", current_timestamp)
           GPIO.output(pool_fill_transformer_relay, True)  # Turns on the Sprinkler Transformer
           GPIO.output(pool_fill_relay, True)  # Turns on the sprinkler valve
           led_control(pool_filling_led, "True") # Turns on the pool filling blue LED
           notify("pool_fill_notifications", "Your pool is low and is automatically filling",
                  "Your pool is low and is automatically filling.")
           update_database("led_status", "pool_filling_led", True)
           log.info("Your Pool is low and is automatically refilling. Pool Filling LED should be on. This is a BLUE LED.")
    elif openclose == "CLOSE":
        GPIO.output(pool_fill_relay, False)  # Turns off the sprinkler valve
        GPIO.output(pool_fill_transformer_relay, False)  # Turns off the Sprinkler Transformer
        led_control(pool_filling_led, "False") # Turns off the pool filling blue LED
        gallons_stop = get_gallons_total()
        update_database("filling_gallons", "gallons_stop", gallons_stop)
        update_database("led_status", "pool_filling_led", False)
        update_database("filling_status", "pool_is_filling", False)
        update_database("filling_time", "pool_fill_total_time", False)
        calculate_gallons_used()
        update_database("filling_gallons", "gallons_current_fill", False)
        log.info("Your pool is done refilling. Pool Filling LED should be OFF. This is a BLUE LED.")
        notify("pool_fill_notifications", "Your pool is done automatically filling", "Your pool is done automatically filling.")
    elif openclose == "WEBCLOSE":
        GPIO.output(pool_fill_relay, False)  # Turns off the sprinkler valve
        GPIO.output(pool_fill_transformer_relay, False)  # Turns off the Sprinkler Transformer
        led_control(pool_filling_led, "False") # Turns off the pool filling blue LED
        gallons_stop = get_gallons_total()
        update_database("filling_gallons", "gallons_stop", gallons_stop)
        update_database("led_status", "pool_filling_led", False)
        update_database("filling_status", "pool_is_filling", False)
        update_database("filling_status", "alexa_manual_fill", False)
        update_database("filling_time", "pool_fill_total_time", False)
        calculate_gallons_used()
        update_database("filling_gallons", "gallons_current_fill", False)
        log.info("Auto Fill terminated by WEB request. Pool Filling LED should be OFF. This is a BLUE LED.")
        notify("pool_fill_notifications", "Pool Auto Fill Terminated by Web Request", "Your swimming pool has stopped filling due to a web request.")
    elif openclose == "CRITICALCLOSE":
        GPIO.output(pool_fill_relay, False)  # Turns off the sprinkler valve
        GPIO.output(pool_fill_transformer_relay, False)  # Turns off the Sprinkler Transformer
        led_control(pool_filling_led, "False")  # Turns off the pool filling blue LED
        gallons_stop = get_gallons_total()
        update_database("filling_gallons", "gallons_stop", gallons_stop)
        update_database("led_status", "pool_filling_led", False)
        led_control(system_error_led, "True") # Turns on the System Error LED
        update_database("led_status", "system_error_led", True)
        update_database("filling_status", "pool_is_filling", False)
        update_database("filling_time", "pool_fill_total_time", False)
        calculate_gallons_used()
        update_database("filling_gallons", "gallons_current_fill", False)
        log.warning("Pool Fill CRITICAL stop! Pool Filling LED should be OFF. This is a BLUE LED.\nSystem Error LED should be on. This is a RED LED!\n")
        notify("pool_fill_notifications", "Pool fill stopped with CRITICAL CLOSE", "You pool has stopped filling due to a CRITICAL STOP! Please check the system!")
    elif openclose == "RESET":
        pool_is_filling = read_database("filling_status", "pool_is_filling")
        if pool_is_filling:
            GPIO.output(pool_fill_relay, False)  # Turns off the sprinkler valve
            GPIO.output(pool_fill_transformer_relay, False)  # Turns off the Sprinkler Transformer
            gallons_stop = get_gallons_total()
            update_database("filling_gallons", "gallons_stop", gallons_stop)
            calculate_gallons_used()
            update_database("filling_gallons", "gallons_current_fill", False)
            # debug("pool_fill_valve called with RESET command")
            log.warning("pool_fill_valve() called with RESET command")
        else:
            # Force relay closed and transformer off regardless of their state just in case,
            # but do not recalculate total gallons, etc.
            GPIO.output(pool_fill_relay, False)  # Turns off the sprinkler valve
            GPIO.output(pool_fill_transformer_relay, False)  # Turns off the Sprinkler Transformer
            # debug("pool_fill_valve called with RESET command")
            log.info("pool_fill_valve() called with RESET command")

    elif openclose == "MANUAL_OPEN":
     #   log.info("pool_fill_valve called with MANUAL_OPEN command")
        sprinkler_status = get_sprinkler_status()
        print ("Our Sprinklers Status is {}".format (sprinkler_status))
        pool_level_sensor_ok = read_database("sensor_status", "pool_level_sensor_ok")
        if sprinkler_status:
            blink_led(manual_fill_button_led, 7, 0.1)
            # debug("Sprinklers are running, we cannot fill the pool at this time, we will try again later")
            log.info("Sprinklers are running, we cannot fill the pool at this time, we will try again later")
            pass
        elif not pool_level_sensor_ok:
            blink_led(manual_fill_button_led, 7, 0.1)
            # debug("INFO", "There is a problem with your pool level sensor and we cannot fill the pool")
            log.warning("There is a problem with your pool level sensor and we cannot fill the pool! Please check your sensor.")
            pass
        else:
            reset_gallon_stop_meter()
            update_database("filling_status", "pool_is_filling", True)
            gallons_start = get_gallons_total()
            log.debug("pool_fill_valve MANUAL_OPEN gallons_start() = {} gallons".format(gallons_start))
            update_database("filling_gallons", "gallons_start", gallons_start)
            update_database("filling_time", "pool_fill_start_time", current_timestamp)
            GPIO.output(pool_fill_transformer_relay, True)  # Turns on the Sprinkler Transformer
            GPIO.output(pool_fill_relay, True)  # Turns on the sprinkler valve
            led_control(pool_filling_led, "True")  # Turns on the pool filling blue LED
            led_control(manual_fill_button_led, "True")
            update_database("led_status", "pool_filling_led", True)
            update_database("led_status", "manual_fill_button_led", True)
            notify("pool_fill_notifications", "Your Pool is MANUALLY Filling", "Your swimming pool is MANUALLY refilling. Pool Filling LED should be on. This is a BLUE LED.")
            log.info("Your pool is MANUALLY Filling.")
    elif openclose == "MANUAL_CLOSE":
        GPIO.output(pool_fill_relay, False)  # Turns off the sprinkler valve
        GPIO.output(pool_fill_transformer_relay, False)  # Turns off the Sprinkler Transformer
        led_control(manual_fill_button_led, "False")
        led_control(pool_filling_led, "False") # Turns off the pool filling blue LED
        gallons_stop = get_gallons_total()
        log.debug("pool_fill_valve MANUAL_CLOSE gallons_stop() = {} gallons".format(gallons_stop))
        update_database("filling_gallons", "gallons_stop", gallons_stop)
        update_database("led_status", "pool_filling_led", False)
        update_database("led_status", "manual_fill_button_led", False)
        update_database("filling_status", "pool_is_filling", False)
        update_database("filling_time", "pool_fill_total_time", False)
        gallons_used = calculate_gallons_used()
        log.debug("pool_fill_valve MANUAL_CLOSED calculate_gallons_used() = {} gallons".format(gallons_used))
        update_database("filling_gallons", "gallons_current_fill", False)
        log.info("Your pool is DONE manually filling.")
        notify("pool_fill_notifications", "Your Pool is DONE manually filling", "Your swimming pool is DONE manually refilling. Pool Filling LED should be off. This is a BLUE LED.")
    elif openclose == "ALEXA_OPEN":
     #   log.info("pool_fill_valve called with ALEXA_OPEN command")
        reset_gallon_stop_meter()
        update_database("filling_status", "pool_is_filling", True)
        update_database("filling_status", "alexa_manual_fill", True)
        gallons_start = get_gallons_total()
        log.debug("pool_fill_valve ALEXA_OPEN gallons_start() = {} gallons".format(gallons_start))
        update_database("filling_gallons", "gallons_start", gallons_start)
        update_database("filling_time", "pool_fill_start_time", current_timestamp)
        GPIO.output(pool_fill_transformer_relay, True)  # Turns on the Sprinkler Transformer
        GPIO.output(pool_fill_relay, True)  # Turns on the sprinkler valve
        led_control(pool_filling_led, "True")  # Turns on the pool filling blue LED
        update_database("led_status", "pool_filling_led", True)
        notify("pool_fill_notifications", "Alexa is refilling Your Pool", "Alexa is refilling Your swimming pool.")
        log.info("Alexa is filling your pool. Pool Filling LED should be on. This is a BLUE LED.")
    elif openclose == "ALEXA_CLOSE":
        GPIO.output(pool_fill_relay, False)  # Turns off the sprinkler valve
        GPIO.output(pool_fill_transformer_relay, False)  # Turns off the Sprinkler Transformer
        led_control(manual_fill_button_led, "False")
        led_control(pool_filling_led, "False") # Turns off the pool filling blue LED
        gallons_stop = get_gallons_total()
        log.debug("pool_fill_valve ALEXA_CLOSE gallons_stop() = {} gallons".format(gallons_stop))
        update_database("filling_gallons", "gallons_stop", gallons_stop)
        update_database("led_status", "pool_filling_led", False)
        update_database("led_status", "manual_fill_button_led", False)
        update_database("filling_status", "pool_is_filling", False)
        update_database("filling_status", "alexa_manual_fill", False)
        update_database("filling_status", "pool_manual_fill", False)
        update_database("filling_time", "pool_fill_total_time", False)
        gallons_used = calculate_gallons_used()
        log.debug("pool_fill_valve ALEXA_CLOSED calculate_gallons_used() = {} gallons".format(gallons_used))
        update_database("filling_gallons", "gallons_current_fill", False)
        log.info("Alexa is done filling Your pool.")
        notify("pool_fill_notifications", "Alexa is done filling you Pool", "Alexa is done refilling your Pool. Pool Filling LED should be off. This is a BLUE LED.")


def get_main_power_readings():
    log.debug("get_main_power_readings() started.")
    """ Function to read power and solar usage information from our emoncms database.
    This information is displayed in DEBUG as well as on our Web Control Panel."""
    power_total_use = read_emoncms_database("data", pooldb.power_total_use)
    power_total_use = int("%1.0f" % power_total_use)
    update_database("power_solar", "total_current_power_utilization", power_total_use)
    log.debug("Total Current Power Utilization: {} watts".format(power_total_use))
    power_importing = read_emoncms_database("data", pooldb.power_importing)
    power_importing = int("%1.0f" % power_importing)
    update_database("power_solar", "total_current_power_import", power_importing)
    log.debug("Total Current Power Import: {} watts".format(power_importing))
    power_solar = read_emoncms_database("data", pooldb.power_solar)
    power_solar = int("%1.0f" % power_solar)
    update_database("power_solar", "total_current_solar_production", power_solar)
    log.debug("Total Current Solar Production: {} watts".format(power_solar))
    log.debug("get_main_power_readings() completed.")


def check_pool_sensors():
    log.debug("Current unix datetime stamp is: {}".format(current_timestamp))

    # Get Pool Level Sensor Information
    get_pool_level_sensor_time = read_emoncms_database("time", pooldb.pool_level_table)
    get_pool_level_sensor_time = int("%1.0f" % get_pool_level_sensor_time)
    log.debug("Pool LEVEL Sensor last updated at: {}".format(get_pool_level_sensor_time))
    pool_level_sensor_time_delta = current_timestamp - get_pool_level_sensor_time
    log.debug("Pool LEVEL Sensor time difference between last sensor reading is: {} seconds.".format(pool_level_sensor_time_delta))
    get_pool_level_sensor_humidity = read_emoncms_database("data", pooldb.pool_level_sensor_humidity_table)
    get_pool_level_sensor_humidity = int("%1.0f" % get_pool_level_sensor_humidity)
    update_database("system_status", "pool_level_sensor_humidity", get_pool_level_sensor_humidity)
    log.debug("Pool LEVEL Sensor Humidity is: {}%".format(get_pool_level_sensor_humidity))
    get_pool_level_sensor_battery_voltage = read_emoncms_database("data", pooldb.pool_level_sensor_battery_table)
    get_pool_level_sensor_battery_voltage = float("%1.2f" % get_pool_level_sensor_battery_voltage)
    level_voltage = get_battery_percentage(get_pool_level_sensor_battery_voltage)
    update_database("system_status", "pool_level_batt_percentage", level_voltage)
    log.debug("Pool LEVEL Sensor battery voltage is {} and battery percentage is {}".format(get_pool_level_sensor_battery_voltage, level_voltage))
    get_pool_level_sensor_temp = read_emoncms_database("data", pooldb.pool_level_sensor_temp_table)
    get_pool_level_sensor_temp = float("%.2f" % get_pool_level_sensor_temp)
    pool_level_temp_c = float((get_pool_level_sensor_temp - 32) / 1.8)
    update_database("system_status", "pool_level_sensor_temp", get_pool_level_sensor_temp)
    log.debug("Pool LEVEL Sensor Box Temperature is: {}F and {}C".format(get_pool_level_sensor_temp, int(pool_level_temp_c)))

    # Get Pool Temp Sensor Information
    get_pool_temp_sensor_time = read_emoncms_database("time", pooldb.pool_temp_table)
    get_pool_temp_sensor_time = int("%1.0f" % get_pool_temp_sensor_time)
    log.debug("Pool TEMPERATURE Sensor last updated at: {}".format(get_pool_temp_sensor_time))
    pool_temp_sensor_time_delta = current_timestamp - get_pool_temp_sensor_time
    log.debug("Pool TEMPERATURE Time difference between last sensor reading is: {} seconds.".format(pool_temp_sensor_time_delta))
    get_pool_temp_sensor_humidity = read_emoncms_database("data", pooldb.pool_temp_sensor_humidity_table)
    get_pool_temp_sensor_humidity = int("%1.0f" % get_pool_temp_sensor_humidity)
    update_database("system_status", "pool_temp_sensor_humidity", get_pool_temp_sensor_humidity)
    log.debug("Pool TEMPERATURE Sensor Humidity is: {}%".format(get_pool_temp_sensor_humidity))
    get_pool_temp_sensor_battery_voltage = read_emoncms_database("data", pooldb.pool_temp_sensor_battery_table)
    get_pool_temp_sensor_battery_voltage = float("%1.2f" % get_pool_temp_sensor_battery_voltage)
    temp_voltage = get_battery_percentage(get_pool_temp_sensor_battery_voltage)
    update_database("system_status", "pool_temp_batt_percentage", temp_voltage)
    log.debug("Pool TEMPERATURE Sensor battery voltage is {} and battery percentage is {}".format(get_pool_temp_sensor_battery_voltage, temp_voltage))
    get_pool_temp_sensor_temp = read_emoncms_database("data", pooldb.pool_temp_sensor_temp_table)
    get_pool_temp_sensor_temp = float("%.2f" % get_pool_temp_sensor_temp)
    pool_temp_temp_c = float((get_pool_temp_sensor_temp - 32) / 1.8)
    update_database("system_status", "pool_temp_sensor_temp", get_pool_temp_sensor_temp)
    log.debug("Pool TEMPERATURE Sensor Box Temperature is: {}F and {}C".format(get_pool_temp_sensor_temp, int(pool_temp_temp_c)))

    # Get Garage Temp Sensor Information
    get_garage_temp_sensor_humidity = read_emoncms_database("data", pooldb.garage_temp_sensor_humidity_table)
    get_garage_temp_sensor_humidity = int("%1.0f" % get_garage_temp_sensor_humidity)
    update_database("system_status", "garage_temp_sensor_humidity", get_garage_temp_sensor_humidity)
    log.debug("Garage TEMP Sensor Humidity is: {}%".format(get_pool_level_sensor_humidity))
    get_garage_temp_sensor_battery_voltage = read_emoncms_database("data", pooldb.garage_temp_sensor_battery_table)
    get_garage_temp_sensor_battery_voltage = float("%1.2f" % get_garage_temp_sensor_battery_voltage)
    garage_temp_voltage = get_battery_percentage(get_garage_temp_sensor_battery_voltage)
    update_database("system_status", "garage_temp_batt_percentage", garage_temp_voltage)
    log.debug("Garage TEMP sensor battery voltage is {} and battery percentage is {}".format(get_garage_temp_sensor_battery_voltage, garage_temp_voltage))
    get_garage_current_temp = read_emoncms_database("data", pooldb.garage_temperature_table)
    get_garage_current_temp = float("%.2f" % get_garage_current_temp)
    garage_current_temp_c = float((get_garage_current_temp - 32) / 1.8)
    update_database("system_status", "garage_current_temp", get_garage_current_temp)
    log.debug("Garage TEMPERATURE is: {}F and {}C".format(get_garage_current_temp, int(garage_current_temp_c)))

    # Get Attic Temp Sensor Information
    get_attic_temp_sensor_battery_voltage = read_emoncms_database("data", pooldb.attic_temp_sensor_battery_table)
    get_attic_temp_sensor_battery_voltage = float("%1.2f" % get_attic_temp_sensor_battery_voltage)
    attic_temp_voltage = get_battery_percentage(get_attic_temp_sensor_battery_voltage)
    update_database("system_status", "attic_temp_batt_percentage", attic_temp_voltage)
    log.debug("Attic TEMP sensor battery voltage is {} and battery percentage is {}".format(get_attic_temp_sensor_battery_voltage, attic_temp_voltage))
    get_attic_current_temp = read_emoncms_database("data", pooldb.attic_temperature_table)
    get_attic_current_temp = float("%.2f" % get_attic_current_temp)
    attic_current_temp_c = float((get_attic_current_temp - 32) / 1.8)
    update_database("system_status", "attic_current_temp", get_attic_current_temp)
    log.debug("Attic TEMPERATURE is: {}F and {}C".format(get_attic_current_temp, int(attic_current_temp_c)))

    # Get Pool Filter Sensor Information
    get_pool_filter_psi = read_emoncms_database("data", pooldb.pool_filter_psi_table)
    get_pool_filter_psi = int("%1.0f" % get_pool_filter_psi)
    influx_data.write_data("filter_psi", get_pool_filter_psi)
    update_database("system_status", "filter_current_psi", get_pool_filter_psi)
    log.debug("Pool FILTER Pressure is: {} PSI".format(get_pool_filter_psi))

    # Check Our Sensors for Timeouts
    pool_level_timeout_alert_sent = read_database("notification_status", "pool_level_sensor_timeout_alert_sent")
    pool_level_lowvoltage_alert_sent = read_database("notification_status", "pool_level_low_voltage_alert_sent")
    pool_temp_timeout_alert_sent = read_database("notification_status", "pool_temp_sensor_timeout_alert_sent")
    pool_temp_lowvoltage_alert_sent = read_database("notification_status","pool_temp_low_voltage_alert_sent")
    pool_filter_psi_alert_sent = read_database("notification_status","pool_filter_psi_alert_sent")
    pool_level_sensor_notifications = read_database("notification_settings","pool_level_sensor_notifications")
    pool_temp_sensor_notifications = read_database("notification_settings","pool_temp_sensor_notifications")
    pool_filter_psi_notifications = read_database("notification_settings","pool_filter_psi_notifications")


    if pool_level_sensor_time_delta > pooldb.max_pool_level_sensor_time_delta:
        if pool_level_timeout_alert_sent:
            pass
        else:
            log.warning("* * * * WARNING * * * *\nPool LEVEL sensor timeout!")
            notify("pool_level_sensor_notifications", "Pool Level Sensor Timeout", "Your Pool Level Sensor has Timed Out!")
            update_database("notification_status", "pool_level_sensor_timeout_alert_sent", True)
            update_database("sensor_status", "pool_level_sensor_ok", False)

    elif pool_level_sensor_time_delta < pooldb.max_pool_level_sensor_time_delta and pool_level_timeout_alert_sent:
        update_database("notification_status", "pool_level_sensor_timeout_alert_sent", False)
        update_database("sensor_status", "pool_level_sensor_ok", True)
        notify("pool_level_sensor_notifications", "Pool Level Sensor Timeout Has Ended", "Your Pool Level Sensor is Back Online!")

    elif get_pool_level_sensor_battery_voltage < pooldb.pool_level_sensor_low_voltage:
        if pool_level_lowvoltage_alert_sent:
            pass
        else:
            log.warning("* * * * WARNING * * * *\nPool LEVEL Sensor Battery Voltage LOW!")
            update_database("notification_status", "pool_level_low_voltage_alert_sent", True)
            update_database("sensor_status", "pool_level_sensor_ok", False)
            notify("pool_level_sensor_notifications", "Pool Level Sensor Low Voltage", "The battery is low in your pool level sensor.")

    elif get_pool_level_sensor_battery_voltage > pooldb.pool_level_sensor_low_voltage and pool_level_lowvoltage_alert_sent:
        update_database("notification_status", "pool_level_low_voltage_alert_sent", False)
        update_database("sensor_status", "pool_level_sensor_ok", True)
        log.debug("Pool LEVEL Sensor Battery level is Normal")

    elif pool_temp_sensor_time_delta > pooldb.max_pool_temp_sensor_time_delta:
        if pool_temp_timeout_alert_sent:
            pass
        else:
            log.warning("* * * * WARNING * * * *\nPool TEMP sensor timeout!")
            update_database("notification_status", "pool_temp_sensor_timeout_alert_sent", True)
            notify("pool_temp_sensor_notifications", "Pool Temp Sensor Timeout", "Your Pool Temp Sensor has Timed Out!")

    elif pool_temp_sensor_time_delta < pooldb.max_pool_temp_sensor_time_delta and pool_temp_timeout_alert_sent:
        update_database("notification_status", "pool_temp_sensor_timeout_alert_sent", False)
        notify("pool_temp_sensor_notifications", "Pool Temp Sensor Timeout Has Ended", "Your Pool Temp Sensor is Back Online!")

    elif get_pool_temp_sensor_battery_voltage < pooldb.pool_level_sensor_low_voltage:
        if pool_temp_lowvoltage_alert_sent:
            pass
        else:
            log.warning("* * * * WARNING * * * *\nPool TEMP Sensor Battery Voltage LOW!")
            update_database("notification_status", "pool_temp_low_voltage_alert_sent", True)
            notify("pool_temp_sensor_notifications", "Pool Temp Sensor Low Voltage", "The battery is low in your pool temp sensor.")

    elif get_pool_temp_sensor_battery_voltage > pooldb.pool_level_sensor_low_voltage and pool_temp_lowvoltage_alert_sent:
        update_database("notification_status", "pool_temp_low_voltage_alert_sent", False)
        log.info("Pool TEMP Sensor Battery level is Normal")

    elif get_pool_filter_psi > pooldb.pool_filter_max_psi:
        if pool_filter_psi_alert_sent:
            pass
        else:
            log.warning("* * * * WARNING * * * *\nPool Filter Pressure HIGH - BAckflush your filter!")
            update_database("notification_status", "pool_filter_psi_alert_sent", True)
            notify("pool_filter_psi_notifications", "Pool Filter HIGH PSI", "It is time to BACK FLUSH your pool filter")
            log.warning("Pool filter PSI is HIGH!")

    elif get_pool_filter_psi < pooldb.pool_filter_max_psi_reset and pool_filter_psi_alert_sent:
        update_database("notification_status", "pool_filter_psi_alert_sent", False)
        log.debug("Pool filter PSI is Normal")

    else:
        log.debug("Everything appears to be OK with the pool sensors!")


def get_pool_level():
    log.debug("get_pool_level() started")
    pool_manual_fill = read_database("filling_status", "pool_manual_fill")
    alexa_manual_fill = read_database("filling_status", "alexa_manual_fill")
    pool_fill_notifications = read_database("notification_settings", "pool_fill_notifications")
    if pool_manual_fill:
        current_timestamp = int(time.time())
        log.debug("Pool is Manually Filling - Automatic Fill disabled!")
        pool_fill_start_time = int(read_database("filling_time", "pool_fill_start_time"))
        pool_fill_total_time = (current_timestamp - int(pool_fill_start_time)) / 60
        update_database("filling_time", "pool_fill_total_time", pool_fill_total_time)
        current_fill_gallons = calculate_current_fill_gallons()
        log.debug("Pool has been MANUALLY filling for {} minutes.".format(pool_fill_total_time))
        log.debug("Current gallons of water added to pool: {} gallons".format(current_fill_gallons))
        if pool_fill_total_time >= pooldb.max_pool_fill_time:
            update_database("filling_status", "fill_critical_stop", True)
            notify("pool_fill_notifications", "Pool MANUAL Fill Critical Stop", "Your Pool has been MANUALLY filling too long. Critical Stop. Check System!")
            update_database("notification_status", "critical_stop_warning_sent", True)
            pool_fill_valve("CRITICALCLOSE")
            update_database("filling_status", "pool_manual_fill", False)
            log.critical("CRITICAL STOP!! Pool Max Fill Time Exceeded!")
        pass
    elif alexa_manual_fill:
        current_timestamp = int(time.time())
        log.debug("Alexa is  Manually Filling the Pool - Automatic Fill disabled!")
        pool_fill_start_time = int(read_database("filling_time", "pool_fill_start_time"))
        pool_fill_total_time = (current_timestamp - int(pool_fill_start_time)) / 60
        update_database("filling_time", "pool_fill_total_time", pool_fill_total_time)
        current_fill_gallons = calculate_current_fill_gallons()
        log.debug("Alexa has been MANUALLY filling the Pool for {} minutes.".format(pool_fill_total_time))
        log.debug("Current gallons of water added to pool: {} gallons".format(current_fill_gallons))
        if pool_fill_total_time >= pooldb.alexa_max_pool_fill_time:
            pool_fill_valve("ALEXA_CLOSE")

    else:
        """ Function to get the current level of our pool from our MySQL DB. """
        get_pool_level_value = read_emoncms_database("data", pooldb.pool_level_table)
        pool_level_percentage = get_pool_level_percentage(get_pool_level_value)
        update_database("pool_level", "pool_level_percentage", pool_level_percentage)
        influx_data.write_data("pool_level", pool_level_percentage)
        log.debug("pool_sensors: Pool Level Percentage is {}".format(pool_level_percentage))
        pool_is_filling = read_database("filling_status", "pool_is_filling")
        critical_stop = read_database("filling_status", "fill_critical_stop")
        current_timestamp = int(time.time())
        if get_pool_level_value == 0:
            get_pool_level = "LOW"
            if pool_is_filling:
                pool_fill_start_time = int(read_database("filling_time", "pool_fill_start_time"))
                pool_fill_total_time = (current_timestamp - int(pool_fill_start_time)) / 60
                update_database("filling_time", "pool_fill_total_time", pool_fill_total_time)
                current_fill_gallons = calculate_current_fill_gallons()
                log.debug("Pool has been AUTOMATICALLY filling for {} minutes.".format(pool_fill_total_time))
                log.debug("Pool has been filling for {} minutes.\nCurrent number of gallons added to pool: {} gallons.".format(pool_fill_total_time, current_fill_gallons))
                if pool_fill_total_time >= pooldb.max_pool_fill_time:
                    update_database("filling_status", "fill_critical_stop", True)
                    notify("pool_fill_notifications", "Pool Fill Critical Stop", "Your Pool has been filling too long. Critical Stop. Check System!")
                    update_database("notification_status", "critical_stop_warning_sent", True)
                    pool_fill_valve("CRITICALCLOSE")
                    log.critical("CRITICAL STOP!! Pool Max Fill Time Exceeded!")
                pass
            else:
                if critical_stop:
                    log.critical("CRITICAL STOP!! Pool Max Fill Time Exceeded!")
                    critical_stop_enabled_warning_sent = read_database("notification_status", "critical_stop_enabled_warning_sent")
                    if not critical_stop_enabled_warning_sent:
                        notify("pool_fill_notifications", "Pool Fill Requested During Critical Stop", "Your Pool Fill is DISABLED due to Critical Stop and is LOW. Please check system!")
                        update_database("notification_status", "critical_stop_enabled_warning_sent", True)
                    pass
                else:
                    log.debug("get_pool_level() returned pool_level = LOW")
                    pool_autofill_active = read_database("system_status", "pool_autofill_active")
                    if pool_autofill_active:
                        pool_fill_valve("OPEN")
                    else:
                        log.info("Pool is low and needs filling, but pool_autofill has been disabled!")


        elif get_pool_level_value == 2:
            get_pool_level = "OK"
            log.debug("get_pool_level() returned pool_level = OK")
            if pool_is_filling:
                log.info("Pool LEVEL is back to normal!")
                pool_fill_valve("CLOSE")
        else:
            if pool_is_filling:
                pool_fill_start_time = int(read_database("filling_time", "pool_fill_start_time"))
                pool_fill_total_time = (current_timestamp - int(pool_fill_start_time)) / 60
                update_database("filling_time", "pool_fill_total_time", pool_fill_total_time)
                current_fill_gallons = calculate_current_fill_gallons()
                log.debug("Pool has been filling for {} minutes.\nCurrent number of gallons added to pool: {} gallons.".format(pool_fill_total_time, current_fill_gallons))
                if pool_fill_total_time >= pooldb.max_pool_fill_time:
                    update_database("filling_status", "fill_critical_stop", True)
                    notify("pool_fill_notifications", "Pool Fill Critical Stop", "Your Pool has been filling too long. Critical Stop. Check System!")
                    log.warning("Pool Fill Critical Stop - Your Pool has been filling too long. Critical Stop. Check System!")
                    update_database("notification_status", "critical_stop_warning_sent", True)
                    pool_fill_valve("CRITICALCLOSE")
                    log.critical("CRITICAL STOP!! Pool Max Fill Time Exceeded!")
                get_pool_level = "MIDWAY"
            else:
                get_pool_level = "MIDWAY"
        log.debug("Our Pool Level is {}.".format(get_pool_level))

def pool_pump_running_chemical():
    pool_pump_running_chemical = GPIO.input(pool_pump_running_pin)
    if not pool_pump_running_chemical:
        log.debug("Pool Pump Running via Chemical Sensor Chamber: TRUE - PUMP IS RUNNING")
    else:
        log.debug("Pool Pump Running via Chemical Sensor Chamber: FALSE - PUMP IS OFF")

def acid_level():
    log.debug("acid_level() started")
    acid_level_ok = GPIO.input(acid_level_sensor_pin)
    if acid_level_ok:
        acid_level_status = read_database("acid_level", "acid_level_ok")
        if not acid_level_status:
            update_database("acid_level", "acid_level_ok", True)
            log.info("Pool ACID Level is back to normal.")

        acid_alert_sent = read_database("notification_status", "acid_level_low_alert_sent")
        if acid_alert_sent:
            update_database("notification_status", "acid_level_low_alert_sent", False)
        log.debug("Acid Level - OK")
    else:
        pool_acid_level_notifications = read_database("notification_settings", "pool_acid_level_notifications")
        acid_alert_sent = read_database("notification_status", "acid_level_low_alert_sent")
        if acid_alert_sent:
            acid_alert_sent_time = int(read_database("notification_status", "acid_level_low_alert_sent_time"))
            acid_alert_sent_delta_time = (current_timestamp - acid_alert_sent_time) / 60
            time_to_next_acid_alert = (pooldb.pool_acid_alert_max_minutes - acid_alert_sent_delta_time)
            log.debug("Acid LOW Level Alert sent {} minuntes ago. Next Alert will be sent in {} minutes".format(acid_alert_sent_delta_time, time_to_next_acid_alert))

            if acid_alert_sent_delta_time >= pooldb.pool_acid_alert_max_minutes:
                notify("pool_acid_level_notifications", "Pool Acid Level is STILL LOW", "Your Acid Level is STILL LOW. Please refill!")
                update_database("notification_status", "acid_level_low_alert_sent_time", current_timestamp)
                log.warning("Pool ACID Level STILL low. Alert sent again!")
            log.info("Pool Acid Level - LOW")
        else:
            log.info("Pool Acid Level - LOW")
            notify("pool_acid_level_notifications", "Pool Acid Level is LOW", "Your Acid Level is LOW. Please refill!")
            update_database("acid_level", "acid_level_ok", False)
            update_database("notification_status", "acid_level_low_alert_sent", True)
            update_database("notification_status", "acid_level_low_alert_sent_time", current_timestamp)
            log.debug("Pool ACID Level is LOW!")

# TODO Why do I have this here? Maybe need to move other pool_temp info to call this function.
# Reads our pool temperature from MySQL DB
def get_pool_temp():
    log.debug("get_pool_temp() Started")
    get_pool_temp = read_emoncms_database("data", pooldb.temp_probe_table)
    get_pool_temp = float("%.2f" % get_pool_temp)
    pool_temp_c = float((get_pool_temp - 32) / 1.8)
    log.info("get_pool_temp returned {}F and {}C".format(get_pool_temp, int(pool_temp_c)))
    update_database("system_status", "pool_current_temp", get_pool_temp)
    log.debug("get_pool_temp() Completed")
    return get_pool_temp



def check_system_status():
    log.debug("check_system_status() started.")
    update_database("system_status", "current_military_time", current_military_time)
    system_reset_required = read_database("reset_status", "system_reset_required")
    critical_stop = read_database("filling_status", "fill_critical_stop")
    if system_reset_required:
        pool_fill_control_reset_notifications = read_database("notification_settings", "pool_fill_control_reset_notifications")
        log.info("System Reset Requested.")
        # Make sure water is shut off
        pool_fill_valve("RESET")
        # Reset all LEDs to OFF
        led_control(pool_fill_valve_disabled_led, "False")
        led_control(sprinkler_run_led, "False")
        led_control(pump_run_led, "False")
        led_control(system_run_led, "False")
        led_control(pool_filling_led, "False")
        led_control(system_error_led, "False")
        led_control(manual_fill_button_led, "False")
        # Reset LED Status Values
        update_database("led_status", "pool_fill_valve_disabled_led", False)
        update_database("led_status", "sprinkler_run_led", False)
        update_database("led_status", "pump_run_led", False)
        update_database("led_status", "system_run_led", False)
        update_database("led_status", "pool_filling_led", False)
        update_database("led_status", "system_error_led", False)
        update_database("led_status", "manual_fill_button_led", False)
        # Reset fill status
        update_database("filling_status", "pool_is_filling", False)
        update_database("filling_status", "fill_critical_stop", False)
        update_database("filling_status", "pool_manual_fill", False)
        update_database("filling_status", "pool_manual_fill", False)
        # Rest Pool Fill Time
        update_database("filling_time", "pool_fill_total_time", 0)
        # Reset Notifications
        update_database("notification_status", "critical_stop_enabled_warning_sent", False)
        update_database("notification_status", "pool_level_sensor_timeout_alert_sent", False)
        update_database("notification_status", "pool_level_low_voltage_alert_sent", False)
        update_database("notification_status", "pool_temp_sensor_timeout_alert_sent", False)
        update_database("notification_status", "pool_temp_low_voltage_alert_sent", False)
        update_database("notification_status", "pool_filter_psi_alert_sent", False)
        update_database("notification_status", "pool_filling_sent", False)
        update_database("notification_status", "critical_time_warning_sent", False)
        update_database("notification_status", "critical_stop_warning_sent", False)
        update_database("notification_status", "pool_database_error_alert_sent", False)
        update_database("notification_status", "acid_level_low_alert_sent", False)
        update_database("notification_status", "pump_not_running_error_alert_sent", False)
        # Turn on our System Run LED now that everything has been reset back to normal.
        led_control(system_run_led, "True")
        update_database("led_status", "system_run_led", True)
        # Reset our Reset Required Value
        update_database("reset_status", "system_reset_required", False)
        # Let me know the reset has been completed
        notify("pool_fill_control_reset_notifications", "Pool Fill Control RESET Complete", "Your Pool Fill Control has been reset to normal conditions.")
    else:
        log.debug("System Reset Status = No Reset Requested")
        # debug("System Reset Status = No Reset Requested")
        led_control(system_run_led, "True")
        update_database("led_status", "system_run_led", True)
    # TODO Create clear_critical_stop.py script also add a button to web interface (2019/01/15)
    if critical_stop:
        log.critical("CRITICAL STOP DETECTED")
        log.critical("Please check all systems and set [system_reset_required = True] in config file and restart program.")
        log.critical("This will reset all systems and restart the program.")


def is_pool_pump_running():
    log.debug("is_pool_pump_running() started.")
    """ Function to determine if our pool pump is running. This utilizes the pump_control_software and
    if the pump control software is not running it looks up how many watts are being  used by the pool
    panel. This should not e confused with the function pool_pump_running_ch() which utilizes GPIO 38 to detect
    if the pump is running utilizing a float switch connected to our pH/ORP chemical pot """
    # debug("is_pool_pump_running() Started")
    pump_control_active = read_database("pump_status", "pump_control_active")
    if pooldb.PUMP_DATA == "NODEJS":
        if pump_control_active:
            pool_pump_running_watts = get_pump_data("watts")
        else:
            pool_pump_running_watts = read_emoncms_database("data", pooldb.pump_running_watts_table)
            pool_pump_running_watts = int("%1.0f" % pool_pump_running_watts)
    else:
        pool_pump_running_watts = read_emoncms_database("data", pooldb.pump_running_watts_table)
        pool_pump_running_watts = int("%1.0f" % pool_pump_running_watts)
    log.info("pool_pump_running_watts returned {} watts in use by the pump.".format(pool_pump_running_watts))
    update_database("pump_status", "pump_watts", pool_pump_running_watts)

    if pool_pump_running_watts > pooldb.max_wattage:
        led_control(pump_run_led, "True")
        pool_pump_running = True
        update_database("led_status", "pump_run_led", True)
        update_database("pump_status", "pump_running", True)
        log.debug("PUMP_RUN_LED should be ON. This is the YELLOW LED")
        pump_error_notification_sent = read_database("notification_status", "pump_not_running_error_alert_sent")
        if pump_error_notification_sent:
            log.debug("Pump Error CLEARED - Pump is currently programmed to be running and is running.")
            notify("pump_error_notifications", "Pump Error CLEARED - Pump is now Running!", "Your Pool Pump is currnetly programmed to run, and it is now running!")
            update_database("notification_status", "pump_not_running_error_alert_sent", False)
    else:
        led_control(pump_run_led, "False")
        pool_pump_running = False
        update_database("led_status", "pump_run_led", False)
        update_database("pump_status", "pump_running", False)
        if pump_control_active:
            pump_program_running = read_database("pump_status", "pump_program_running")
            if pump_program_running in ("program_1", "program_2", "program_3", "program_4"):
                log.warning("Pump is currently programmed to be running but it is NOT running. Please Check Pool System!")
                pump_error_notification_sent = read_database("notification_status", "pump_not_running_error_alert_sent")
                if not pump_error_notification_sent:
                    notify("pump_error_notifications", "Pump Error - Pump Not Running!", "Your Pool Pump is currnetly programmed to run, but it is not running. Check your system!")
                    update_database("notification_status", "pump_not_running_error_alert_sent", True)
        log.debug("PUMP_RUN_LED should be OFF. This is the YELLOW LED")
    log.debug("is_pool_pump_running() completed.")
    return pool_pump_running


# This is where we check to see if we can talk to our database. If not, stop and send notification.
#TODO Check all databases and database servers (emoncms & pool_control)
#TODO rewrite notification as it will not work if we cannot read from mysql
def is_database_online():
    log.debug("is_database_online() Started")
    pool_database_error_alert_sent = read_database("notification_status","pool_database_error_alert_sent")
    try:
        cnx = mysql.connector.connect(user=db_info.emoncms_username,
                                      password=db_info.emoncms_password,
                                      host=db_info.emoncms_servername,
                                      database=db_info.emoncms_db,
                                      raise_on_warnings=True)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            log.critical("Database connection failure: Please check your username and password!")
            if not pool_database_error_alert_sent:
                notify("pool_database_notifications", "Pool DB ACCESS DENIED Failure!", "Pool DB ACCESS DENIED Failure. Check your username/password and other access settings and reenable the system!")
                update_database("notification_status", "pool_database_error_alert_sent", True)
            exit()    
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            log.critical("Database Error: Database does not exist. Please check your settings.")
            if not pool_database_error_alert_sent:
                notify("pool_database_notifications", "Pool DB Connection Failure!", "Pool DB does not exist. Check your settings and reenable the system!")
                update_database("notification_status", "pool_database_error_alert_sent", True)
            exit()
        elif err.errno == errorcode.CR_CONN_HOST_ERROR:
            log.critical("Database Error: Cannot connect to MySQL database. Please check your settings.")
            if not pool_database_error_alert_sent:
                notify("pool_database_notifications", "Pool DB Connection Failure!", "Cannot Connect to MySQL Server. Check your settings and reenable the system!")
                update_database("notification_status", "pool_database_error_alert_sent", True)
            exit()
        else:
            log.critical("Database Error: Unknown Error.")
            if not pool_database_error_alert_sent:
                notify("pool_database_notifications", "Pool DB Connection Failure!", "Pool DB error. Check your settings and reenable the system!")
                update_database("notification_status", "pool_database_error_alert_sent", True)
            exit()
    else:
        if pool_database_error_alert_sent:
            update_database("notification_status", "pool_database_error_alert_sent", False)
            notify("pool_database_notifications", "Pool DB Back Online!", "Your Pool Database is back online. System is Normal!")
            cnx.close()
            pass
        else:
            cnx.close()
            log.debug("is_database_online() Completed - DB is Online")
            pass

# TODO Convert == Yes to bool
def get_current_ph():
    log.debug("get_current_ph() started.")
    if pooldb.ph_probe == "Yes":
        if pooldb.temp_probe == "Yes":
            pool_temp = float(read_database("system_status", "pool_current_temp"))
            current_ph = get_ph.get_current_ph_with_temp(pool_temp)
        else:
            current_ph = get_ph.get_current_ph_no_temp()
        log.debug("get_current_ph() completed.")
        return current_ph
    else:
        log.debug("get_current_ph() completed.")
        pass

def get_current_orp():
    log.debug("get_current_orp() started.")
    if pooldb.orp_probe == "Yes":
        current_orp = get_orp.get_current_orp()
        log.debug("get_current_orp completed.")
        return current_orp
    else:
        log.debug("get_current_orp completed.")
        pass

## The following three functions utilize the new Influx database engine(s) residing on 'scripts' located
## at our house as well as a second off-site server located in a datacenter in N. California. 
#TODO - Create database function tests to determine best database to use (MySQL or Influx). Default to local
# influx database, fallback to remote Influx database and then fall back to remote MySQL database. Fail if 
# no database connectivity or no internet connectivity for remote databases.

def get_current_solar():
    log.debug("get_current_solar() started.")
    current_solar_results = influx_data.read_energy_data("electrical_monitoring", "energy", "XXX340_ch4_w")
    if current_solar_results == "None":
        current_solar = 0
    else:
        current_solar = (int(float(current_solar_results)) * -1)
    log.debug("get_current_solar() completed.")
    return current_solar

def get_current_mains():
    log.debug("get_current_mains() started.")
    current_mains_results = influx_data.read_energy_data("electrical_monitoring", "energy", "XXX340_ch20_w")
    if current_mains_results == "None":
        current_mains = 0
    else:
        current_mains = (int(float(current_mains_results)))
    log.debug("get_current_mains() completed.")
    return current_mains

def calculate_total_power_consumption():
    log.debug("calculate_total_power_consumption() started.")
    current_mains = get_current_mains()
    current_solar = get_current_solar()
    total_consumption = (current_mains + current_solar)
    log.debug("Total current Power Utilizations is {0} watts. (InfluxDB)".format(total_consumption))
    log.debug("Total current Power Import is {0} watts. (InfluxDB)".format(current_mains))
    log.debug("Total current Solar Production is {0} watts. (InfluxDB)".format(current_solar))
    log.debug("calculate_total_power_consumption() completed.")
    return total_consumption


def get_last_fill_date():
    log.debug("get_last_fill_date() started.")
    last_fill_date = read_database_fill("pool_filling_history", "time")
    last_fill_date = last_fill_date.strftime("%m/%d/%Y")
    log.debug("Last Pool Fill Date was: {}".format(last_fill_date))
    log.debug("get_last_fill_date() completed.")
    return last_fill_date


# Here we go.......
def main():
    setup_logging()
 #   notify("pool_database_notifications", "Pool Control System Started", "Your Pool System Has Started!")
    log.debug("pool_control_master_db() Starting.")
    check_internet()  # If we have no internet, immediately exit() and check again in 1 minute. 
    is_database_online() # If we cannot communicate to our DB, immediately exit() and check again in 1 minute.
    check_pump_control_url()
    is_pool_pump_running()
    pool_pump_running_chemical()
    check_system_status()
  #  mightyhat_serial_setup() # See comment in function.
    get_pool_temp()
    check_pool_sensors()
    get_sprinkler_status()
    get_pool_level()
    get_gallons_total()
    acid_level()
    get_main_power_readings()
    calculate_total_power_consumption() # Testing InfluxDB
    get_pump_data("gpm")
    get_pump_data("rpm")
    get_pump_data("watts")
    get_ph_reading()
    get_orp_reading()
    get_last_fill_date()
    log.debug("pool_control_master_db() Completed.")
 #   notify("pool_database_notifications", "Pool Control System Completed", "Your Pool System Has Completed!")

if __name__ == '__main__':
    main()


