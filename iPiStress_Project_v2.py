
from machine import ADC, Pin, I2C
from time import sleep_ms, ticks_ms, ticks_diff
import ssd1306
import network
import urequests as requests 
import ujson
import math

sensor = ADC(26)
sw0 = Pin(9, Pin.IN, Pin.PULL_UP)

i2c = I2C(1, sda=Pin(14), scl=Pin(15))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

#class Encoder to handle rotation and button interrupts
class Encoder:   
    
    def __init__(self, outA_pin, outB_pin, switch_pin):
        self.outA = Pin(outA_pin, Pin.IN, Pin.PULL_UP) # Pin CLK of encoder
        self.outB = Pin(outB_pin, Pin.IN, Pin.PULL_UP) # Pin DT of encoder
        self.switch = Pin(switch_pin, Pin.IN, Pin.PULL_UP) # inbuilt switch on the rotary encoder, ACTIVE LOW
        self.option = 1
        self.page = 0	#0:select option, 1:HR only, 2:Offline, 3:Online
        self.outA.irq(trigger = Pin.IRQ_FALLING, handler = self.encoder_irq)
        self.switch.irq(trigger = Pin.IRQ_FALLING, handler = self.button_irq)
        #self.sw0 = sw0

    # interrupt handler function (IRQ) for CLK and DT pins
    def encoder_irq(self, pin):	#handle rotation in page 0 ONLY
        if self.page == 0:
            if self.outB.value():   
                self.option = (self.option + 1) % 3 + 1                
                Page.Menu(self.option)
            else:            
                self.option = (self.option % 3) + 1
                Page.Menu(self.option)
                
    # interrupt handler function (IRQ) for SW (switch) pin
    def button_irq(self, pin):
        global measuring
        global sw0
        global goBack
        sleep_ms(20)	# debounce time
        if not self.switch():
            if self.page == 0:
                self.page = self.option
                Page.Option(self.option)
                sw0.irq(trigger = Pin.IRQ_FALLING, handler = sw0Irq)
            else:                    
                self.page = 0
                sw0.irq(trigger = Pin.IRQ_FALLING, handler = None)
                measuring = False
                #print(measuring)
                #Page.Menu(self.option)
                goBack = True

#class Page to display current page on oled
class Page:
    def Menu(option):
        oled.fill(0)
        oled.text('Select a mode:',10,0)
        if option == 1:
            oled.fill_rect(0,14,128,10,1)
            oled.text('HR BPM only',0,15,0)
            oled.text('Offline Analysis',0,30)
            oled.text('Online Analysis',0,45)
        elif option == 2:
            oled.fill_rect(0,29,128,10,1)
            oled.text('HR BPM only',0,15)
            oled.text('Offline Analysis',0,30,0)
            oled.text('Online Analysis',0,45)
        else:
            oled.fill_rect(0,44,128,10,1)
            oled.text('HR BPM only',0,15)
            oled.text('Offline Analysis',0,30)
            oled.text('Online Analysis',0,45,0)
        oled.show()

    def Option(option):
        if option == 3:	#online mode
            #connect to wifi
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            #wlan.connect("Rhod", "0413113368")
            wlan.connect("KME551Group3", "NoP@ssword")
            while not wlan.isconnected():
                oled.fill(0)
                oled.text('Checking WiFi',0,30)
                oled.show()
                sleep_ms(500)
                oled.fill(0)
                oled.show()
                sleep_ms(300)
        
        oled.fill(0)
        oled.text('Press SW_0', 0, 5)
        oled.text('to start',0,15)
        oled.show()

