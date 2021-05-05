
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import random
import time
#import destination_generator as dest_gen
def time_shift_by_min(four_digit_time,time_shift_in_min):
    hour = four_digit_time // 100
    minute = four_digit_time % 100
    newmin = minute+time_shift_in_min
    hour_increase = newmin//60
    newmin = newmin%60
    newhour = hour+hour_increase
    newhour = newhour%24
    return 100*newhour + newmin
class ASInstance:
    def __init__(self,enterpriseID,servername,windowlocationx=1800,windowlocationy=0):
        self.enterpriseID = int(enterpriseID)
        self.serverURL = "https://"+str(servername)+".airlinesim.aero"
        self.driver = webdriver.Edge()
        self.driver.implicitly_wait(1)
        #Change window size to avoid "not in window" issue:
        #Note: not working since edge is too "intelligent"
        self.driver.set_window_size(1920, 2160)
        #Move to a place that does not completely block stuff
        self.driver.set_window_position(windowlocationx,windowlocationy)
        login(self.driver,self.serverURL)
        selectenterprise(self.driver,self.enterpriseID,self.serverURL)
        try:
            self.tokenaircraftURL = gettokenaircraftURL(self.driver,self.serverURL)
        except TimeoutException:
            #probably no aircraft available. still functional in many sense
            self.tokenaircraftURL = self.serverURL
            print("Caution: No aircraft in default fleet.\n")
    def readFP(self,aircraftID):
        driver = self.driver
        wait = WebDriverWait(driver,10)
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(aircraftID)+"/0"
        driver.get(aircraftURL)
        FP = FlightPlan([[],[],[],[],[],[],[]])
        for weekday in range(7):#note weekday here is 0 based, but 1 based in Xpath
            flightsinday = driver.find_elements_by_xpath("(//div[@class='day'])["+str(weekday+1)+"]/div/div[starts-with(@class,'block flight started')]/div/span")
            flighttimes = driver.find_elements_by_xpath("(//div[@class='day'])["+str(weekday+1)+"]/div/div[starts-with(@class,'block flight started')]/div/div[@class='times']/span[@class='start']")
            for index in range(len(flightsinday)):
                FP.addflight(int(''.join([i for i in flightsinday[index].text if i.isdigit()])),[weekday])
        #Further steps that increase robustness with via flights: 
        for weekday in range(7):
            #Check if first flight in a day appeared in previous day (then it is second lag of a via flight): 
            previousday = weekday - 1
            if previousday == -1:
                previousday = 6
            if len(FP.flightsbyday[previousday])>0 and len(FP.flightsbyday[weekday])>0 and FP.flightsbyday[previousday][-1] == FP.flightsbyday[weekday][0]:
                FP.flightsbyday[weekday].pop()
            #Remove repeated flight numbers in a day (this can only happen as the second lag of a via flight):
            FP.flightsbyday[weekday] = list(set(FP.flightsbyday[weekday]))
        
        print(FP)
        return FP
                
    def createflight(self,flight):
        assert isinstance(flight,Flight)
        driver=self.driver
        wait = WebDriverWait(driver,10)
        scheduleURL = self.serverURL+"/app/com/scheduling/"+str(flight.dep)+str(flight.arr)
        driver.get(scheduleURL)
        flightnumberbox = wait.until(EC.element_to_be_clickable((By.XPATH,"//input[@name='number:number_body:input']")))
        flightnumberbox.send_keys(str(flight.flightnumber))
        try: 
            driver.find_element_by_xpath("//span[@class='fa fa-plus']").click()
        except EC.NoSuchElementException:
            flightnumberbox.send_keys(Keys.ENTER)
            wait.until(EC.presence_of_element_located((By.XPATH,"//span[@class='fa fa-plus']"))).click()
        wait.until(EC.presence_of_element_located((By.XPATH,"//h3[contains(.,'"+str(flight.flightnumber)+"')]")))
        #set departure time:
        hour = int(flight.time/100)
        hourstr=str(hour)
        if hour<10:
            hourstr="0"+hourstr
        minute = flight.time - 100*hour
        minutestr=str(minute)
        if minute<10:
            minutestr = "0"+minutestr
        print("Departure time: "+hourstr+":"+minutestr)
        hourbox = driver.find_element_by_xpath("//select[contains(@name,'newDeparture:hours')]")
        hourbox.send_keys(hourstr)
        hourbox.send_keys(Keys.TAB)
        minutebox = driver.find_element_by_xpath("//select[contains(@name,'newDeparture:minutes')]")
        minutebox.send_keys(minutestr)
        minutebox.send_keys(Keys.TAB)
        driver.find_element_by_xpath("//input[@value='Apply schedule settings']").send_keys(Keys.ENTER)
        #make sure time set is applied: 
        speedbox = wait.until(EC.element_to_be_clickable((By.XPATH,"//input[contains(@name,'speed-overrides:0')]")))
        speedboxid = speedbox.get_attribute("id")
        wait.until_not(EC.presence_of_element_located((By.ID,speedboxid)))
        #set speed override:
        if flight.spd !=None:
            self.setspeed(flight.flightnumber,flight.spd)

    
    def openstations(self,stationIATAs):
        driver = self.driver
        wait = WebDriverWait(driver,5)
        for stationIATA in stationIATAs:
            print(stationIATA)
            while True:
                try: 
                    driver.get(self.serverURL+"/app/info/search?query="+stationIATA)
                    wait.until(EC.presence_of_element_located((By.XPATH,"//input[@value='Search' and @type='submit']")))
                    #select first airport result: 
                    driver.find_element_by_xpath("//a[contains(@href,'airports')]").click()
                    break
                except TimeoutException:
                    #tryagain: 
                    continue
            while True:
                try: 
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME,"img-responsive")))
                    driver.find_element_by_class_name("btn btn-success").click()
                    wait.until_not(EC.presence_of_element_located((By.CLASS_NAME,"fa fa-plus")))
                    break
                except EC.NoSuchElementException: 
                    print("Probably station already opened.\n")
                    break
                except TimeoutException:
                    continue
            
            

            

    def assignflight(self,flight,aircraftID,daystoassign=range(7)):
        try:
            assert isinstance(flight,Flight)
            assignflighttoaircraft_low_level(self.driver,self.serverURL,flight.flightnumber,aircraftID,daystoassign)
        except AssertionError:
            assignflighttoaircraft_low_level(self.driver,self.serverURL,int(flight),aircraftID,daystoassign)
    def assignflightplan(self,flightplan,aircraftID):
        assert isinstance(flightplan,FlightPlan)
        flightnumbers = sum(flightplan.flightsbyday,[])
        flightnumbers = list(set(flightnumbers))
        for flightnumber in flightnumbers:
            weekdays = [i for i in range(7) if flightnumber in flightplan.flightsbyday[i]]
            print("flightnumber: "+str(flightnumber))
            print("assign to: ")
            print(weekdays)
            assignflighttoaircraft_low_level(self.driver,self.serverURL,flightnumber,aircraftID,weekdays)
    def getallstation(self):
        #get all station IATA code: 
        self.driver.get(self.serverURL+"/app/ops/stations")
        stationlinks = [i.get_attribute("href") for i in self.driver.find_elements_by_xpath("//a[@title='View Station']")]
        stationIATAs = [i[-3:] for i in stationlinks]
        return stationIATAs
    def batchsetallroute(self,departureIATA,Yratio=1.5,Cratio=1.65,Fratio=1.0, Cargoratio = 0.5, departureTerminal = 'T1'):
        wait = WebDriverWait(self.driver,10)
        stationIATAs = self.getallstation()
        self.batchsetroute(departureIATA,stationIATAs,Yratio,Cratio,Fratio,Cargoratio,departureTerminal)
    def batchsetroute(self,departureIATA,arrivalIATAs,Yratio=1.0,Cratio=1.0,Fratio=1.0, Cargoratio = 0.5, departureTerminal = 'T1'):
        wait = WebDriverWait(self.driver,10)
        #switch to a assignment page
        for arrivalIATA in arrivalIATAs:
            if arrivalIATA == departureIATA:
                continue
            self.driver.get(self.serverURL+"/app/com/inventory/"+departureIATA+arrivalIATA)
            #get distance:
            wait.until(EC.presence_of_element_located((By.TAG_NAME,"small")))
            distancetext = self.driver.find_element_by_tag_name("small").text
            #trick that convert string to int:
            distance = int(''.join([i for i in distancetext if i.isdigit()]))
            #set On board service: 
            servicebox = wait.until(EC.element_to_be_clickable((By.XPATH,"//select[contains(@name,'serviceProfile-group')]")))
            servicebox.click()
            if distance >= 7000:
                try:
                    #Very long haul
                    self.driver.find_element_by_xpath("//option[contains(text(),'Long PY')]").click()
                except EC.NoSuchElementException:
                    continue#Then probably this company does not have setup for ultra long haul
            elif (distance >= 1500):
                #long haul:
                self.driver.find_element_by_xpath("//option[contains(text(),'min 1500km')]").click()
            elif (distance >= 800):
                    #medium haul: 
                    self.driver.find_element_by_xpath("//option[contains(text(),'min 800km')]").click()
            else:
                #short haul: 
                self.driver.find_element_by_xpath("//select[contains(@name,'serviceProfile-group')]/option[2]").click()
            #set to avoid bulk by default: 
            #Commented out since not currently using any dynamic turnaround server.
            #cargobox = wait.until(EC.element_to_be_clickable((By.XPATH,"//select[contains(@name,'cargoPreference-group')]")))
            #cargobox.click()
            #self.driver.find_element_by_xpath("//option[@value='NO_BULK']").click()
            #select departure terminal:
            departureTbox = wait.until(EC.element_to_be_clickable((By.XPATH,"//select[contains(@name,'originTerminal-group:originTerminal-group_body:originTerminal')]")))
            departureTbox.click()
            self.driver.find_element_by_xpath("//select[@name='originTerminal-group:originTerminal-group_body:originTerminal']/option[starts-with(text(),"+departureTerminal+")]").click()
            if departureTerminal == 'T2':
                departureTbox.send_keys(Keys.ARROW_DOWN)
            if departureTerminal == 'T3':
                departureTbox.send_keys(Keys.ARROW_DOWN)
                departureTbox.send_keys(Keys.ARROW_DOWN)
            if departureTerminal == 'T4':
                departureTbox.send_keys(Keys.ARROW_DOWN)
                departureTbox.send_keys(Keys.ARROW_DOWN)
                departureTbox.send_keys(Keys.ARROW_DOWN)
            if departureTerminal == 'T5':
                departureTbox.send_keys(Keys.ARROW_DOWN)
                departureTbox.send_keys(Keys.ARROW_DOWN)
                departureTbox.send_keys(Keys.ARROW_DOWN)
                departureTbox.send_keys(Keys.ARROW_DOWN)
            #set default prices: 
            self.__setroutepriceonpage(Yratio,Cratio,Fratio,Cargoratio)
            self.driver.find_element_by_xpath("//button[@name='p::submit']").click()
            wait.until(EC.presence_of_element_located((By.CLASS_NAME,"feedbackPanelINFO")))
    def __setroutepriceonpage(self,Yratio,Cratio,Fratio,Cargoratio):
        driver = self.driver
        #Find default prices: 
        Ydefaultpricetext = driver.find_element_by_xpath("//td[text()='Y']/following-sibling::td[@class='number']/span").text
        Ydefaultprice = int(''.join([i for i in Ydefaultpricetext if i.isdigit()]))
        Ycurrentprice = int(driver.find_element_by_xpath("//input[@name='classes:prices:0:newPrice']").get_attribute("value"))
        Yslider = driver.find_element_by_xpath("//td[text()='Y']/following-sibling::td[@class='slider-cell']/div/span")
        self.__executeslideprice(Yslider,Ycurrentprice,int(Ydefaultprice*Yratio))
        Cdefaultpricetext = driver.find_element_by_xpath("//td[text()='C']/following-sibling::td[@class='number']/span").text
        Cdefaultprice = int(''.join([i for i in Cdefaultpricetext if i.isdigit()]))
        Ccurrentprice = int(driver.find_element_by_xpath("//input[@name='classes:prices:1:newPrice']").get_attribute("value"))
        Cslider = driver.find_element_by_xpath("//td[text()='C']/following-sibling::td[@class='slider-cell']/div/span")
        self.__executeslideprice(Cslider,Ccurrentprice,int(Cdefaultprice*Cratio))
        Fdefaultpricetext = driver.find_element_by_xpath("//td[text()='F']/following-sibling::td[@class='number']/span").text
        Fdefaultprice = int(''.join([i for i in Fdefaultpricetext if i.isdigit()]))
        Fcurrentprice = int(driver.find_element_by_xpath("//input[@name='classes:prices:2:newPrice']").get_attribute("value"))
        Fslider = driver.find_element_by_xpath("//td[text()='F']/following-sibling::td[@class='slider-cell']/div/span")
        self.__executeslideprice(Fslider,Fcurrentprice,int(Fdefaultprice*Fratio))
        Cargodefaultpricetext = driver.find_element_by_xpath("//td[text()='Cargo']/following-sibling::td[@class='number']/span").text
        Cargodefaultprice = int(''.join([i for i in Cargodefaultpricetext if i.isdigit()]))
        Cargocurrentprice = int(driver.find_element_by_xpath("//input[@name='classes:prices:3:newPrice']").get_attribute("value"))
        Cargoslider = driver.find_element_by_xpath("//td[text()='Cargo']/following-sibling::td[@class='slider-cell']/div/span")
        self.__executeslideprice(Cargoslider,Cargocurrentprice,int(Cargodefaultprice*Cargoratio))
    def setrouteprice(self,departureIATA,arrivalIATA,Yratio=1.5,Cratio=1.65,Fratio=1.0,Cargoprice=0.5):
        driver = self.driver
        wait = WebDriverWait(driver,5)
        driver.get(self.serverURL+"/app/com/inventory/"+departureIATA+arrivalIATA)
        self.__setroutepriceonpage(Yratio,Cratio,Fratio,Cargoprice)
        driver.find_element_by_xpath("//button[@name='submit-prices']").click()
        wait.until(EC.presence_of_element_located((By.CLASS_NAME,"feedbackPanelINFO")))
    def __executeslideprice(self,sliderelement,currentprice,targetprice):
        if currentprice>targetprice:
            sliderelement.send_keys(Keys.ARROW_LEFT*int(currentprice - targetprice))
        elif currentprice < targetprice:
            sliderelement.send_keys(Keys.ARROW_RIGHT*int(targetprice - currentprice))
    def __selectdeparturetimeinassign(self,departuretime):#subroutine only used when in flight assignment page: 
        driver = self.driver
        wait = WebDriverWait(driver,10)
        hour = int(departuretime/100)
        hourstr=str(hour)
        if hour<10:
            hourstr="0"+hourstr
        minute = departuretime - 100*hour
        minutestr=str(minute)
        if minute<10:
            minutestr = "0"+minutestr
        print("Departure time: "+hourstr+":"+minutestr)
        wait.until(EC.element_to_be_clickable((By.XPATH,"//select[@name='departure:hours']")))
        hourbox = driver.find_element_by_xpath("//select[@name='departure:hours']")
        hourbox.send_keys(hourstr)
        hourbox.send_keys(Keys.ENTER)
        minutebox = driver.find_element_by_xpath("//select[@name='departure:minutes']")
        minutebox.send_keys(minutestr)
        minutebox.send_keys(Keys.ENTER)
    
    def __selectODpairinassign(self,departureIATA,arrivalIATA):#subroutine only used when in flight assignment page: 
        driver = self.driver
        wait = WebDriverWait(driver,10)
        departurebox = wait.until(EC.element_to_be_clickable((By.XPATH,"//span[@id='select2-chosen-2']")))
        setdepartureIATA = ActionChains(driver)
        setdepartureIATA.move_to_element(departurebox)
        setdepartureIATA.click()
        setdepartureIATA.send_keys("("+departureIATA)
        setdepartureIATA.send_keys(Keys.ENTER)
        setdepartureIATA.perform()
        arrivalbox = wait.until(EC.element_to_be_clickable((By.XPATH,"//span[@id='select2-chosen-3']")))
        setarrivalIATA = ActionChains(driver)
        setarrivalIATA.move_to_element(arrivalbox)
        setarrivalIATA.click()
        setarrivalIATA.send_keys("("+arrivalIATA)
        setarrivalIATA.send_keys(Keys.ENTER)
        setarrivalIATA.perform()

    def __executeassign(self,daysofweek=range(7)):#subroutine only used when in flight assignment page: 
        driver = self.driver
        wait = WebDriverWait(driver,10)
        while True:
            wait.until(EC.element_to_be_clickable((By.XPATH,"//a[@title='find first available']"))).click()
            wait.until_not(EC.presence_of_element_located((By.XPATH,"//input[@maxlength='4' and @value='']")))
            flightnumber = driver.find_element_by_xpath("//input[@maxlength='4']").get_attribute("value")
            driver.find_element_by_xpath("//input[@value='Create new flight number']").click()
            try: 
                speedupkey = wait.until(EC.element_to_be_clickable((By.XPATH,"//a[@title='set all with assignment to maximum speed']")))
                speedupkeyid = speedupkey.get_attribute("id")
                ActionChains(driver).move_to_element(speedupkey).click().perform()
                #speedupkey.click()
            except TimeoutException:
                #Then probably not correctly shifted to flight info page
                continue
            
            try: 
                wait.until_not(EC.presence_of_element_located((By.ID,speedupkeyid)))
            except TimeoutException:
                #Then probably speed override not enforced. Not a big issue for this usage. 
                pass
            except EC.NoSuchElementException:
                #Probably means not correctly shifted to page. Retry
                continue
            #Avoid speedup-caused aircraft performance issue: 
            try:
                assert len(driver.find_elements_by_xpath("//td[text()='Aircraft performance']/following-sibling::td/span[@class='fa fa-times bad']")) == 0
            except AssertionError:
                #Aircraft performance probably caused by speedup
                while True:
                    try:
                        speedneutralkey = wait.until(EC.element_to_be_clickable((By.XPATH,"//a[@title='remove all overrides']")))
                        speedneutralkeyid = speedneutralkey.get_attribute("id")
                        ActionChains(driver).move_to_element(speedneutralkey).click().perform()
                        #speedneutralkey.click()
                        wait.until_not(EC.presence_of_element_located((By.ID,speedneutralkeyid)))
                        break
                    except TimeoutException:
                        continue
            #days of week part, used for weekly assigns:
            if (daysofweek != range(7)):
                #apply none of the days first: 
                assignbox = driver.find_element_by_xpath("//input[contains(@name,'daySelection:"+str(0)+"')]")
                assignboxid = assignbox.get_attribute("id")
                wait.until(EC.element_to_be_clickable((By.LINK_TEXT,"none"))).click()
                wait.until_not(EC.presence_of_element_located((By.ID,assignboxid)))
                #Apply desired days: 
                for i in daysofweek:
                    assignbox = driver.find_element_by_xpath("//input[contains(@name,'daySelection:"+str(i)+"')]")
                    assignboxid = assignbox.get_attribute("id")
                    assignbox.click()
                    wait.until_not(EC.presence_of_element_located((By.ID,assignboxid)))
            while True:
                try: #Check flight time validity: 
                    assert len(driver.find_elements_by_xpath("//span[@class='fa fa-times bad']")) == 0
                    break
                except AssertionError:
                    #likely departure time not valid, set departure time forward (low level) by 5min
                    hourbox = driver.find_element_by_xpath("//select[@name='segmentSettings:0:newDeparture:hours']")
                    minutebox = driver.find_element_by_xpath("//select[@name='segmentSettings:0:newDeparture:minutes']")
                    #record a speedupkey to check that schedule is updated
                    speedupkeyID = driver.find_element_by_xpath("//a[@title='set all with assignment to maximum speed']").get_attribute("id")
                    if len(driver.find_elements_by_xpath("//tr[@class='departure']//span[contains(text(),':59')]"))==0: #if not 59:
                        shiftminute = ActionChains(driver)
                        shiftminute.move_to_element(minutebox)
                        shiftminute.click()
                        shiftminute.send_keys(Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.TAB)
                        shiftminute.perform()
                    else:
                        assert len(driver.find_elements_by_xpath("//tr[@class='departure']//span[contains(text(),'23:59')]")) == 0
                        #if is 23:59, then stop trying to avoid dead loop.
                        shifthourandminute = ActionChains(driver)
                        shifthourandminute.move_to_element(hourbox)
                        shifthourandminute.click()
                        shifthourandminute.send_keys(Keys.ARROW_DOWN+Keys.TAB)
                        shifthourandminute.perform()
                        wait.until_not(EC.presence_of_element_located((By.ID,speedupkeyID)))
                        speedupkeyID = driver.find_element_by_xpath("//a[@title='set all with assignment to maximum speed']").get_attribute("id")
                        minutebox = driver.find_element_by_xpath("//select[@name='segmentSettings:0:newDeparture:minutes']")
                        shiftminute = ActionChains(driver)
                        shiftminute.move_to_element(minutebox)
                        shiftminute.click()
                        shiftminute.send_keys("0"+Keys.TAB).perform()
                        
                    #check departure is actually different:
                    try:
                        wait.until_not(EC.presence_of_element_located((By.ID,speedupkeyID)))
                    except TimeoutException:
                        #If time change fails, still continue to next steps anyway.
                        pass
                    continue
            #Apply schedule
            ActionChains(driver).move_to_element(driver.find_element_by_xpath("//input[@value='Apply schedule settings']")).click().perform()
            #driver.find_element_by_xpath("//input[@value='Apply schedule settings']").click()
            while True:
                try:
                    wait.until_not(EC.presence_of_element_located((By.XPATH,"//input[@name='button-remove']")))
                    break
                except TimeoutException:
                    print("Consider manually applying flights: ")
                    continue
            break
        return flightnumber
    def odshuttle(self,departureIATA,arrivalIATA,firstflighttime,cyclecount,aircraftID):
        driver = self.driver
        #open aircraft page
        wait = WebDriverWait(driver,10)
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(aircraftID)+"/0"
        driver.get(aircraftURL)
        #select OD pair
        self.__selectODpairinassign(departureIATA,arrivalIATA)
        #select initial departure time
        self.__selectdeparturetimeinassign(firstflighttime)
        #iterate through all departure cycles: 
        for i in range(2*cyclecount):
            self.__executeassign()
    def odhubspoke(self,hubIATA,spokeIATAs,firstflighttime,aircraftID):
        driver = self.driver
        #open aircraft page
        wait = WebDriverWait(driver,10)
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(aircraftID)+"/0"
        driver.get(aircraftURL)
        self.__selectdeparturetimeinassign(firstflighttime)
        for spokeIATA in spokeIATAs:
            self.__selectODpairinassign(hubIATA,spokeIATA)
            self.__executeassign()
            self.__selectODpairinassign(spokeIATA,hubIATA)
            self.__executeassign()
    def seg(self,targetIATA,depttime,turndelay=0):
        #Assume already in AC page:
        driver = self.driver
        hubIATAlongstring = driver.find_element_by_id("select2-chosen-2").text
        hubIATA = hubIATAlongstring[-4:-1]
        self.__selectdeparturetimeinassign(depttime)
        self.__selectODpairinassign(hubIATA,targetIATA)
        self.__executeassign()
        default_return_time = self.__get_depature_time()
        newtime = time_shift_by_min(default_return_time,turndelay)
        self.__selectdeparturetimeinassign(newtime)
        self.__selectODpairinassign(targetIATA,hubIATA)
        self.__executeassign()
    def __get_depature_time(self):
        #Find departure time in flight assignment page
        driver = self.driver
        departurehour = int(driver.find_element_by_xpath("//select[@name='departure:hours']//option[@selected='selected']").get_attribute("value"))
        departureminute = int(driver.find_element_by_xpath("//select[@name='departure:minutes']//option[@selected='selected']").get_attribute("value"))
        return departurehour*100+departureminute
    def odchain(self,IATAchain,firstflighttime,aircraftID):
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(aircraftID)+"/0"
        self.driver.get(aircraftURL)
        originIATA = IATAchain[0]
        print("assign flight chain: ")
        print(IATAchain)
        self.__selectdeparturetimeinassign(firstflighttime)
        for destIATA in IATAchain[1:]:
            self.__selectODpairinassign(originIATA,destIATA)
            self.__executeassign()
            originIATA = destIATA
    def assignweeklyinteractive(self,fleetreference):
        targetIDs = self.getaircraftnumber(fleetreference)
        driver = self.driver
        #open aircraft page
        wait = WebDriverWait(driver,10)
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(targetIDs[0])+"/0"
        driver.get(aircraftURL)
        print("Stage 1: create weekly rotation")
        departureIATA=input("departure IATA: ")
        weekday = 0
        while True:
            destinationIATA = input("next destination (or type N to enter next stage): ")
            if destinationIATA=='N':
                break
            try:
                departureTime=int(input("next departure time (use non-integer input for default): "))
                self.__selectdeparturetimeinassign(departureTime)
            except ValueError:
                pass
            self.__selectODpairinassign(departureIATA,destinationIATA)
            previousflightnumber = self.__executeassign([weekday])
            #figure out next weekday: shift to next day if some maintain block exists for the next weekday. 
            try: 
                nextweekday = weekday+1
                if nextweekday == 7:
                    nextweekday = 0
                driver.find_element_by_xpath("(//div[@class='day'])["+str(nextweekday+1)+"]/div/div[starts-with(@class,'block ready')]/div/span")
                weekday += 1
                if weekday == 7:
                    weekday = 0
            except EC.NoSuchElementException:
                pass
            departureIATA = destinationIATA
        nextaction = input("Stage 2: Apply created rotation. Type C to continue, R to restart assignment, or anything else to do nothing")
        if nextaction == 'C':
            self.assignweeklybyfleet(fleetreference)
        if nextaction == 'R':
            selectactivate = ActionChains(driver)
            selectactivate.move_to_element(driver.find_element_by_xpath("//select[@class='form-control' and @name='select']"))
            selectactivate.click()
            selectactivate.send_keys(Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN)
            selectactivate.perform()
            selectactivate.move_to_element(driver.find_element_by_xpath("//input[@value='execute...']")).click().perform()
            driver.get(self.serverURL+"/app/com/numbers")
            wait.until(EC.presence_of_element_located((By.XPATH,"//input[@name='ignoreEmptyAssignments']"))).click()
            driver.find_element_by_xpath("//div/buttion[@class='btn btn-danger']").click()
            self.assignweeklyinteractive(fleetreference)
