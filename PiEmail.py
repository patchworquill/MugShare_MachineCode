import argparse
import smtplib
import info.emailINFO as emailINFO
from email.mime.text import MIMEText
#Function
#   Purpose - email the recipients a short message requesting a machine refill
#   Inputs  - Machine ID and measured capacity
def reqRefill(machine, cap):

    #stored in EmailInfo file
    recipients = emailINFO.recipients.split(';')
    
    # Email content
    msg = MIMEText('Hi Mug Share staff,\n\nMug Machine ' + machine + ' is at ' + cap + '% and needs to be refilled!\n\nThank you!')
    msg['Subject'] = 'Refill Mug Share Machine Notification'
    msg['From'] = emailINFO.sender
    msg['To'] = ", ".join(emailINFO.recipients)

    # Send email
    server = smtplib.SMTP('smtp.gmail.com',587)
    server.starttls()
    server.login(emailINFO.sender, emailINFO.sender_pwd)
    server.sendmail(emailINFO.sender, emailINFO.recipients, msg.as_string()) #recipients needs to be in an array
    server.quit()