#class Program to execute offline and online mode
class Program:
    
    def OfflineAnalysis():
        #print('offline mode')
        oled.fill(0)
        oled.text('Analyzing...', 0, 5)
        oled.show()
        
        tmp = 0
        meanRR = sum(intervals) // 20
        meanHR = 60000 // meanRR
        for i in intervals:
            tmp += (i - meanRR)**2
        sdnn = int(math.sqrt(tmp / 19))	#int(math.sqrt(tmp / (len(intervals) - 1)))
        tmp = 0
        for i in range(19):	# 19 = len(intervals) - 1
            tmp += (intervals[i+1] - intervals[i])**2
        rmssd = int(math.sqrt(tmp / 19))	#int(math.sqrt(tmp / (len(intervals) - 1)))
        
        oled.fill(0)
        oled.text('Pi Pico says: ',10,0)
        oled.text('mean PPI: '+str(meanRR),0, 15)
        oled.text('mean HR: '+str(meanHR)+' bpm',0, 27)
        oled.text('SDNN: '+str(sdnn),0, 39)
        oled.text('RMSSD: '+str(rmssd),0, 51)
        oled.show()
    
    def OnlineAnalysis():  
        APIKEY = "pbZRUi49X48I56oL1Lq8y8NDjq6rPfzX3AQeNo3a" 
        CLIENT_ID = "3pjgjdmamlj759te85icf0lucv" 
        CLIENT_SECRET = "111fqsli1eo7mejcrlffbklvftcnfl4keoadrdv1o45vt9pndlef" 
        TOKEN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/oauth2/token" 

        response = requests.post( 
            url = TOKEN_URL, data = 'grant_type=client_credentials&client_id={}'.format(CLIENT_ID), 
            headers = {'Content-Type':'application/x-www-form-urlencoded'}, auth = (CLIENT_ID, CLIENT_SECRET)) 
        response = response.json() #Parse JSON response into a python dictionary
        access_token = response["access_token"] #Parse access token out of the response dictionary 
                
        oled.fill(0)
        oled.text('Analyzing...', 0, 5)
        oled.show()

        data_set = {
            "type": "RRI",
            "data": intervals,
            "analysis": {
            "type": "readiness"}
            }

        # Make the readiness analysis with the given data 
        response = requests.post( url = "https://analysis.kubioscloud.com/v2/analytics/analyze", 
            headers = { "Authorization": "Bearer {}".format(access_token), 
            #use access token to access your KubiosCloud analysis session 
            "X-Api-Key": APIKEY }, 
            json = data_set) #dataset will be automatically converted to JSON by the urequests library 
        response = response.json() 
        #Print out the SNS and PNS values on the OLED screen
        #print(response)
        meanRR = int(response['analysis']['mean_rr_ms'])
        meanHR = int(response['analysis']['mean_hr_bpm'])
        sdnn = int(response['analysis']['sdnn_ms'])
        rmssd = int(response['analysis']['rmssd_ms'])
        #sns_index = response['analysis']['sns_index']
        #pns_index = response['analysis']['pns_index']
        oled.fill(0)
        oled.text('Kubios says: ',10,0)
        oled.text('mean PPI: '+str(meanRR),0, 15)
        oled.text('mean HR: '+str(meanHR)+' bpm',0, 27)
        oled.text('SDNN: '+str(sdnn),0, 39)
        oled.text('RMSSD: '+str(rmssd),0, 51)
        oled.show()
        
#sw_0 interrpt handler to start a new measurement
def sw0Irq(pin):
    global startMeasure
    sleep_ms(20)
    if not sw0():
        startMeasure = True
        #print('inside sw0Irq')

#function to draw hr pulse graphic and bpm
lastPosY = 0
def drawOled(dv, minv, maxv, bpm):
    global lastPosY
    oled.scroll(-1,0) # Scroll left 1 pixel
    if dv > maxv:
        dv = maxv
    elif dv < minv:
        dv = minv
    newPosY = 64 - 32 * (dv - minv) // valRange
    oled.line(125, lastPosY, 126, newPosY, 1)
    lastPosY = newPosY
    oled.fill_rect(0,0,128,32,0)
    oled.text('Measuring...', 10, 5)
    oled.text('%d BPM' % bpm, 10, 20)
    oled.show()
    