#    def intelligent_fleet_assignment(self,hubIATA,destination_csv_filename,fleetreference,rotation_count,distance_bound,freshstart=False,turnaround_time=70.0,speed_in_minute=14.0,time_difference_in_minute=0):
#        aircraftpool = self.getaircraftnumber(fleetreference)
#        dest_gen_instance = dest_gen.Integer_programming_rotation_finder(destination_csv_filename)
#        existing_departure = self.get_departure_count(hubIATA)
#        if not freshstart:
#            for destIATA_flight_count_pair in existing_departure:
#                dest_gen_instance.adjust_existing_rotation(destIATA_flight_count_pair[0],destIATA_flight_count_pair[1])
#        rotation_list = dest_gen_instance.find_rotations(len(aircraftpool),rotation_count,distance_bound)
#        for aircraft,rotation in zip(aircraftpool,rotation_list):
#            #get departure time
#            departure_time = dest_gen_instance.find_departure_time(rotation,turnaround_time,speed_in_minute,time_difference_in_minute)
#            while departure_time < 0:
#                rotation = dest_gen_instance.find_next_rotation(rotation_count,distance_bound)
#                departure_time = dest_gen_instance.find_departure_time(rotation,turnaround_time,speed_in_minute,time_difference_in_minute)
#            try: 
#                self.odhubspoke(hubIATA,rotation,departure_time,aircraft)
#            except:
#                print("Assignment for an aircraft may failed, continue to next one")
#                continue
    def get_departure_count(self,hubIATA):
        #returns a list of pair [destIATA,depature]
        rval = []
        driver = self.driver
        wait = WebDriverWait(driver,2)
        driver.get(self.serverURL+"/app/com/scheduling/"+hubIATA+"BRW")
        dest_IATA_list = [element.text for element in driver.find_elements_by_xpath("//td/a[starts-with(@href,'./"+hubIATA+"')]/following-sibling::span")]
        dest_flightcount_list = [int(element.text) for element in driver.find_elements_by_xpath("//td/a[starts-with(@href,'./"+hubIATA+"')]/parent::td/following-sibling::td[@class='number']")]
        for dest_IATA,dest_flightcount in zip(dest_IATA_list,dest_flightcount_list):
            if dest_flightcount > 0:
                rval.append([dest_IATA,dest_flightcount])
        return rval

            

    def bidallAC(self):
        driver = self.driver
        wait = WebDriverWait(driver,2)
        while True:
            try:
                bidURL = driver.find_element_by_xpath("//a[contains(@href,'aircraftOfferPanel-bid-leasingOfficial')]")
                driver.get(bidURL.get_attribute("href"))
            except EC.NoSuchElementException:
                break
            except TimeoutException:
                continue
    def assignweekly(self,flightplan,aircraftIDs):
        assert isinstance(flightplan,FlightPlan)
        for aircraftID in aircraftIDs:
            assert isinstance(aircraftID,int)
            self.assignflightplan(flightplan,aircraftID)
            flightplan.rotateweekday(1)
    def assignweeklylazy(self,sourceaircraftID,targetaircraftIDs):
        #As a further simplification, target IDs can contain source ID
        try:
            targetaircraftIDs.remove(sourceaircraftID)
        except ValueError:
            pass
        FP = self.readFP(sourceaircraftID)
        FP.rotateweekday()
        self.assignweekly(FP,targetaircraftIDs)
    def assignweeklybyfleet(self,fleetreference): 
        assert isinstance(fleetreference,str) or isinstance(fleetreference,int)
        targetIDs = self.getaircraftnumber(fleetreference)
        sourceaircraftURL = self.driver.find_element_by_xpath("//a[@class='btn btn-warning']").get_attribute("href")
        sourceID = [int(i) for i in sourceaircraftURL.split('/') if i.isdigit()][0]
        self.assignweeklylazy(sourceID,targetIDs)
    def setspeed(self,flightnumber,speed):#To be member function
        wait = WebDriverWait(self.driver,10)
        self.driver.get(self.tokenaircraftURL)
        selectflight(self.driver,flightnumber)
        for i in range(7):
            while True:
                try:
                    speedbox = wait.until(EC.element_to_be_clickable((By.XPATH,"//input[contains(@name,'speed-overrides:"+str(i)+"')]")))
                    speedboxid = speedbox.get_attribute("id")
                    speedbox.clear()
                    speedbox.send_keys(str(speed))
                    #Enter twice to force webpage reload
                    speedbox.send_keys(Keys.ENTER)
                    speedbox.send_keys(Keys.ENTER)
                    wait.until_not(EC.presence_of_element_located((By.ID,speedboxid)))
                    break
                except TimeoutException:
                    break
        self.driver.find_element_by_xpath("//input[@value='Apply schedule settings']").send_keys(Keys.ENTER)
    def getaircraftURL(self,fleetreference=0):#To be member function
        wait = WebDriverWait(self.driver,10)
        try:
            fleetID=int(fleetreference)
            self.driver.get(self.serverURL+"/app/fleets/"+str(fleetID))
        except ValueError:
            self.driver.get(self.serverURL+"/app/fleets/")
            wait.until(EC.element_to_be_clickable((By.XPATH,"//a[contains(.,'"+str(fleetreference)+"')]"))).click()
            wait.until(EC.presence_of_element_located((By.XPATH,"//h2[contains(.,'"+str(fleetreference)+"')]")))
        return [i.get_attribute("href") for i in self.driver.find_elements_by_xpath("//a[@title='Flight Planning']")]
    def getaircraftnumber(self,fleetreference=0):#To be member function
        URLs = self.getaircraftURL(fleetreference)
        rval = []
        for URL in URLs:
            rval.append([int(i) for i in URL.split('/') if i.isdigit()][0])
        return rval
    def close(self):
        self.driver.close()
    def activatefleet(self,fleetreference=0,activate_3_days=False):
        aircraftnumbers = self.getaircraftnumber(fleetreference)
        for aircraftnumber in aircraftnumbers:
            self.activateaircraft(aircraftnumber,activate_3_days)
    def activateaircraft(self,aircraftnumber,activate_3_days=False):
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(aircraftnumber)
        driver = self.driver
        driver.get(aircraftURL)
        selectactivate = ActionChains(driver)
        selectactivate.move_to_element(driver.find_element_by_xpath("//select[@class='form-control' and @name='select']"))
        selectactivate.click()
        if activate_3_days:
            selectactivate.send_keys(Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_DOWN+Keys.ARROW_DOWN)
        else:
            selectactivate.send_keys(Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_DOWN)
        selectactivate.perform()
        selectactivate.move_to_element(driver.find_element_by_xpath("//input[@value='execute...']")).click().perform()
        wait = WebDriverWait(driver,5)
        try:
            wait.until(EC.presence_of_element_located((By.XPATH,"//option[@selected='selected' and contains(text(),'Activate Flight Plan')]")))
        except TimeoutException:
            print("Activate may failed")
    def lockfleet(self,fleetreference=0):
        aircraftnumbers = self.getaircraftnumber(fleetreference)
        for aircraftnumber in aircraftnumbers:
            self.lockaircraft(aircraftnumber)
    def lockaircraft(self,aircraftnumber):
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(aircraftnumber)
        driver = self.driver
        driver.get(aircraftURL)
        selectlock = ActionChains(driver)
        selectlock.move_to_element(driver.find_element_by_xpath("//select[@class='form-control' and @name='select']"))
        selectlock.click()
        selectlock.send_keys(Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_UP+Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN)
        selectlock.perform()
        selectlock.move_to_element(driver.find_element_by_xpath("//input[@value='execute...']")).click().perform()
        wait = WebDriverWait(driver,5)
        try:
            wait.until(EC.presence_of_element_located((By.XPATH,"//option[@selected='selected' and text()='Lock flight Plan']")))
        except TimeoutException:
            print("Lock may failed")
    def deletefleet(self,fleetreference=0):
        aircraftnumbers = self.getaircraftnumber(fleetreference)
        for aircraftnumber in aircraftnumbers:
            self.deleteaircraft(aircraftnumber)
    def deleteaircraft(self,aircraftnumber):
        aircraftURL = self.serverURL+"/app/fleets/aircraft/"+str(aircraftnumber)
        driver = self.driver
        driver.get(aircraftURL)
        selectlock = ActionChains(driver)
        selectlock.move_to_element(driver.find_element_by_xpath("//select[@class='form-control' and @name='select']"))
        selectlock.click()
        selectlock.send_keys(Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN+Keys.ARROW_DOWN)
        selectlock.perform()
        selectlock.move_to_element(driver.find_element_by_xpath("//input[@value='execute...']")).click().perform()
        wait = WebDriverWait(driver,5)
        try:
            wait.until(EC.presence_of_element_located((By.XPATH,"//option[@selected='selected' and text()='Delete flight Plan']")))
        except TimeoutException:
            print("Delete may failed")



