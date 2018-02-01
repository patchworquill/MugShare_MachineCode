import argparse
import smtplib
from email.mime.text import MIMEText

# Example
# 1. -r "RecipientOne; RecipientTwo" -m ABC -e SenderEmail -p Password
# 2. -r RecipientOne;RecipientTwo -m ABC -e SenderEmail -p Password

# Parse information 
parser = argparse.ArgumentParser()
parser.add_argument('-r', help='List of email recipients separated by semicolons')
parser.add_argument('-m', help='Name of the mug share machine to be refilled')
parser.add_argument('-e', help='Gmail email for sending the notification email')
parser.add_argument('-p', help='Password for the Gmail account')
args = parser.parse_args()

# Sender log in information
recipients = args.r.split(';')
machine = args.m
sender = args.e
sender_pwd = args.p

# Email content
msg = MIMEText('Hi Mug Share staff,\n\nMug Machine ' + machine + 'needs to be refilled!\n\nThank you!')
msg['Subject'] = 'Refill Mug Share Machine Notification'
msg['From'] = sender
msg['To'] = ", ".join(recipients)

# Send email
server = smtplib.SMTP('smtp.gmail.com',587)
server.starttls()
server.login(sender, sender_pwd)
server.sendmail(sender, recipients, msg.as_string()) #recipients needs to be in an array
server.quit()