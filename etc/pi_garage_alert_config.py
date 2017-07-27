#!/usr/bin/python2.7

##############################################################################
# Global settings
##############################################################################

# Describes all the garage doors being monitored
# time is in seconds
# start and end hours can be [0-23] - will alert only within those hours
GARAGE_DOORS = [
#    {
#        'pin': 16,
#        'name': "Garage Door 1",
#        'alerts': [
#            {
#                'state': 'open',
#                'time': 120,
#                'recipients': [ 'sms:+11112223333', 'sms:+14445556666' ]
#            },
#            {
#                'state': 'open',
#                'time': 600,
#                'recipients': [ 'sms:+11112223333', 'sms:+14445556666' ]
#            }
#        ]
#    },

    {
        'pin': 15,
        'name': "Garage Door",
        'alerts': [
            {
                'state': 'open',
                'time': 300,
                'start': 23,
                'end': 7,
                'recipients': [ 'ifttt:garage_event' ]
            },
            {
                'state': 'open',
                'time': 7200,
                'start': 0,
                'end': 23,
                'recipients': [ 'ifttt:garage_event' ]
            }
        ]
    }
]
##############################################################################
# Home and away setting. Set it to away with the app when you are on vacation
# to trigger an alert immediately if the garage door is open.
# Default setting on startup is home
##############################################################################
HOMEAWAY = ''

# All messages will be logged to stdout and this file
LOG_FILENAME = "/var/log/pi_garage_alert.log"

##############################################################################
# Email settings
##############################################################################

SMTP_SERVER = 'localhost'
SMTP_PORT = 25
SMTP_USER = ''
SMTP_PASS = ''
EMAIL_FROM = 'Garage Door <user@example.com>'
EMAIL_PRIORITY = '1'
# 1 High, 3 Normal, 5 Low

##############################################################################
# IFTTT Maker Channel settings
# Create an applet using the "Maker" channel, pick a event name,
# and use the event name as a recipient of one of the alerts,
# e.g. 'recipients': [ 'ifft:garage_event' ]
#
# Get the key by going to https://ifttt.com/services/maker/settings.
# The key is the part of the URL after https://maker.ifttt.com/use/.
# Do not include https://maker.ifttt.com/use/ in IFTTT_KEY.
##############################################################################

IFTTT_KEY = ''

##############################################################################
# use ifconfig to find your ip address or use localhost
##############################################################################
NETWORK_IP = 'localhost'
NETWORK_PORT = '6000'