class Flight:
    'A flight number consists of dep/arr and time speed etc. '
    def __init__(self,flightnumber,dep,arr,time,spd=None):
        self.flightnumber=int(flightnumber)
        self.dep = str(dep)
        self.arr = str(arr)
        self.time=int(time)
        self.spd = spd

class FlightPlan:
    'A weekly flight plan for an aircraft'
    def __init__(self,flightsbyday = [[],[],[],[],[],[],[]]):
        assert len(flightsbyday)==7
        self.flightsbyday = flightsbyday
    def setflightonweekday(self,weekday,flightnumbers):
        self.flightsbyday[weekday] = flightnumbers
    def addflight(self,flight,weekdays=range(7)):
        flightnumber = None
        try:
            assert isinstance(flight,Flight)
            flightnumber=flight.flightnumber
        except AssertionError:           
            flightnumber=int(flight)
        for weekday in weekdays:
            self.flightsbyday[weekday].append(flightnumber)
    def rotateweekday(self,daystoshift=1):
        nval = self.flightsbyday[-daystoshift:] + self.flightsbyday[:-daystoshift]
        self.flightsbyday = nval
    def __str__(self):
        rval = "M "
        for flightnumber in self.flightsbyday[0]:
            rval += str(flightnumber)+" "
        rval += "T "
        for flightnumber in self.flightsbyday[1]:
            rval += str(flightnumber)+" "
        rval += "W "
        for flightnumber in self.flightsbyday[2]:
            rval += str(flightnumber)+" "
        rval += "H "
        for flightnumber in self.flightsbyday[3]:
            rval += str(flightnumber)+" "
        rval += "F "
        for flightnumber in self.flightsbyday[4]:
            rval += str(flightnumber)+" "
        rval += "S "
        for flightnumber in self.flightsbyday[5]:
            rval += str(flightnumber)+" "
        rval += "U "
        for flightnumber in self.flightsbyday[6]:
            rval += str(flightnumber)+" "
        return rval


