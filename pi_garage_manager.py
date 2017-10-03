#!/usr/bin/env python
""" Pi Garage Manager

Authors: Richard L. Lynch <rich@richlynch.com> and John Kyrus

Description: Emails, tweets, or sends an SMS if a garage door is left open
too long and allows you to open and close the door remotely.

Learn more at http://www.richlynch.com/code/pi_garage_alert
"""

##############################################################################
#
# The MIT License (MIT)
#
# Copyright (c) 2013-2014 Richard L. Lynch <rich@richlynch.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
##############################################################################

import time
from time import strftime
from datetime import datetime
from datetime import timedelta
import subprocess
import re
import sys
import signal
import json
import logging
import smtplib
import ssl
import traceback
from email.mime.text import MIMEText
import socket
from multiprocessing.connection import Listener
import multiprocessing
import threading
import requests
import httplib2
import RPi.GPIO as GPIO

sys.path.append('/usr/local/etc')
import pi_garage_manager_config as cfg

##############################################################################
# Email support
##############################################################################

class Email(object):
    """Class to send emails"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def send_email(self, recipient, subject, msg):
        """Sends an email to the specified email address.

        Args:
            recipient: Email address to send to.
            subject: Email subject.
            msg: Body of email to send.
        """
        self.logger.info("Sending email to %s: subject = \"%s\", message = \"%s\"", recipient, subject, msg)

        msg = MIMEText(msg)
        msg['Subject'] = subject
        msg['To'] = recipient
        msg['From'] = cfg.EMAIL_FROM
        msg['X-Priority'] = cfg.EMAIL_PRIORITY

        try:
            mail = smtplib.SMTP(cfg.SMTP_SERVER, cfg.SMTP_PORT)
            if cfg.SMTP_USER != '' and cfg.SMTP_PASS != '':
                mail.login(cfg.SMTP_USER, cfg.SMTP_PASS)
            mail.sendmail(cfg.EMAIL_FROM, recipient, msg.as_string())
            mail.quit()
        except:
            self.logger.error("Exception sending email: %s", sys.exc_info()[0])

##############################################################################
# IFTTT support using Maker Channel (https://ifttt.com/maker)
##############################################################################

class IFTTT(object):
    """Class to send IFTTT triggers using the Maker Channel"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def send_trigger(self, event, value1, value2, value3):
        """Send an IFTTT event using the maker channel.

        Get the key by following the URL at https://ifttt.com/services/maker/settings

        Args:
            event: Event name
            value1, value2, value3: Optional data to supply to IFTTT.
        """
        self.logger.info("Sending IFTTT event \"%s\": value1 = \"%s\", value2 = \"%s\", value3 = \"%s\"", event, value1, value2, value3)

        headers = {'Content-type': 'application/json'}
        payload = {'value1': value1, 'value2': value2, 'value3': value3}
        try:
            requests.post("https://maker.ifttt.com/trigger/%s/with/key/%s" % (event, cfg.IFTTT_KEY), headers=headers, data=json.dumps(payload))
        except:
            self.logger.error("Exception sending IFTTT event: %s", sys.exc_info()[0])

##############################################################################
# FIREBASE support https://firebase.google.com/docs/cloud-messaging/
##############################################################################

