import os
import string
import pymssql
import time
import info.loginINFO as loginINFO
from datetime import datetime

#Response Constants
HAS_MUG = 1
NOT_IN_DB = 2
FAILED_ASSIGNMENT = 3
FAILED_USER_UPDATE = 4
FAILED_MUG_UPDATE = 5
FAILED_MACHINE_UPDATE = 6
FAILED_HOUR_STAT = 7
FAILED_MONTH_STAT = 8
FAILED_YEAR_STAT = 9
FAILED_STAFF = 10

#Function
#   Purpose - ask Database if a user has already rented a mug
#   Input   - the userID read from the card reader
#   Output  - the state of the user, has a mug, does not have a mug, or not registered
#   Error   - Returns the integer 3 when the SQL command failed to transmit.
def checkUser(userID):
    try:
        connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
        cursor = connection.cursor()
        cmd = "SELECT MugInUse FROM MugShareUsers WHERE StudentNumber = %d"
        cursor.execute(cmd, userID)
        response = cursor.fetchone()
        print str(response)
        connection.close()
    except:
        response = FAILED_ASSIGNMENT
        print "Assign"
        return response
    
    if response == None:
        return NOT_IN_DB
    if response == (True,):
        return HAS_MUG
    return 0

#Funtion
#   Purpose - check the userID a 2nd time and then update the datatables in the database to assign the mug to the user
#   Input   - userID from card reader
#           - mugID from RFID reeader
#           - machine ID assigned to the machine
#           - currentlySupply of the machine
#           - cutOff is which SQL command the prev assignment failed and should continue from
#
#   Output  - new cutOff if a SQL command fails
#           - integer 0 if assignment was a success
#           - state of the user if it has changed
def tryMug(userID, mugID, machID, currentSupply, cutOff):
    response = 0
    if cutOff == FAILED_ASSIGNMENT:
        try:
            connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
            cursor = connection.cursor()
            cmd = "SELECT MugInUse FROM MugShareUsers WHERE StudentNumber = %d"
            cursor.execute(cmd, userID)
            response = cursor.fetchone()
            print str(response)
            connection.close()
        except:
            response = FAILED_ASSIGNMENT
            print "Assign"
            return response

        if response == None:
            return NOT_IN_DB
        if response == (True,):
            return HAS_MUG

        cutOff = FAILED_USER_UPDATE
    
    if cutOff == FAILED_USER_UPDATE:
        try:
            connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
            cursor = connection.cursor()
            date = str(datetime.today())
            date = date[0:date.find(" ")+1]
            print date
            cmd = "UPDATE MugShareUsers SET MugInUse = 'true', DateOfRental = %s, TotalMugsBorrowed = TotalMugsBorrowed + 1 WHERE StudentNumber = %d"
            cursor.execute(cmd, (date, userID))
            connection.commit()    #Only need this line if changing data
            connection.close()
        except:
            response = FAILED_USER_UPDATE
            print "user"
            return response

        cutOff = FAILED_MUG_UPDATE
    print '1'
    if cutOff == FAILED_MUG_UPDATE:
        print str(mugID)
        print str(userID)
        try:
            connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
            cursor = connection.cursor()
            cmd = "UPDATE MugRegistry SET LastBorrowedBy = %d, CurrentlyInUse = 'true' WHERE MugID = %s"
            cursor.execute(cmd, (userID, mugID))
            connection.commit()    #Only need this line if changing data
            connection.close()
        except:
            response = FAILED_MUG_UPDATE
            print "mug"
            return response

        cutOff = FAILED_MACHINE_UPDATE

    if cutOff == FAILED_MACHINE_UPDATE:
        try:
            connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
            cursor = connection.cursor()
            cmd = "UPDATE LocationSupply SET CurrentSupply = %d WHERE MachineID = %s"
            cursor.execute(cmd, (currentSupply, machID))
            connection.commit()    #Only need this line if changing data
            connection.close()
        except:
            response = FAILED_MACHINE_UPDATE
            print "machine"
            return response
        
	cutOff = FAILED_HOUR_STAT

    if cutOff == FAILED_HOUR_STAT:
        try:
            connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
            cursor = connection.cursor()
            cmd = "UPDATE HourlyStatistics SET [" + time.strftime('%H') + "] = [" + time.strftime('%H') + "] + 1 WHERE MachineID = %s"
            print cmd
            cursor.execute(cmd, machID)
            connection.commit()    #Only need this line if changing data
            connection.close()
        except:
            response = FAILED_HOUR_STAT
            print "hour"
            return response

        cutOff = FAILED_MONTH_STAT
        
    if cutOff == FAILED_MONTH_STAT:
        try:
            connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
            cursor = connection.cursor()
            cmd = "UPDATE MonthlyStatistics SET " + time.strftime('%B') + " = " + time.strftime('%B') + " + 1"
            cursor.execute(cmd)
            connection.commit()    #Only need this line if changing data
            connection.close()
        except:
            response = FAILED_MONTH_STAT
            print "month"
            return response

        cutOff = FAILED_YEAR_STAT
            
    if cutOff == FAILED_YEAR_STAT:
        try:
            connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
            cursor = connection.cursor()
	    cmd = "IF EXISTS (SELECT * FROM YearlyStatistics WHERE Year = %d) UPDATE YearlyStatistics Set TotalMugsBorrowed = TotalMugsBorrowed + 1 WHERE Year = %d ELSE INSERT INTO YearlyStatistics (Year, TotalMugsBorrowed) VALUES (%d, 1)"
            print cmd
            print time.strftime('%Y')
            cursor.execute(cmd, (int(time.strftime('%Y')), int(time.strftime('%Y')), int(time.strftime('%Y'))))
            connection.commit()    #Only need this line if changing data
            connection.close()
        except:
            response = FAILED_YEAR_STAT
            print "year"
            return response

    return 0

#Function
#   Purpose - check if the given ID has been assigned staff access by the Database
#   Output  - boolean True is the given ID is assigned to a staff member, False if not, and integer 10 if the SQL command failed
#   Input   - staffId read from the card reader
def tryStaff(staffID):
    try:
        connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
        cursor = connection.cursor()
        cmd = "SELECT * FROM Security WHERE StaffCardID = %d"
        cursor.execute(cmd, (staffID))
        response = cursor.fetchone()
        connection.close()
    except:
        response = FAILED_STAFF
        return response

    if response == None:
        return False
    else:
        return True

#Function
#   Purpose - get the total number of mugs dispensed from a machine with the given ID
#   Output  - number of mugs dispensed from the machine
#   Input   - machine ID
def getDisp(machID):
    try:
        connection = pymssql.connect(server=loginINFO.server, user=loginINFO.user, password=loginINFO.password, database=loginINFO.database)
        cursor = connection.cursor()
        cmd = "SELECT TotalMugsDispensed FROM LocationSupply WHERE MachineID = %d"
        cursor.execute(cmd, (machID))
        response = cursor.fetchone()
        connection.close()
    except:
        response = -1
        return response
    response = str(response)
    start = response.find('(') + 1
    end = response.find(',')
    response = response[start:end]
    return response