def login(driver,serverURL):
    username = "USERNAME"
    password = "PASSWORD"
    while True:
        wait = WebDriverWait(driver,3)
        driver.get("https://accounts.airlinesim.aero/app/auth/login?0")
        try:
            usernamefield = driver.find_element_by_name("username")
            usernamefield.clear()
            usernamefield.send_keys(username)
            passwordfield = driver.find_element_by_name("password")
            passwordfield.click()
            passwordfield.clear()
            passwordfield.send_keys(password)
            Loginbutton = driver.find_element_by_xpath("//div[@class='account login']/input[3]")
            Loginbutton.click()
        except EC.NoSuchElementException:
            if len(driver.find_elements_by_xpath("//h2[text()='Login successful']"))>0:
                driver.get(serverURL)
                break
        driver.get(serverURL)
        try:
            driver.find_element_by_xpath("//a[contains(@href,'/app/auth/login')]").click()
        except EC.NoSuchElementException:
            continue
        driver.refresh()
        try:
            driver.find_element_by_xpath("//a[contains(@href,'/app/auth/login')]").click()
        except EC.NoSuchElementException:
            continue
        try:
            wait.until(EC.presence_of_element_located((By.XPATH,"//a[@title='Settings']")))
            break
        except TimeoutException:
            print("login failed, trying again...")
            continue
            