class Firebase(object):
    """Class to send Firebase notification triggers using Google's FCM"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def send_trigger(self, value1, value2, value3):
        """Send a Firebase event using the FCM.

        Get the server key by following the URL at https://console.firebase.google.com/

        Args:
            event: Event name
            value1, value2, value3: Optional data to supply to Firebase.
        """
        self.logger.info("Sending Firebase event: value1 = \"%s\", value2 = \"%s\", value3 = \"%s\"", value1, value2, value3)

	if cfg.FIREBASE_ID == '' or cfg.FIREBASE_KEY == '':
		self.logger.error("Firebase ID or KEY is empty")
	else:
	        time = format_duration(int(value3))
		body = "Your garage door has been " + value2 + " for " + time
		headers = { "Content-type": "application/json", "Authorization": cfg.FIREBASE_KEY }
		payload = ''

		if value1 == 'notification':
                    payload = { "notification": { "title": "Garage door alert", "text": body }, "data": { "event": value2 }, "to": cfg.FIREBASE_ID }
		else:
		    payload = { "data": { "event": value2 } , "to": cfg.FIREBASE_ID }

		try:
		    requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, json=payload)
		except:
		    self.logger.error("Exception sending Firebase event: %s", sys.exc_info()[0])

##############################################################################
# Logging and alerts
##############################################################################

def send_alerts(logger, alert_senders, recipients, subject, msg, state, time_in_state):
    """Send subject and msg to specified recipients

    Args:
        recipients: An array of strings of the form type:address
        subject: Subject of the alert
        msg: Body of the alert
        state: The state of the door
    """
    for recipient in recipients:
        if recipient[:6] == 'email:':
            alert_senders['Email'].send_email(recipient[6:], subject, msg)
        elif recipient[:6] == 'ifttt:':
            alert_senders['IFTTT'].send_trigger(recipient[6:], subject, state, '%d' % (time_in_state))
	elif recipient[:9] == 'firebase:':
            alert_senders['Firebase'].send_trigger(recipient[9:], state, '%d' % (time_in_state))
        else:
            logger.error("Unrecognized recipient type: %s", recipient)

##############################################################################
# Misc support
##############################################################################

def truncate(input_str, length):
    """Truncate string to specified length

    Args:
        input_str: String to truncate
        length: Maximum length of output string
    """
    if len(input_str) < (length - 3):
        return input_str

    return input_str[:(length - 3)] + '...'

def format_duration(duration_sec):
    """Format a duration into a human friendly string"""
    days, remainder = divmod(duration_sec, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    ret = ''
    if days > 1:
        ret += "%d days " % (days)
    elif days == 1:
        ret += "%d day " % (days)

    if hours > 1:
        ret += "%d hours " % (hours)
    elif hours == 1:
        ret += "%d hour " % (hours)

    if minutes > 1:
        ret += "%d minutes" % (minutes)
    if minutes == 1:
        ret += "%d minute" % (minutes)

    if ret == '':
        ret += "%d seconds" % (seconds)

    return ret

##############################################################################
# Garage Door Sensor support
##############################################################################

def get_garage_door_state():
    """Returns the state of the garage door on the specified pin as a string

    Args:
        pin: GPIO pin number.
    """
    if GPIO.input(15): # pylint: disable=no-member
        state = 'open'
    else:
        state = 'closed'

    return state

def get_uptime():
    """Returns the uptime of the RPi as a string
    """
    with open('/proc/uptime', 'r') as uptime_file:
        uptime_seconds = int(float(uptime_file.readline().split()[0]))
        uptime_string = str(timedelta(seconds=uptime_seconds))
    return uptime_string

##############################################################################
# Listener thread for getting/setting state and openning/closing the garage
##############################################################################

def doorTriggerLoop():
    address = (cfg.NETWORK_IP, int(cfg.NETWORK_PORT))
    listener = Listener(address)	    

    while True:
        # Receive incomming communications and set defaults
	conn = listener.accept()
	received_raw = ''
	received_raw = conn.recv_bytes()

	received = received_raw.lower()
	response = 'unknown command'
	trigger = False

        if received == 'trigger':
            trigger = True
            if state == 'open':
                response = 'closing'
            else:
                response = 'opening'
        elif received == 'open' or received == 'up':
            if state == 'open':
                response = 'already open'
            else:
                response = 'opening'
                trigger = True
        elif received == 'close' or received == 'down':
            if state == 'open':
                response = 'closing'
                trigger = True
            else:
                response = 'already closed'
	elif received == 'home' or received == 'set to home':
	    cfg.HOMEAWAY = 'home'
	    response = 'set to home'
        elif received == 'away' or received == 'set to away':
            cfg.HOMEAWAY = 'away'
            response = 'set to away'
        elif received == 'state' or received == 'status':
            response = get_garage_door_state() + ' and ' + cfg.HOMEAWAY
	elif received.startswith('firebase:'):
	    cfg.FIREBASE_ID = received_raw.replace('firebase:','')
            response = 'ok'

        conn.send_bytes(response)
	#self.logger.info('received ' + received_raw + '. ' + response)

        if trigger:
            GPIO.output(26, GPIO.LOW)
	    time.sleep(2)
	    GPIO.output(26, GPIO.HIGH)

        trigger = False
        time.sleep(1)

    conn.close()
    listener.close()

##############################################################################
# Main functionality
##############################################################################
class PiGarageAlert(object):
    """Class with main function of Pi Garage Alert"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def main(self):
        """Main functionality
        """

        try:
            # Set up logging
            log_fmt = '%(asctime)-15s %(levelname)-8s %(message)s'
            log_level = logging.INFO

            if sys.stdout.isatty():
                # Connected to a real terminal - log to stdout
                logging.basicConfig(format=log_fmt, level=log_level)
            else:
                # Background mode - log to file
                logging.basicConfig(format=log_fmt, level=log_level, filename=cfg.LOG_FILENAME)

            # Banner
            self.logger.info("==========================================================")
            self.logger.info("Pi Garage Manager Starting")

            # Use Raspberry Pi board pin numbers
            GPIO.setmode(GPIO.BOARD)
            # Configure the sensor pin as input
            self.logger.info("Configuring pin 15 and 26 for %s", cfg.NAME)
            GPIO.setup(15, GPIO.IN, pull_up_down=GPIO.PUD_UP)
	    # Configure the control pin for the relay to open and close the garage door
            GPIO.setup(26, GPIO.OUT, initial=GPIO.HIGH)
		
	    # Start garage door trigger listening thread
            self.logger.info("Listening for commands")
            doorTriggerThread = threading.Thread(target=doorTriggerLoop)
            doorTriggerThread.setDaemon(True)
            doorTriggerThread.start()

            # Configure global settings
            door_state = ''
            time_of_last_state_change = ''

            # Create alert sending objects
            alert_senders = {
                "Email": Email(),
                "IFTTT": IFTTT(),
		"Firebase": Firebase()
            }

            # Read initial states
            name = cfg.NAME
            state = get_garage_door_state()
            door_state = state
            time_of_last_state_change = time.time()
            alert_state = 0

            self.logger.info("Initial state of \"%s\" is %s", name, state)

            # Prepare socket to listen for commands
            address = (cfg.NETWORK_IP, int(cfg.NETWORK_PORT))
            listener = Listener(address)

            while True:
                state = get_garage_door_state()
                time_in_state = time.time() - time_of_last_state_change

                # Check if the door has changed state
                if door_state != state:
                    door_state = state
                    time_of_last_state_change = time.time()
                    self.logger.info("State of %s changed to %s after %.0f sec", name, state, time_in_state)

                    # Reset alert when door changes state
                    alert_state = 0
                    # Reset time_in_state
                    time_in_state = 0

                # See if there are any alerts
                for alert in cfg.ALERTS:

                    if alert_state == 0:
                        # Get start and end times and only alert if current time is in between
                        time_of_day = int(datetime.now().strftime("%H"))
                        start_time = alert['start']
                        end_time = alert['end']
                        send_alert = False

                        # If system is set to away and the door is a open send an alert
                        if cfg.HOMEAWAY == 'away' and state == 'open':
                            send_alert = True
                        # Is start and end hours in the same day?
                        elif start_time < end_time:
                            # Is the current time within the start and end times and has the time elapsed and is this the state to trigger the alert?
                            if time_of_day >= start_time and time_of_day <= end_time and time_in_state > alert['time'] and state == alert['state']:
                                send_alert = True
                        elif start_time > end_time:
                            if (time_of_day >= start_time or time_of_day <= end_time) and time_in_state > alert['time'] and state == alert['state']:
                                send_alert = True

                        if send_alert:
                            send_alerts(self.logger, alert_senders, alert['recipients'], name, "%s has been %s for %d seconds!" % (name, state, time_in_state), state, time_in_state)
                            alert_state += 1
				
        except:
            logging.critical("Terminating process")
	finally:
	    GPIO.cleanup()
    	    print 'Exiting pi_garage_manager.py'
    	    sys.exit(0)

if __name__ == "__main__":
    PiGarageAlert().main()
