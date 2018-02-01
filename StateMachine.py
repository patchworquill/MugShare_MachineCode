#!/usr/bin/python
import serial
import RPi.GPIO as GPIO
import time
import info.machINFO as mi
import DBInterface as db
import PiEmail as email
import Tkinter as tk
import os
import ttk
import tkFont
from Tkinter import *

#Setup for servo controls
SERVO_FREQ = 50 #needs to be confirmed
SERVO_DOWN = 11.5 #Duty Cycle of 180 degrees (Approx 2ms) divided by SERVO_FREQ
SERVO_UP = 2.5 ##Duty Cycle of 0 degrees (Approx 1ms) divided by SERVO_FREQ
SERVO_DELAY = 0.2 #delay in seconds
PULSE_DELAY = 0.5 #time the Pi sends a waveform to the Servos

#Servo GPIO pin numbers
TOP_SERVO = 13
BOT_SERVO = 15

#Lock pin number
LOCK = 11

#IR sensors in the mug magazine, higher number corresponds to higher on the magazine
IR_01 = 7
IR_02 = 8
IR_03 = 9
IR_04 = 10

#IR Constants
IR_CLOSE = GPIO.HIGH
IR_FAR = GPIO.LOW

#Misc Constants
HAS_MUG = 1
NOT_IN_DB = 2

#default msgs
default_msg = "Need a mug?\nPlease swipe your UBC card to rent one!"

#Function
#   Purpose - Reads the RFID of a mug when called.
#   Return  - A string
def readMugID():
    #Open RFID reader for scanning
    ser = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout = 3)
    tag = ''

    while 1:
        data = ser.read()
        #Look for the end of the RFID string
        if data == '':
            return -1
        if data == '\r':
            return tag
            break
        else:
            tag = tag + data
    