#Non member functions that are "Low level", and used in initializing airlinesimInstance:
def selectenterprise(driver,enterpriseIDinput,serverURL):
    wait = WebDriverWait(driver,10)
    driver.get(serverURL+"/app/enterprise/dashboard?select="+str(enterpriseIDinput))
    enterprisedropdown = wait.until(EC.element_to_be_clickable((By.XPATH,"//ul[@class='nav navbar-nav']/li[1]")))
    ActionChains(driver).move_to_element(enterprisedropdown).perform()
    #enterpriselink = driver.find_element_by_link_(text)(enterpriseID)
    #enterpriselink.click()
def checklogin(driver):
    try:
        driver.find_element_by_link_text("Login").click()
    except EC.NoSuchElementException:
        print("Logged in already")
def gettokenaircraftURL(driver,serverURL):
    wait = WebDriverWait(driver,10)
    driver.get(serverURL+"/app/fleets")
    aircrafthref = wait.until(EC.presence_of_element_located((By.XPATH,"//div[@class='btn-group']/a[1]"))).get_attribute("href")
    #driver.find_element_by_xpath("//div[@class='btn-group']/a[1]").get_attribute("href")
    return aircrafthref
def selectflight(driver,flightnumber):
    wait = WebDriverWait(driver,5)
    wait.until(EC.element_to_be_clickable((By.XPATH,"//a[contains(.,'Existing Flight Number')]"))).click()
    #driver.find_element_by_link_text("//a[text() = 'Existing Flight Number']").click()
    wait.until(
        EC.presence_of_element_located((By.XPATH,"//div[@class='layout-col-md-4']/div[1]/select[1]/option[1]"))
    )
    insertflightnumber = ActionChains(driver)
    for i in range(3):
        try:
            wait.until(EC.presence_of_element_located((By.XPATH,"//option[starts-with(text(),'"+str(flightnumber)+":')]")))
            break
        except TimeoutException:
            continue
    flightnumberbox = driver.find_element_by_xpath("//div[@class='layout-col-md-4']/div[1]/select[1]")
    insertflightnumber.move_to_element(flightnumberbox)
    insertflightnumber.click()
    insertflightnumber.send_keys(str(flightnumber)+Keys.ENTER)
    insertflightnumber.perform()
    try:
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT,"invert")))
    except TimeoutException:
        print("Flight selection failed, trying again")
        selectflight(driver,flightnumber)
    #further increase robustness: double check correct flight is selected: 
    try:
        driver.find_element_by_xpath("//option[@selected='selected' and starts-with(text(),'"+str(flightnumber)+":')]")
    except EC.NoSuchElementException:
        print("Did not select the right flight, trying again")
        selectflight(driver,flightnumber)


def assignflighttoaircraft_low_level(driver,serverURL,flightnumber,aircraftnumber,daystoassign=range(7)):
    while True:
        try:
            wait = WebDriverWait(driver,10)
            aircraftURL = serverURL+"/app/fleets/aircraft/"+str(aircraftnumber)+"/0"
            if not driver.current_url.startswith(aircraftURL):
                driver.get(aircraftURL)
            selectflight(driver,flightnumber)
            for i in daystoassign:
                assignbox = driver.find_element_by_xpath("//input[contains(@name,'daySelection:"+str(i)+"')]")
                assignboxid = assignbox.get_attribute("id")
                assignbox.click()
                wait.until_not(EC.presence_of_element_located((By.ID,assignboxid)))
            Applybutton = driver.find_element_by_xpath("//input[@value='Apply schedule settings']")
            Applybuttonid = Applybutton.get_attribute("id")
            Applybutton.send_keys(Keys.ENTER)
            wait.until_not(EC.presence_of_element_located((By.ID,Applybuttonid)))
            break
        except (TimeoutException,EC.NoSuchElementException):
            continue


def main():
    asi = ASInstance(6498,'riem')
    asi.get_departure_count("JFK")

if __name__ == '__main__':
    main()