rot = Encoder(10,11,12)
startMeasure = False
measuring = False
goBack = True
dlist = []
while True:
    if goBack:	#check if go back from executing program to selecting mode screen
        goBack = False
        Page.Menu(rot.option)
        
    if startMeasure:	#check if sw_0 has been pressed to start new measurement
        #print('startMeasure = True***')
        startMeasure = False
        measuring = True
        beat = False	#mark if found beat or not
        beatTime = [0 , 0]	#store timestamps of 2 consecutive beats
        bpm = 0	#store calculated bpm
        minv = 65535	#init minv to prepare for calculating threshold
        maxv = 0		#init maxv to prepare for calculating threshold
        sampleCount = 0	#count samples to recalculate threshold
        sumIbi = 0	#sum of amount of ibi to calculate mean value of ibi
        beatCount = 0	#count number of beats to calculate a average ibi
        intervals = []
        intervalsCount = 0				
        
        #get correct minv maxv first
        for a in range(200):
            dv = sensor.read_u16()
            sleep_ms(4)
            dlist.append(dv)
            dlist = dlist[-5:]
            #find max and min value to display beat line on oled
            if dv > maxv:
                maxv = dv
            if dv < minv:
                minv = dv
        #calculate threshold
        thres_H = (minv + maxv * 3) // 4   # 3/4
        thres_L = (minv + maxv) // 2      # 1/2
        valRange = maxv - minv
        
    if measuring:	#check if program is executing a measurement
        #print('measuring = ', measuring)
        if intervalsCount < 20:
            dlist.append(sensor.read_u16())
            sleep_ms(4)                
            dlist = dlist[-5:]
            dv = sum(dlist) // 5
            sampleCount += 1	#count number of dv
            #find max and min value to display beat line on oled
            if dv > maxv:
                maxv = dv
            if dv < minv:
                minv = dv
            #detect a beat: a beat is found when a very first dv > threshold
            #print('line 229')
            if dv > thres_H and not beat:
                beat = True
                dt = ticks_ms()	#get a timestamp when a beat is found
                beatTime.append(dt)	#add new timestamp to a queue
                beatTime = beatTime[-2:]	#limit the timestamp list to 2 items
                #calculate inter-beat-interval ibi: calculate a timespan between 2 consecutive beats
                ibi = ticks_diff(beatTime[-1], beatTime[-2])
                #print(ibi)
                #calculate mean ibi then calculate bpm
                if 250 < ibi < 1500:	#limit range of bpm from 40-240 bpm
                    sumIbi += ibi
                    beatCount += 1
                    #calculate mean ibi after beatCount
                    if beatCount == 1:	//modify this value to get better result
                        beatCount = 0
                        avrIbi = sumIbi // 1	//modify this value to get better result
                        bpm = 60000 // avrIbi
                        intervals.append(avrIbi)
                        intervalsCount += 1
                        sumIbi = 0
            #print('line 250')
            if dv < thres_L and beat:	#ignor all dv < threshold
                beat = False
            #update data and draw beat line to oled after every calculated mean dv
            drawOled(dv, minv, maxv, bpm)
            #recalculate threshold after sampleCount
            #print('line 256')
            if sampleCount > 200:
                sampleCount = 0                 
                thres_H = (minv + maxv * 3) // 4   # 3/4
                thres_L = (minv + maxv) // 2      # 1/2
                valRange = maxv - minv
                minv = 65535
                maxv = 0
                #print(thres_L, thres_H)
            #sleep_ms(2)
            if rot.option == 1:
                intervalsCount = 0	#reset intervalsCount to get infinite measurement in option 1
            
        else:	#if intervalsCount = 20 then starts to go with offline or online mode
            #print(intervals)
            measuring = False
            if rot.option == 2:	#offline mode
                Program.OfflineAnalysis()
            if rot.option == 3:	#online mode
                Program.OnlineAnalysis()
            
        

