#!/usr/bin/env python3
import bluetooth
import os
import time
import MySQLdb #for database
import hashlib #for the md5 hash
import requests #for push bullet
from datetime import datetime, timedelta
from sense_hat import SenseHat
import select
import sys
import time


class Bluetooth:
    urid = None
    mac = None
    deviceName = None
    deviceMac = None
    def __init__(self): #reading constructor
        # self.urid = urid
        self.ubid = hashlib.md5(str(datetime.utcnow()).encode('utf8')).hexdigest() #uses the current datetime and hashes it for a UBID (Unique Bluetooth Identifiation)    

    def run(self):
        #self.deviceName = input('Enter the name of your phone: ')
        print("NOTE: If no device name is entered in 20 seconds, notifications will be sent automatically to nearby devices already in the database.")
        print("Enter the name of your bluetooth device: ")
        a, b, c = select.select( [sys.stdin], [], [], 20 ) #is similar so input method. However is used to delay for 20 seconds. If no user input detected begin automation -> automateAndNotify()
        if (a):
            self.searchDb(sys.stdin.readline().strip())
        else:
            self.automateAndNotify()

    def searchDb(self, deviceName):
        self.deviceName = deviceName
        currentDeviceName = None
        currentDeviceMac = None
        
        print("Looking up device name: {} in database...".format(self.deviceName))
        connection = MySQLdb.connect(host="localhost", user="iot", passwd="Password123?", database="iot")
        cursor = connection.cursor()
        sql = "SELECT devicename, devicemac, updated_at FROM bluetooth WHERE devicename = %s"
        adr = (deviceName, )
        cursor.execute(sql, adr)
        rows = cursor.fetchall()

        for row in rows:
            currentDeviceName = row[0]  # loops through and gets name
            currentDeviceMac = row[1]  # loops through and gets mac addres
            lastUpdate = row[2]  # loops through and gets timestamp
        if currentDeviceName is not None and currentDeviceMac is not None:
            print("Device named {} with the MAC address of: {}, is already in the database".format(currentDeviceName, currentDeviceMac))
            if lastUpdate > datetime.utcnow() - timedelta(seconds = 3600): #if device has sent a notification in the last hour
                print("Device: {} has already sent a message".format(currentDeviceName))
            else:
                self.lookUpAndNotfy()
        if currentDeviceName is None or currentDeviceMac is None:
            self.search(self.deviceName)

    def search(self, deviceName):
        print("Searching...")
        while True:
            foundDevice = False
            time.sleep(3) #Sleep three seconds 
            nearby_devices = bluetooth.discover_devices() #gets list f near by devices

            for mac_address in nearby_devices:
                if self.deviceName == bluetooth.lookup_name(mac_address, timeout=5): #keep trying to get the requested name, if nto set a timeout of 5 seconds
                    foundDevice = True
                    self.deviceMac = mac_address
                    break #stop loop

            if foundDevice != False:
                print("Your device ({}) with the MAC address: {}, has been found".format(self.deviceName, self.deviceMac)) #visual confirmation
                self.bluetoothSelection() #ask user if they want to save device to DB
                break

            else:
                print("Could not find your device, retrying...")

    def bluetoothSelection(self): #gets user input for adding device to the database. 
        addToDbChoice = input("No Record Found in Database, \n Would you like to save this device into the database Y or N?: ")
        self.choiceAction(addToDbChoice)


    def choiceAction(self, addToDbChoice):
        choice = addToDbChoice.strip().upper() #strip all whitespace chars and put input to uppercase
        if choice == 'Y':
            #add to to
            print("Add to database")
            self.addDeviceToDb()
            self.notifySelectection()
        elif choice == 'N':
            #ignore, just send message with current device
            print("DONT add to database")
        else:
            print("\nIncorrect input, either choose Y for yes or N for no...")
            self.bluetoothSelection() #ask user if they want to save device to DB


    def notifySelectection(self): #gets user input for notifications
        notifyChoice = input("Do you want to send a notification now Y or N?: ")
        self.notifyActions(notifyChoice)

    def notifyActions(self, notifyChoice):
        choice = notifyChoice.strip().upper() #strip all whitespace chars and put input to uppercase
        if choice == 'Y':
            #add to to
            self.updateUpdatedAt(self.ubid)
            self.lookUpAndNotfy()
        elif choice == 'N':
            #ignore, just send message with current device
            print("Exiting...")
        else:
            print("Incorrect input, either choose Y for yes or N for no...")
            self.notifySelectection() #ask user if they want to save device to DB

    def addDeviceToDb(self): #Simply adds the device details to the database
        db = MySQLdb.connect(host="localhost", user="iot", passwd="Password123?", db="iot")
        cursor = db.cursor()
        sql = "INSERT INTO bluetooth (ubid, devicemac, devicename, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)"
        val = (self.ubid, self.deviceMac, self.deviceName, datetime.utcnow(), datetime.utcnow())
        cursor.execute(sql, val)
        db.commit() #saves row in database based of object 

    def lookUpAndNotfy(self): #looks up device in database, does checks and will send a PushBullet notification if the checks have been passed
        temp = None
        humidity = None
        status = None
        tempStatusMSG = None
        humidityStatusMSG = None
        print("Sending....")
        connection = MySQLdb.connect(host="localhost", user="iot", passwd="Password123?", database="iot")
        # prepare a cursor object using cursor() method
        cursor = connection.cursor()
        # execute the SQL query using execute() method.
        cursor.execute("SELECT temp, humidity, status, tempStatusMSG, humidityStatusMSG FROM readings ORDER BY urid DESC LIMIT 1")
        # fetch all of the rows from the query
        rows = cursor.fetchall()
        for row in rows:
            temp = row[0] #temp
            humidity = row[1] #humidity
            tatus = row[2] #status
            tempStatusMSG = row[3] #tempMSG
            humidityStatusMSG = row[4] #humidityMSG

        headers = {'Access-Token': 'o.XE04vcyyRIYKWaqDhno27lsmcE0uxGXk', 'Content-Type': 'application/json'}
        payload = {'body':'Temprature: {},\n Humidity: {},\n Status: {},\n {},\n {}'.format(temp, humidity, status, tempStatusMSG, humidityStatusMSG),'title':'Bluetooth Notification for device: {}'.format(self.deviceName),'type':'note','channel_tag':'iot-s3656070'}
        response = requests.post("https://api.pushbullet.com/v2/pushes", json=payload, headers=headers)
        print("{}".format(response))
        if response.status_code == 200:
            print('Sent notification!')
            self.updateUpdatedAt(self.ubid)
        else:
            raise Exception("ERROR: Could not send notification! Response Received: {}, check here for more information: https://docs.pushbullet.com/#http-status-codes".format(response))

    def automateAndNotify(self): #automates the jobs of looking up devices in the database, matches records against devices nearby, then sends a notification if checks have been passed
        temp = None
        humidity = None
        status = None
        tempStatusMSG = None
        humidityStatusMSG = None
        deviceName = None
        lastUpdate = None
        deviceMac = None
        updated_at = None
        print("NOTE: If a device has recently been added, please wait 1 hour...")
        connection = MySQLdb.connect(host="localhost", user="iot", passwd="Password123?", database="iot")
        # prepare a cursor object using cursor() method
        cursor = connection.cursor()

        cursor.execute("SELECT ubid, devicename, devicemac, updated_at FROM bluetooth") #performs device look up
        deviceRows = cursor.fetchall()
        cursor.execute("SELECT temp, humidity, status, tempStatusMSG, humidityStatusMSG FROM readings ORDER BY urid DESC LIMIT 1") #performs readings look up
        rows = cursor.fetchall()
        addresses = [] #init a list of addresses.
        nearby_devices = bluetooth.discover_devices() #gets a list of nearby bluetooth mac addresses.
        for mac_address in nearby_devices:
            addresses.append(mac_address) #adds mac addresses to array
        # execute the SQL query using execute() method.
        # fetch all of the rows from the query
        for row in rows:
            temp = row[0] #temp
            humidity = row[1] #humidity
            status = row[2] #status
            tempStatusMSG = row[3] #tempMSG
            humidityStatusMSG = row[4] #humidityMSG
               
        for deviceRow in deviceRows:
            ubid = deviceRow[0]
            deviceName = deviceRow[1]
            deviceMac =  deviceRow[2]
            updated_at = deviceRow[3]
            time.sleep(2) #delay 2 seconds so we dont spam PushBullet's API
            if updated_at > datetime.utcnow() - timedelta(seconds = 3600): #if device has sent a notification in the last hour
                print("Device: {} has already sent a message less then 1 hour ago.".format(deviceName))
            else:
                for currentMacAddress in addresses: #for all nearby bluetooth mac addresses
                    if currentMacAddress == deviceMac: #if a near by device matches a mac address in the database
                        print("Sending notification for device: {}".format(deviceName))
                        headers = {'Access-Token': 'o.XE04vcyyRIYKWaqDhno27lsmcE0uxGXk', 'Content-Type': 'application/json'}
                        payload = {'body':'Temprature: {},\n Humidity: {},\n Status: {},\n {},\n {}'.format(temp, humidity, status, tempStatusMSG, humidityStatusMSG),'title':'Bluetooth Notification for device: {}'.format(deviceName),'type':'note','channel_tag':'iot-s3656070'}
                        response = requests.post("https://api.pushbullet.com/v2/pushes", json=payload, headers=headers)
                        print("{}".format(response))
                        if response.status_code == 200:
                            print('Sent notification!')
                            self.updateUpdatedAt(ubid) #update time if the notification has been successfully sent
                        else:
                            raise Exception("ERROR: Could not send notification! Response Received: {}, check here for more information: https://docs.pushbullet.com/#http-status-codes".format(response))

    def updateUpdatedAt(self, ubid):#updates the current bluetooth device in the database, and updates the time to now, so we can make sure only once device gets a maximum of 1 message per hour
        db = MySQLdb.connect(host="localhost", user="iot", passwd="Password123?", db="iot")
        update = db.cursor()
        sql = "UPDATE bluetooth SET updated_at = %s WHERE ubid = %s"
        val = (datetime.utcnow(), ubid)
        update.execute(sql, val)
        db.commit()


bt = Bluetooth() #create new object.
bt.run() #run program.
