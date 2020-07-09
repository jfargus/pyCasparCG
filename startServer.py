from amcp_pylib.core import Client
from amcp_pylib.module.query import VERSION, BYE
import pandas as pd
import datetime
import time
import xmltodict
import pprint

#function to revert back to the info 'TV Guide' channel when no programming is scheduled
def startInfoChannel():
    
    #set music sites
    radioSiteMorning = "http://jzr-sunset.ice.infomaniak.ch/jzr-sunset.mp3?listening-from-radio-garden=1593559278551"
    radioSiteOvernight="https://radio.stereoscenic.com/asp-s?listening-from-radio-garden=1594126513986"
    #only two right now, I'll add another one eventually
    radioSiteDay = radioSiteMorning
    
    currentHourInfoChannelDefault = datetime.datetime.today().hour
    
    #clear channels
    response = client.send(bytes("STOP 1-09 \r\n",encoding='utf8'))
    response = client.send(bytes("STOP 1-10 \r\n",encoding='utf8'))
    
    #change music playing based on time of day
    if currentHourInfoChannelDefault < 9 or currentHourInfoChannelDefault > 21:
        response = client.send(bytes("PLAY 1-09 [HTML] "+ radioSiteOvernight + " \r\n",encoding='utf8'))
    elif currentHourInfoChannelDefault < 13:
        response = client.send(bytes("PLAY 1-09 [HTML] "+ radioSiteMorning + " \r\n",encoding='utf8'))
    else:
        response = client.send(bytes("PLAY 1-09 [HTML] "+ radioSiteDay + " \r\n",encoding='utf8'))
    
    #play default channel
    response = client.send(bytes("PLAY 1-10 [HTML] "+ defaultPage + " \r\n",encoding='utf8'))

#function to update the up next flash graphic that plays, super crappy design but best I can do rn
def updateUpNext(pathOriginal,pathInPlace, title,time):
    #update the title lower third with a next up card
    f = open(pathOriginal,'r') # open file with read permissions
    filedata = f.read() # read contents
    f.close() # closes file
    f = open(pathInPlace,'w') # open the same (or another) file with write permissions
    f.write(filedata) # update it replacing the previous strings 
    f.close() # closes the file
    f = open(pathInPlace,'r') # open file with read permissions
    filedata = f.read() # read contents
    f.close() # closes file
    filedata = filedata.replace('MyTitle', title) # replace 1111 with 1234
    filedata = filedata.replace('TIME', time) # you can add as many replace rules as u need
    f = open(pathInPlace,'w') # open the same (or another) file with write permissions
    f.write(filedata) # update it replacing the previous strings 
    f.close() # closes the file

#get seconds from time
def get_sec(time_str):
    #Gets seconds from time
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)

def ceil_dt(dt, delta):
    #Rounds current time up by minute value - delta
    return dt + (datetime.datetime.min - dt) % delta

#set client IP below and HTML page for info channel
clientIP = "192.168.1.101"
defaultPage = "http://192.168.3.9:8099"

#connect to casparcg client
client = Client()
client.connect(clientIP, 5250)
radioSite = "https://www.jango.com/stations/113387000/tunein?"

#start infochannel
startInfoChannel()

#start infinite loop of checking for new programming and updating the TV server
while True:
    currentWeekday = datetime.datetime.today().weekday()
    print(currentWeekday)
    currentHour = datetime.datetime.today().hour
    currentMinute = datetime.datetime.today().minute
    currentDate = pd.Timestamp('today').normalize()
    now = datetime.datetime.now()
    nextSlotTime = ceil_dt(now, datetime.timedelta(minutes=15))
    nextMinuteSlot = nextSlotTime.minute
    nextHourSlot = nextSlotTime.hour
    nextWeekdaySlot = nextSlotTime.weekday()
    followingSlotTime = nextSlotTime + datetime.timedelta(minutes=10)
    print("Runtime: ",now)
    print("Up next slot time: ",nextSlotTime)
    print("Next refresh at: ",followingSlotTime)

    #read schedule document
    schedule = pd.read_csv('schedule.csv')
    adList = pd.read_csv('adList.csv')

    #convert date column to pandas friendly datetime
    schedule['start'] = pd.to_datetime(schedule['start'])
    print("Full Schedule:")
    print(schedule)

    #filter schedule document where items match upcoming slot
    nextItem = schedule.loc[schedule['hour'] == nextHourSlot]
    nextItem = nextItem.loc[schedule['minute'] == nextMinuteSlot]
    nextItem = nextItem.loc[schedule['weekday'] == nextWeekdaySlot]

    #examine how many items were found, set to var
    itemQueue = nextItem.shape[0]
    print("Items in queue")
    print(itemQueue)

    #if more than one item matches, examine recurrances
    if itemQueue > 1:
        print("More than one item in queue, parsing recurrances...")
        nextItem = nextItem.loc[nextItem['start']<=currentDate]
        itemQueue = nextItem.shape[0]
        print(itemQueue)

    if itemQueue == 0:
        startInfoChannel()
        refreshInterval = ((followingSlotTime - datetime.datetime.now())).total_seconds()
        print("Waiting ",refreshInterval, " seconds to refresh queue...")
        time.sleep(refreshInterval)
    else: 
        #regardless, choose first item in list as next up
        nextItem = nextItem.head(n=1)
        print("Next Up:")
        print(nextItem)
        #Get video name and length
        videoName = nextItem.iloc[0,0]
        videoLength = get_sec(nextItem.iloc[0,4])
        
        time.sleep(2)
        #create next up card and display for 14 seconds
        if nextHourSlot>12: 
            AMPM= "PM" 
            hourUp = str(nextHourSlot-12)
        else: 
            AMPM ="AM"
            hourUp = str(nextHourSlot)
        friendlySlotTime = hourUp+":"+str(nextMinuteSlot)+" "+AMPM
        print(friendlySlotTime)
        updateUpNext('U://upnext.html','Q://upnext.html',videoName ,friendlySlotTime)    
        response = client.send(bytes("CG 1-20 ADD 0 upnext 1 \r\n",encoding='utf8'))
        print("Updating next up title card")
        print(response)
        print("Waiting for title card to finish")
        time.sleep(14)
        response = client.send(bytes("CG 1-20 REMOVE 0 upnext 1 \r\n",encoding='utf8'))
        print(response)

        #define time to wait until next clip
        waitTime = (nextSlotTime - datetime.datetime.now()).total_seconds()

        #Wait until slot time
        print("Waiting for next show start",waitTime)
        time.sleep(waitTime)

        #Stop default info channel on layer
        print("Stopping default channel")
        response = client.send(bytes("STOP 1-09 \r\n",encoding='utf8'))
        response = client.send(bytes("STOP 1-10 \r\n",encoding='utf8'))
        print(response)

        #Start video
        print("Playing clip")
        response = client.send(bytes('PLAY 1-10 \"'+videoName+ '\" PUSH 20 EASEINSINE '+'\r\n',encoding='utf8'))
        print(response)

        #Wait length of video until the clip is finished
        print("Waiting for video end:",videoLength)
        time.sleep(videoLength)

        #Stop video
        print("Stopping video")
        response = client.send(bytes('STOP 1-10 \"'+videoName+'\"\r\n',encoding='utf8'))
        print(response)

        #Resume info channel
        print("Starting default channel")
        startInfoChannel()
        print(response)
