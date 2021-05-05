from itertools import cycle
from airlinesim import ASInstance
import sys
ASI = ASInstance(340,'reality')
aircraftpool = ASI.getaircraftnumber('autoassign')
hubIATA = 'ORD'
destIATAlist = ['MHT','PVD','ISP','SAV','ORF','TUL','OKC','ALB','CHS']
destIATAcycle = cycle(destIATAlist)
cyclelength = 3
for aircraftindex in range(len(aircraftpool)):
    try:
        aircraftIATAlist = [next(destIATAcycle) for i in range(cyclelength)]
        print("assign to ")
        print(aircraftIATAlist)
        ASI.odhubspoke(hubIATA,aircraftIATAlist,330,aircraftpool[aircraftindex])
    except:
        print("Assign failed for pair")
ASI.driver.close()