#Class holder for the GUI and Device Controller logic
class Application(tk.Frame):

    #Initialization function to show the GUI
    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.pack()
        self.setup()
        root.title("Mugshare Machine Application")

    #Setup function to initialize variables, setup IO devices, create GUI, and push any leftover changes to the database. 
    def setup(self):
        self.setupIO()
        self.totalMugsDisp = 0
        self.createWidgets()
        self.grabSelfData()
        self.staff_menu = 0
        self.out_of_order = 0
        self.mugID = ''
        self.last_error = ""
        self.dbCatchUp()

    #Function
    #   Purpose - Push leftover changes from a previous session to the database
    #   Updates - Clears service_log.txt file only when the changes have been pushed successfully
    def dbCatchUp(self):
        #Try to open the service_log.txt file if it exists.
        try:
            target = open('service_log.txt', 'r')
        except IOError:
            #Create the file if it is missing and assume no changes need to be pushed
            target = open('service_log.txt', 'w')
            target.close()
            print "Service log created."
            return

        #Read the variables for the last database changes to be pushed if there are any
        lastCmd = target.readline()
        if os.stat('service_log.txt').st_size == 0:
            print "No leftover cmds"
            target.close()
            return
        
        print lastCmd
        var = lastCmd.split(",")
        target.close()

        #Try to push the changes 3 times
        trials = 0
        cutOff = 0
        while trials < 3:
            mugAttempt = db.tryMug(int(var[0]), var[1], var[2], int(var[3]), int(var[4]))
            if mugAttempt == 0:
                print "complete"
                break
            elif mugAttempt == HAS_MUG:
                print "User already registered to a mug."
                break
            elif mugAttempt == NOT_IN_DB:
                print "User not found in database. Please register for the program.\n"
                break
            else:
                cutOff = mugAttempt
                trials += 1

        if trials >= 3:
            #Issue persists and the command failed again
            self.outOfOrder()
        else:
            #Clear the file of the only log
            target = open('service_log.txt', 'w')
            target.seek(0)
            target.truncate()
            target.close()
            
    #Function
    #   Purpose - Assign the pins for IO devices and initialize the starting positions of the servos
    def setupIO(self):
        GPIO.setmode(GPIO.BOARD)
        
        GPIO.setup(TOP_SERVO, GPIO.OUT)
        GPIO.setup(BOT_SERVO, GPIO.OUT)

        self.tServo = GPIO.PWM(TOP_SERVO, SERVO_FREQ)
        self.bServo = GPIO.PWM(BOT_SERVO, SERVO_FREQ)

        self.tServo.start(SERVO_UP)
        time.sleep(PULSE_DELAY)
        self.tServo.ChangeDutyCycle(0)

        time.sleep(SERVO_DELAY)
        
        self.bServo.start(SERVO_DOWN)
        time.sleep(PULSE_DELAY)
        self.bServo.ChangeDutyCycle(0)
        
        time.sleep(SERVO_DELAY)

        GPIO.setup(LOCK, GPIO.OUT)
        GPIO.output(LOCK, GPIO.LOW) #Low is locked, high is unlocked

        #GPIO.setup(tTrayIR, GPIO.IN)
        #GPIO.setup(bTrayIR, GPIO.IN)
        
        #GPIO.setup(IR_01, GPIO.IN)
        #GPIO.setup(IR_02, GPIO.IN)
        #GPIO.setup(IR_03, GPIO.IN)
        #GPIO.setup(IR_04, GPIO.IN)
        
        print "Done IO Setup"

    #Function
    #   Purpose - Read in and process either a staff attempt or a mug rental when triggered
    def idInput(self, event):

        #Retrieve the userID from the card reader
        self.id_entry.focus_set()
        self.userID = self.idHolder.get()
        self.id_entry.delete(0, 'end')
        start = self.userID.find("=") + 1
        self.userID = int(self.userID[start:self.userID.find("=", start)])
        
        #Disable the cardreader to prevent additional requests until the current request is processed
        self.id_entry["state"] = 'disabled'
        #Disable staff button
        self.staff_menu_button.place_forget()

        #Attempt to access the staff menu
        if self.staff_menu == 1 or self.out_of_order == 1:
            trials = 0
            #Attempt to contact database for information 3 times
            while trials < 3:
                staffAttempt = db.tryStaff(self.userID)
                if staffAttempt == True:
                    self.openStaff()
                    break
                elif staffAttempt == False:
                    self.msg.set("Card is not valid.")
                    self.staff_menu = 0
                    self.cont_button.place(relx=0.5, y = 400, anchor = CENTER)
                    break
                else:
                    trials = trials + 1
                    
            #Trials all failed
            if trials >= 3:
                self.last_error = "SQL command failed to execute."
                self.outOfOrder()
                    
        else:
            trials = 0
            while trials < 3:
                mugAttempt = 0#db.checkUser(self.userID)
                if mugAttempt == 0:
                    break
                elif mugAttempt == HAS_MUG:
                    self.msg.set("User is already registered to a mug.")
                    self.cont_button.place(relx=0.5, y = 400, anchor = CENTER)
                    return
                elif mugAttempt == NOT_IN_DB:
                    print "User not found in database. Please register for the program.\n"
                    self.msg.set("User not found in database. Please register for the program.")
                    self.cont_button.place(relx=0.5, y = 400, anchor = CENTER)
                    return
                else:
                    cutOff = mugAttempt
                    trials += 1
            if trials >= 3:
                self.last_error = "SQL command failed to execute."
                self.outOfOrder()
                return

            #Lower a mug into the scanning zone
            self.bServo.ChangeDutyCycle(SERVO_DOWN)
            time.sleep(PULSE_DELAY)
            self.bServo.ChangeDutyCycle(0)
            time.sleep(SERVO_DELAY)
            
            self.tServo.ChangeDutyCycle(SERVO_DOWN)
            #Begin scanning for the RFID immediately.
            self.mugID = readMugID()
            print self.mugID

            time.sleep(PULSE_DELAY)
            
            #Writing 0 to the servo to prevent the servo from drifting away from proper position
            self.tServo.ChangeDutyCycle(0)
            time.sleep(SERVO_DELAY)
            
            self.tServo.ChangeDutyCycle(SERVO_UP)
            time.sleep(PULSE_DELAY)
            self.tServo.ChangeDutyCycle(0)
            time.sleep(SERVO_DELAY)
            
            self.bServo.ChangeDutyCycle(SERVO_DOWN)
            time.sleep(PULSE_DELAY)
            self.bServo.ChangeDutyCycle(0)
            time.sleep(SERVO_DELAY)

            if self.mugID == -1:
                self.last_error = "Mug failed to scan."
                self.outOfOrder()
                return
            
            #Take the last 12 characters of the RFID scanned to cut out garbage values.
            self.mugID = self.mugID[-12:]

            #Attempt to assign the mug to the user and push the changes to the database three times
            trials = 0
            cutOff = 3
            while trials < 3:
                mugAttempt = 0#db.tryMug(self.userID, self.mugID, self.machID, self.currentCapacity, cutOff)
                if mugAttempt == 0:
                    #Display user feedback
                    self.totalMugsDisp += 1
                    self.msg.set("We have saved a total of " + str(self.totalMugsDisp) + " cups!")
                    self.mug_count.set("Total Cups Saved:\n" + str(self.totalMugsDisp))

                    #Dispense the mug
                    self.bServo.ChangeDutyCycle(SERVO_UP)
                    time.sleep(PULSE_DELAY)
                    self.bServo.ChangeDutyCycle(0)
                    time.sleep(SERVO_DELAY)
                    
                    self.tServo.ChangeDutyCycle(SERVO_UP)
                    time.sleep(PULSE_DELAY)
                    self.tServo.ChangeDutyCycle(0)
                    time.sleep(SERVO_DELAY)
                    
                    self.bServo.ChangeDutyCycle(SERVO_DOWN)
                    time.sleep(PULSE_DELAY)
                    self.bServo.ChangeDutyCycle(0)
                    time.sleep(SERVO_DELAY)
                    
                    self.tServo.ChangeDutyCycle(SERVO_UP)
                    time.sleep(PULSE_DELAY)
                    self.tServo.ChangeDutyCycle(0)
                    #time.sleep(SERVO_DELAY)

                    #Check the current supply of mugs
                    self.checkCap()
                    break
                elif mugAttempt == HAS_MUG:
                    self.msg.set("User is already registered to a mug.")
                    break
                elif mugAttempt == NOT_IN_DB:
                    print "User not found in database. Please register for the program.\n"
                    self.msg.set("User not found in database. Please register for the program.")
                    break
                else:
                    cutOff = mugAttempt
                    trials += 1
                    
            self.cont_button.place(relx=0.5, y = 400, anchor = CENTER)

            #All trials have failed to push changes, so we save the changes locally and declare out of order
            if trials >= 3:
                target = open('service_log.txt', 'w')
                varString = str(self.userID) + ',' + self.mugID + ',' + self.machID + ',' + str(self.currentCapacity) + ',' + str(cutOff)
                target.write(varString)
                target.close()
                self.last_error = "SQL command failed to execute.\nPlease exit application, check internet connection,\nand restart application."
                self.outOfOrder()

    #Function
    #   Purpose - called when the continue button is pressed. Meant to re-enable the card reader, reset the msg, and default back to renting mugs
    def resetMsg(self):
        if self.out_of_order == 0:
            self.msg.set(default_msg)
        self.staff_menu = 0
        self.cont_button.place_forget()
        self.id_entry["state"] = 'normal'
        self.staff_menu_button.place(relx = 1.0, rely = 1.0, x = -20, y = -20, anchor = 'se')
        
    #Function
    #   Purpose - called when an error occurs. Meant to lock the machine so users can only attempt to access the staff menu
    def outOfOrder(self):
        self.msg.set("Sorry, we are currently empty.")
        self.out_of_order = 1
        self.id_entry["state"] = 'normal'
        self.staff_menu_button.place(relx = 1.0, rely = 1.0, x = -20, y = -20, anchor = 'se')

    #Function
    #   Purpose - called when the Staff Menu button is pressed. Meant to queue the next card read as an attempt to access the staff menu
    def staffAttempt(self):
        self.msg.set("Please swipe UBC card to access staff menu.")
        print "staff attempt"
        self.id_entry.focus_set()
        self.staff_menu = 1
        self.staff_menu_button.place_forget()
        self.staff_cancel_button.pack()
        self.staff_cancel_button.place(relx = 1.0, rely = 1.0, x = -20, y = -20, anchor = 'se')

    #Function
    #   Purpose - called when the staff cancel button is pressed. Meant to reset the next card read as a mug rental.
    def cancelStaff(self):
        self.msg.set(default_msg)
        print "staff attempt cancelled"
        self.id_entry.focus_set()
        self.staff_menu = 0
        self.staff_cancel_button.place_forget()
        self.staff_menu_button.place(relx = 1.0, rely = 1.0, x = -20, y = -20, anchor = 'se')

    #Function
    #   Purpose - Show the user staff menu options when the user is confirmed a member of staff by the database.
    #               Also displays the last known error to have occurred.
    def openStaff(self):
        print "staff confirmed"
        if self.last_error == '':
            self.msg.set("No Previous Error")
        else:
            self.msg.set(self.last_error)
        self.shut_down.pack(side="right")
        self.unlock_but.pack(side="left")
        self.lock_but.pack(side="left")
        self.exit_staff.pack(side="bottom")
        self.mug_count_display.place_forget()
        self.staff_menu_button.place_forget()
        self.cont_button.place_forget()
        self.staff_cancel_button.place_forget()
        
    #Function
    #   Purpose - unlock the side panel of the machine
    def unlock(self):
        GPIO.output(LOCK, GPIO.HIGH) #to unlock
        self.msg.set("Machine is unlocked.")
        print "unlock"
        time.sleep(1)

    #Function
    #   Purpose - lock the side panel of the machine
    def lock(self):
        GPIO.output(LOCK, GPIO.LOW) #to lock
        self.msg.set("Machine is locked.")
        print "lock"
        time.sleep(1)

    #Function
    #   Purpose - exit the staff menu and reset the out of order state.
    def exitStaff(self):
        self.shut_down.pack_forget()
        self.unlock_but.pack_forget()
        self.lock_but.pack_forget()
        self.exit_staff.pack_forget()
        self.mug_count_display.place(relx = 0, rely = 0, x = 20, y = 500, anchor = 'nw')
        self.id_entry["state"] = 'normal'
        #assuming staff only exits staff menu when machine is fixed otherwise we assume machine is turned off
        self.msg.set("Returning to normal operation.")
        self.cont_button.place(relx=0.5, y = 400, anchor = CENTER)
        self.out_of_order = 0
        self.checkCap()

    #Function
    #   Purpose - Retrieve and initialize machine data
    def grabSelfData(self):
        self.machID = mi.machID
        #try to get total mugs dispensed from this machine 3 times before going out of order
        trials = 0
        self.totalMugsDisp = -1
        while trials < 3:
            self.totalMugsDisp = int(db.getDisp(self.machID))
            if self.totalMugsDisp != -1:
                break
            trials += 1

        if trials >= 3:
            self.outOfOrder()
        self.mug_count.set("Total Cups Saved:\n" + str(self.totalMugsDisp))
        self.checkCap()

    #Function
    #   Purpose - Check the current capacity of the machine. Reports by email to staff when the machine is low or empty.
    def checkCap(self):
        self.currentCapacity = 100
        return
        if GPIO.input(IR_01) == IR_FAR:
            self.currentCapacity = 0
            #requesting refill once the machine is empty
            email.reqRefill(self.machID, 0)
            self.outOfOrder()
        elif GPIO.input(IR_02) == IR_FAR:
            self.currentCapacity = 25
            #requesting refill once the machine reaches 25% capacity
            if self.email_low == 0:
                email.reqRefill(self.machID, 25)
                self.email_low = 1
        elif GPIO.input(IR_03) == IR_FAR:
            self.email_low = 0
            self.currentCapacity = 50
        else:
            self.email_low = 0
            self.currentCapacity = 75


    #Function
    #   Purpose - Initialize and display text and buttons to be used during machine operation
    def createWidgets(self):

        self.botFrame = tk.Frame(root, bg = bgColor)
        self.botFrame.pack(side="bottom")

        bg = tk.PhotoImage(file = "/home/pi/Mugshare/mugshare_bg_template.gif")
        self.bg = tk.Label(root, image=bg)
        self.bg.photo = bg
        self.bg.pack(side = "top")
        
        font_name = 'DejaVu Serif'
        
        txtFont = tkFont.Font(family=font_name, size=30)
        txtFont_2 = tkFont.Font(family=font_name, size=24)
        buttonFont = tkFont.Font(family=font_name, size=24)

        self.msg = tk.StringVar()
        self.instructions = tk.Message(root, textvariable = self.msg, width=1024, font = txtFont, justify = CENTER, bg = bgColor, fg = textColor)
        self.msg.set(default_msg)
        #self.instructions.pack(side="top")
        self.instructions.place(relx = 0.5, y = 300, anchor = CENTER)

        self.mug_count = tk.StringVar()
        self.mug_count_display = tk.Message(root, textvariable = self.mug_count, width = 300, font = txtFont_2, justify = LEFT, bg = bgColor, fg = textColor)
        self.mug_count.set("Total Cups Saved:\n" + str(self.totalMugsDisp))
        self.mug_count_display.place(relx = 0, rely = 0, x = 20, y = 500, anchor = 'nw')

        self.idHolder = StringVar()
        self.idHolder.set('')
        self.id_entry = Entry(self.botFrame, textvariable=self.idHolder, width = 0, bd = 0, show = '*')
        #self.id_entry.pack(side="bottom")
        self.id_entry.place(relx = 1.0, rely = 1.0, x = 0, y = 0, anchor = 'se')
        self.id_entry.focus_set()
        self.id_entry.bind('<Return>', self.idInput)

        #replace with solid block of color matching bg
        hidpic = tk.PhotoImage(file = "/home/pi/Mugshare/bottom_banner.gif")
        self.hidden = tk.Label(self.botFrame, image=hidpic, borderwidth = 0, highlightthickness = 0)
        self.hidden.photo = hidpic
        self.hidden.place(relx = 1.0, rely = 1.0, x = 0, y = 0, anchor = 'se')
        self.id_entry.lower()

        self.cont_button = tk.Button(root, padx=4, pady=4, text="Continue", command=self.resetMsg, font=buttonFont, fg=btColor, bg=bColor)

        self.staff_menu_button = tk.Button(root, padx=4, pady=4)
        self.staff_menu_button["text"] = "Staff Menu"
        self.staff_menu_button["command"] = self.staffAttempt
        self.staff_menu_button["font"]=buttonFont
        self.staff_menu_button["foreground"]=btColor
        self.staff_menu_button["background"]=bColor
        self.staff_menu_button["activeforeground"]=bgColor
        self.staff_menu_button["activebackground"]=bColor
        self.staff_menu_button.pack()
        self.staff_menu_button.place(relx = 1.0, rely = 1.0, x = -20, y = -20, anchor = 'se')

        self.staff_cancel_button = tk.Button(root, padx=4, pady=4)
        self.staff_cancel_button["text"] = "Cancel"
        self.staff_cancel_button["command"] = self.cancelStaff
        self.staff_cancel_button["font"]=buttonFont
        self.staff_cancel_button["foreground"]=btColor
        self.staff_cancel_button["background"]=bColor
        self.staff_cancel_button["activeforeground"]=bgColor
        self.staff_cancel_button["activebackground"]=bColor

        
        self.shut_down = tk.Button(self.botFrame, padx=50, pady=18)
        self.shut_down["text"] = "Shutdown"
        self.shut_down["fg"] = "red"
        self.shut_down["font"] = buttonFont
        self.shut_down["background"]=bColor
        self.shut_down["command"] = self.quit

        self.lock_but = tk.Button(self.botFrame, padx=50, pady=18)
        self.lock_but["text"] = "Lock"
        self.lock_but["font"]=buttonFont
        self.lock_but["foreground"]=btColor
        self.lock_but["background"]=bColor
        self.lock_but["activeforeground"]=btColor
        self.lock_but["activebackground"]=bColor
        self.lock_but["command"] = self.lock

        self.unlock_but = tk.Button(self.botFrame, padx=50, pady=18)
        self.unlock_but["text"] = "Unlock"
        self.unlock_but["font"]=buttonFont
        self.unlock_but["foreground"]=btColor
        self.unlock_but["background"]=bColor
        self.unlock_but["activeforeground"]=btColor
        self.unlock_but["activebackground"]=bColor
        self.unlock_but["command"] = self.unlock

        self.exit_staff = tk.Button(self.botFrame, padx=50, pady=18)
        self.exit_staff["text"] = "Exit Menu"
        self.exit_staff["font"]=buttonFont
        self.exit_staff["foreground"]=btColor
        self.exit_staff["background"]=bColor
        self.exit_staff["activeforeground"]=btColor
        self.exit_staff["activebackground"]=bColor
        self.exit_staff["command"] = self.exitStaff

#Defining colors to be used in the GUI
tk_rgb = "#%02x%02x%02x" % (128, 166, 216)
bColor = 'white'
textColor = 'white'
bgColor = tk_rgb
btColor = 'royal blue'

root = tk.Tk()
root.attributes("-fullscreen", True)
app = Application(master=root)
root.configure(background=bgColor)
app.mainloop()
root.destroy()
